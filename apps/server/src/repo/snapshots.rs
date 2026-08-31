use chrono::{DateTime, Utc};
use serde::Serialize;
use sha2::{Digest, Sha256};
use sqlx::{MySql, MySqlPool, Transaction};

use crate::{
    error::{AppError, AppResult},
    models::{
        dto::{
            SnapshotInput, SnapshotPricingDto, SnapshotProductDto, SnapshotSalesDto,
            SnapshotSellerDto, SnapshotShippingDto, SnapshotSkuDto,
        },
        entity::{ProductPlatform, ProductSnapshotRef},
    },
};

#[derive(Debug, Serialize)]
struct SnapshotHashPayload<'a> {
    platform: &'a str,
    platform_product_id: &'a str,
    captured_at: DateTime<Utc>,
    product: &'a SnapshotProductDto,
    pricing: &'a SnapshotPricingDto,
    sales: &'a SnapshotSalesDto,
    seller: &'a SnapshotSellerDto,
    shipping: &'a SnapshotShippingDto,
    sku: &'a [SnapshotSkuDto],
}

pub fn compute_snapshot_hash(
    input: &SnapshotInput,
    platform_product_id: &str,
) -> AppResult<String> {
    let payload = SnapshotHashPayload {
        platform: &input.platform,
        platform_product_id,
        captured_at: input.captured_at,
        product: &input.product,
        pricing: &input.pricing,
        sales: &input.sales,
        seller: &input.seller,
        shipping: &input.shipping,
        sku: &input.sku,
    };
    let canonical = serde_json::to_string(&payload)?;
    let digest = Sha256::digest(canonical.as_bytes());
    Ok(hex::encode(digest))
}

pub async fn find_existing_snapshot(
    pool: &MySqlPool,
    product_platform_id: u64,
    snapshot_hash: &str,
) -> AppResult<Option<ProductSnapshotRef>> {
    sqlx::query_as::<_, ProductSnapshotRef>(
        r#"
        SELECT id, product_platform_id, snapshot_hash
        FROM product_snapshots
        WHERE product_platform_id = ? AND snapshot_hash = ?
        "#,
    )
    .bind(product_platform_id)
    .bind(snapshot_hash)
    .fetch_optional(pool)
    .await
    .map_err(AppError::from)
}

pub async fn ingest_one(
    pool: &MySqlPool,
    crawl_task_id: u64,
    input: &SnapshotInput,
) -> AppResult<IngestOutcome> {
    let platform_product_id = resolve_platform_product_id(input)?;
    let snapshot_hash = compute_snapshot_hash(input, &platform_product_id)?;

    let mut tx = pool.begin().await?;
    let platform = upsert_product_platform(&mut tx, input, &platform_product_id).await?;

    if let Some(existing) =
        find_existing_snapshot_in_tx(&mut tx, platform.id, &snapshot_hash).await?
    {
        tx.commit().await?;
        return Ok(IngestOutcome::Duplicate {
            product_snapshot_id: existing.id,
            product_platform_id: platform.id,
        });
    }

    let snapshot_id =
        insert_product_snapshot(&mut tx, platform.id, crawl_task_id, input, &snapshot_hash).await?;

    insert_price_snapshot(&mut tx, snapshot_id, platform.id, input).await?;
    insert_sales_snapshot(&mut tx, snapshot_id, platform.id, input).await?;
    insert_sku_snapshots(&mut tx, snapshot_id, input).await?;
    insert_seller_snapshot(&mut tx, snapshot_id, input).await?;
    insert_shipping_snapshot(&mut tx, snapshot_id, input).await?;
    insert_media_snapshots(&mut tx, snapshot_id, input).await?;
    insert_raw_snapshot(&mut tx, snapshot_id, input).await?;

    tx.commit().await?;
    Ok(IngestOutcome::Created {
        product_snapshot_id: snapshot_id,
        product_platform_id: platform.id,
    })
}

pub enum IngestOutcome {
    Created {
        product_snapshot_id: u64,
        product_platform_id: u64,
    },
    Duplicate {
        product_snapshot_id: u64,
        product_platform_id: u64,
    },
}

fn resolve_platform_product_id(input: &SnapshotInput) -> AppResult<String> {
    input
        .product
        .platform_product_id
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .ok_or_else(|| AppError::BadRequest("product.platform_product_id is required".into()))
}

async fn upsert_product_platform(
    tx: &mut Transaction<'_, MySql>,
    input: &SnapshotInput,
    platform_product_id: &str,
) -> AppResult<ProductPlatform> {
    let now = input.captured_at;
    let title = input
        .product
        .title
        .as_deref()
        .filter(|value| !value.is_empty())
        .unwrap_or(platform_product_id);

    if let Some(existing) =
        find_product_platform_in_tx(tx, &input.platform, platform_product_id).await?
    {
        sqlx::query(
            r#"
            UPDATE product_platforms
            SET title = ?, url = ?, shop_id = ?, shop_name = ?, seller_id = ?,
                last_seen_at = ?, updated_at = CURRENT_TIMESTAMP(6)
            WHERE id = ?
            "#,
        )
        .bind(&input.product.title)
        .bind(&input.product.url)
        .bind(&input.product.shop_id)
        .bind(&input.product.shop_name)
        .bind(&input.product.seller_id)
        .bind(now)
        .bind(existing.id)
        .execute(&mut **tx)
        .await?;

        return Ok(existing);
    }

    let product_id = insert_product(tx, title, &input.product).await?;
    sqlx::query(
        r#"
        INSERT INTO product_platforms (
            product_id, platform, platform_product_id, url, title,
            shop_id, shop_name, seller_id, status, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        "#,
    )
    .bind(product_id)
    .bind(&input.platform)
    .bind(platform_product_id)
    .bind(&input.product.url)
    .bind(&input.product.title)
    .bind(&input.product.shop_id)
    .bind(&input.product.shop_name)
    .bind(&input.product.seller_id)
    .bind(now)
    .bind(now)
    .execute(&mut **tx)
    .await?;

    find_product_platform_in_tx(tx, &input.platform, platform_product_id)
        .await?
        .ok_or_else(|| AppError::Other(anyhow::anyhow!("product_platform insert failed")))
}

async fn insert_product(
    tx: &mut Transaction<'_, MySql>,
    name: &str,
    product: &SnapshotProductDto,
) -> AppResult<u64> {
    let result = sqlx::query(
        r#"
        INSERT INTO products (name, brand, description, cover_url, status)
        VALUES (?, ?, ?, ?, 'active')
        "#,
    )
    .bind(name)
    .bind(&product.brand)
    .bind(&product.description)
    .bind(&product.cover_url)
    .execute(&mut **tx)
    .await?;

    Ok(result.last_insert_id())
}

async fn find_product_platform_in_tx(
    tx: &mut Transaction<'_, MySql>,
    platform: &str,
    platform_product_id: &str,
) -> AppResult<Option<ProductPlatform>> {
    sqlx::query_as::<_, ProductPlatform>(
        r#"
        SELECT id, product_id, platform, platform_product_id
        FROM product_platforms
        WHERE platform = ? AND platform_product_id = ?
        "#,
    )
    .bind(platform)
    .bind(platform_product_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(AppError::from)
}

async fn find_existing_snapshot_in_tx(
    tx: &mut Transaction<'_, MySql>,
    product_platform_id: u64,
    snapshot_hash: &str,
) -> AppResult<Option<ProductSnapshotRef>> {
    sqlx::query_as::<_, ProductSnapshotRef>(
        r#"
        SELECT id, product_platform_id, snapshot_hash
        FROM product_snapshots
        WHERE product_platform_id = ? AND snapshot_hash = ?
        "#,
    )
    .bind(product_platform_id)
    .bind(snapshot_hash)
    .fetch_optional(&mut **tx)
    .await
    .map_err(AppError::from)
}

async fn insert_product_snapshot(
    tx: &mut Transaction<'_, MySql>,
    product_platform_id: u64,
    crawl_task_id: u64,
    input: &SnapshotInput,
    snapshot_hash: &str,
) -> AppResult<u64> {
    let result = sqlx::query(
        r#"
        INSERT INTO product_snapshots (
            product_platform_id, crawl_task_id, captured_at, title, subtitle,
            description, brand, category, attributes_json, cover_url, snapshot_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(product_platform_id)
    .bind(crawl_task_id)
    .bind(input.captured_at)
    .bind(&input.product.title)
    .bind(&input.product.subtitle)
    .bind(&input.product.description)
    .bind(&input.product.brand)
    .bind(&input.product.category)
    .bind(&input.product.attributes)
    .bind(&input.product.cover_url)
    .bind(snapshot_hash)
    .execute(&mut **tx)
    .await?;

    Ok(result.last_insert_id())
}

async fn insert_price_snapshot(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    product_platform_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    let pricing = &input.pricing;
    if pricing.price.is_none() && pricing.original_price.is_none() && pricing.price_text.is_none() {
        return Ok(());
    }

    sqlx::query(
        r#"
        INSERT INTO price_snapshots (
            product_snapshot_id, product_platform_id, currency, price, original_price,
            min_price, max_price, discount_amount, coupon_amount, shipping_fee,
            price_text, captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(snapshot_id)
    .bind(product_platform_id)
    .bind(pricing.currency.as_deref().unwrap_or("CNY"))
    .bind(decimal_opt(pricing.price))
    .bind(decimal_opt(pricing.original_price))
    .bind(decimal_opt(pricing.min_price))
    .bind(decimal_opt(pricing.max_price))
    .bind(decimal_opt(pricing.discount_amount))
    .bind(decimal_opt(pricing.coupon_amount))
    .bind(decimal_opt(pricing.shipping_fee))
    .bind(&pricing.price_text)
    .bind(input.captured_at)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn insert_sales_snapshot(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    product_platform_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    let sales = &input.sales;
    sqlx::query(
        r#"
        INSERT INTO sales_snapshots (
            product_snapshot_id, product_platform_id, sales_count, sales_period,
            sales_text, review_count, rating, favorite_count, want_count,
            view_count, captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(snapshot_id)
    .bind(product_platform_id)
    .bind(sales.sales_count)
    .bind(&sales.sales_period)
    .bind(&sales.sales_text)
    .bind(sales.review_count)
    .bind(sales.rating)
    .bind(sales.favorite_count)
    .bind(sales.want_count)
    .bind(sales.view_count)
    .bind(input.captured_at)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn insert_sku_snapshots(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    for sku in &input.sku {
        sqlx::query(
            r#"
            INSERT INTO sku_snapshots (
                product_snapshot_id, platform_sku_id, sku_name, attributes_json,
                price, original_price, stock, sku_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(snapshot_id)
        .bind(&sku.platform_sku_id)
        .bind(&sku.sku_name)
        .bind(&sku.attributes)
        .bind(decimal_opt(sku.price))
        .bind(decimal_opt(sku.original_price))
        .bind(sku.stock)
        .bind(&sku.data)
        .execute(&mut **tx)
        .await?;
    }
    Ok(())
}

async fn insert_seller_snapshot(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    let seller = &input.seller;
    if seller.seller_id.is_none() && seller.shop_name.is_none() {
        return Ok(());
    }

    sqlx::query(
        r#"
        INSERT INTO seller_snapshots (
            product_snapshot_id, seller_id, shop_id, shop_name, seller_level,
            rating, positive_rate, follower_count, transaction_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(snapshot_id)
    .bind(&seller.seller_id)
    .bind(&seller.shop_id)
    .bind(&seller.shop_name)
    .bind(&seller.seller_level)
    .bind(seller.rating)
    .bind(seller.positive_rate)
    .bind(seller.follower_count)
    .bind(seller.transaction_count)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn insert_shipping_snapshot(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    let shipping = &input.shipping;
    if shipping.origin.is_none()
        && shipping.destination.is_none()
        && shipping.shipping_fee.is_none()
    {
        return Ok(());
    }

    sqlx::query(
        r#"
        INSERT INTO shipping_snapshots (
            product_snapshot_id, origin, destination, shipping_fee, free_shipping,
            delivery_time, fulfillment_type, shipping_data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(snapshot_id)
    .bind(&shipping.origin)
    .bind(&shipping.destination)
    .bind(decimal_opt(shipping.shipping_fee))
    .bind(shipping.free_shipping.map(|value| i8::from(value)))
    .bind(&shipping.delivery_time)
    .bind(&shipping.fulfillment_type)
    .bind(&shipping.data)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn insert_media_snapshots(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    for (index, media) in input.media.iter().enumerate() {
        let Some(url) = media.url.as_deref().filter(|value| !value.is_empty()) else {
            continue;
        };
        sqlx::query(
            r#"
            INSERT INTO product_media_snapshots (
                product_snapshot_id, media_type, url, sort_order, metadata_json
            ) VALUES (?, ?, ?, ?, ?)
            "#,
        )
        .bind(snapshot_id)
        .bind(media.media_type.as_deref().unwrap_or("image"))
        .bind(url)
        .bind(media.sort_order.unwrap_or(index as i32))
        .bind(&media.metadata)
        .execute(&mut **tx)
        .await?;
    }
    Ok(())
}

async fn insert_raw_snapshot(
    tx: &mut Transaction<'_, MySql>,
    snapshot_id: u64,
    input: &SnapshotInput,
) -> AppResult<()> {
    let raw = &input.raw;
    let Some(data) = &raw.data else {
        return Ok(());
    };

    sqlx::query(
        r#"
        INSERT INTO raw_snapshots (
            product_snapshot_id, platform, raw_data_json, content_type,
            data_version, crawler_version
        ) VALUES (?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(snapshot_id)
    .bind(&input.platform)
    .bind(data)
    .bind(&raw.content_type)
    .bind(&raw.data_version)
    .bind(&raw.crawler_version)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

fn decimal_opt(value: Option<crate::models::dto::DecimalField>) -> Option<rust_decimal::Decimal> {
    value.and_then(|field| field.to_sql_decimal())
}
