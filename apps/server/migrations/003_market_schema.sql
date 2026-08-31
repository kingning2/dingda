-- Migrate legacy auth table and replace crawler products with market schema.

ALTER TABLE users
    ADD COLUMN email VARCHAR(255) NULL AFTER id,
    ADD COLUMN name VARCHAR(128) NULL AFTER email,
    ADD COLUMN avatar VARCHAR(1024) NULL AFTER name,
    ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active' AFTER avatar;

UPDATE users
SET email = CONCAT(username, '@local.invalid')
WHERE email IS NULL;

ALTER TABLE users
    MODIFY email VARCHAR(255) NOT NULL,
    ADD UNIQUE KEY uq_users_email (email);

ALTER TABLE users
    DROP INDEX uq_users_username,
    DROP COLUMN username;

DROP TABLE IF EXISTS products;

CREATE TABLE workspaces (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    owner_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_workspaces_owner_id (owner_id),
    CONSTRAINT fk_workspaces_owner FOREIGN KEY (owner_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE workspace_members (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'member',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_workspace_members (workspace_id, user_id),
    KEY ix_workspace_members_user_id (user_id),
    CONSTRAINT fk_workspace_members_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_workspace_members_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(512) NOT NULL,
    brand VARCHAR(128) NULL,
    model VARCHAR(128) NULL,
    category_id BIGINT UNSIGNED NULL,
    description TEXT NULL,
    cover_url VARCHAR(1024) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_products_status (status),
    KEY ix_products_category_id (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_platforms (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_id BIGINT UNSIGNED NOT NULL,
    platform VARCHAR(32) NOT NULL,
    platform_product_id VARCHAR(128) NOT NULL,
    url TEXT NULL,
    title VARCHAR(512) NULL,
    shop_id VARCHAR(128) NULL,
    shop_name VARCHAR(256) NULL,
    seller_id VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    first_seen_at DATETIME(6) NOT NULL,
    last_seen_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_product_platforms (platform, platform_product_id),
    KEY ix_product_platforms_product_id (product_id),
    KEY ix_product_platforms_last_seen_at (last_seen_at),
    CONSTRAINT fk_product_platforms_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE discovery_tasks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    keyword VARCHAR(256) NULL,
    platforms JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    started_at DATETIME(6) NULL,
    finished_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_discovery_tasks_workspace_id (workspace_id),
    KEY ix_discovery_tasks_status (status),
    CONSTRAINT fk_discovery_tasks_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE crawl_tasks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    discovery_task_id BIGINT UNSIGNED NULL,
    client_ref VARCHAR(128) NULL,
    platform VARCHAR(32) NOT NULL,
    task_type VARCHAR(64) NOT NULL DEFAULT 'snapshot',
    target_url TEXT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    total_count INT UNSIGNED NOT NULL DEFAULT 0,
    success_count INT UNSIGNED NOT NULL DEFAULT 0,
    failed_count INT UNSIGNED NOT NULL DEFAULT 0,
    started_at DATETIME(6) NULL,
    finished_at DATETIME(6) NULL,
    error_message TEXT NULL,
    client_id VARCHAR(128) NULL,
    crawler_version VARCHAR(64) NULL,
    data_version VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_crawl_tasks_workspace_client_ref (workspace_id, client_ref),
    KEY ix_crawl_tasks_workspace_id (workspace_id),
    KEY ix_crawl_tasks_discovery_task_id (discovery_task_id),
    KEY ix_crawl_tasks_status (status),
    CONSTRAINT fk_crawl_tasks_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_crawl_tasks_discovery FOREIGN KEY (discovery_task_id) REFERENCES discovery_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_platform_id BIGINT UNSIGNED NOT NULL,
    crawl_task_id BIGINT UNSIGNED NOT NULL,
    captured_at DATETIME(6) NOT NULL,
    title VARCHAR(512) NULL,
    subtitle VARCHAR(512) NULL,
    description TEXT NULL,
    brand VARCHAR(128) NULL,
    category VARCHAR(256) NULL,
    attributes_json JSON NULL,
    cover_url VARCHAR(1024) NULL,
    snapshot_hash CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_product_snapshots_hash (product_platform_id, snapshot_hash),
    KEY ix_product_snapshots_platform_id (product_platform_id),
    KEY ix_product_snapshots_crawl_task_id (crawl_task_id),
    KEY ix_product_snapshots_captured_at (captured_at),
    CONSTRAINT fk_product_snapshots_platform FOREIGN KEY (product_platform_id) REFERENCES product_platforms(id),
    CONSTRAINT fk_product_snapshots_crawl_task FOREIGN KEY (crawl_task_id) REFERENCES crawl_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE price_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    product_platform_id BIGINT UNSIGNED NOT NULL,
    currency VARCHAR(16) NOT NULL DEFAULT 'CNY',
    price DECIMAL(18, 4) NULL,
    original_price DECIMAL(18, 4) NULL,
    min_price DECIMAL(18, 4) NULL,
    max_price DECIMAL(18, 4) NULL,
    discount_amount DECIMAL(18, 4) NULL,
    coupon_amount DECIMAL(18, 4) NULL,
    shipping_fee DECIMAL(18, 4) NULL,
    price_text VARCHAR(512) NULL,
    captured_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_price_snapshots_snapshot_id (product_snapshot_id),
    KEY ix_price_snapshots_platform_id (product_platform_id),
    KEY ix_price_snapshots_captured_at (captured_at),
    CONSTRAINT fk_price_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id),
    CONSTRAINT fk_price_snapshots_platform FOREIGN KEY (product_platform_id) REFERENCES product_platforms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sales_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    product_platform_id BIGINT UNSIGNED NOT NULL,
    sales_count BIGINT NULL,
    sales_period VARCHAR(64) NULL,
    sales_text VARCHAR(256) NULL,
    review_count BIGINT NULL,
    rating DECIMAL(8, 4) NULL,
    favorite_count BIGINT NULL,
    want_count BIGINT NULL,
    view_count BIGINT NULL,
    captured_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_sales_snapshots_snapshot_id (product_snapshot_id),
    KEY ix_sales_snapshots_platform_id (product_platform_id),
    CONSTRAINT fk_sales_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id),
    CONSTRAINT fk_sales_snapshots_platform FOREIGN KEY (product_platform_id) REFERENCES product_platforms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sku_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    platform_sku_id VARCHAR(128) NULL,
    sku_name VARCHAR(512) NULL,
    attributes_json JSON NULL,
    price DECIMAL(18, 4) NULL,
    original_price DECIMAL(18, 4) NULL,
    stock BIGINT NULL,
    sku_data_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_sku_snapshots_snapshot_id (product_snapshot_id),
    CONSTRAINT fk_sku_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE seller_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    seller_id VARCHAR(128) NULL,
    shop_id VARCHAR(128) NULL,
    shop_name VARCHAR(256) NULL,
    seller_level VARCHAR(64) NULL,
    rating DECIMAL(8, 4) NULL,
    positive_rate DECIMAL(8, 4) NULL,
    follower_count BIGINT NULL,
    transaction_count BIGINT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_seller_snapshots_snapshot_id (product_snapshot_id),
    CONSTRAINT fk_seller_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE shipping_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    origin VARCHAR(256) NULL,
    destination VARCHAR(256) NULL,
    shipping_fee DECIMAL(18, 4) NULL,
    free_shipping TINYINT(1) NULL,
    delivery_time VARCHAR(128) NULL,
    fulfillment_type VARCHAR(64) NULL,
    shipping_data_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_shipping_snapshots_snapshot_id (product_snapshot_id),
    CONSTRAINT fk_shipping_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_media_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    media_type VARCHAR(32) NOT NULL,
    url TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    metadata_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_product_media_snapshots_snapshot_id (product_snapshot_id),
    CONSTRAINT fk_product_media_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE raw_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_snapshot_id BIGINT UNSIGNED NOT NULL,
    platform VARCHAR(32) NOT NULL,
    raw_data_json JSON NOT NULL,
    content_type VARCHAR(128) NULL,
    data_version VARCHAR(64) NULL,
    crawler_version VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_raw_snapshots_snapshot_id (product_snapshot_id),
    CONSTRAINT fk_raw_snapshots_snapshot FOREIGN KEY (product_snapshot_id) REFERENCES product_snapshots(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_watch (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    product_platform_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_product_watch (workspace_id, product_platform_id),
    KEY ix_product_watch_product_id (product_id),
    CONSTRAINT fk_product_watch_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_product_watch_product FOREIGN KEY (product_id) REFERENCES products(id),
    CONSTRAINT fk_product_watch_platform FOREIGN KEY (product_platform_id) REFERENCES product_platforms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_costs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    source_product_platform_id BIGINT UNSIGNED NOT NULL,
    purchase_price DECIMAL(18, 4) NULL,
    shipping_cost DECIMAL(18, 4) NULL,
    packaging_cost DECIMAL(18, 4) NULL,
    platform_fee DECIMAL(18, 4) NULL,
    payment_fee DECIMAL(18, 4) NULL,
    advertising_cost DECIMAL(18, 4) NULL,
    after_sales_cost DECIMAL(18, 4) NULL,
    tax_cost DECIMAL(18, 4) NULL,
    other_cost DECIMAL(18, 4) NULL,
    effective_from DATETIME(6) NULL,
    effective_to DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_product_costs_workspace_id (workspace_id),
    KEY ix_product_costs_product_id (product_id),
    CONSTRAINT fk_product_costs_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_product_costs_product FOREIGN KEY (product_id) REFERENCES products(id),
    CONSTRAINT fk_product_costs_platform FOREIGN KEY (source_product_platform_id) REFERENCES product_platforms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE profit_analysis (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    source_product_platform_id BIGINT UNSIGNED NOT NULL,
    target_product_platform_id BIGINT UNSIGNED NULL,
    source_price DECIMAL(18, 4) NULL,
    target_price DECIMAL(18, 4) NULL,
    purchase_cost DECIMAL(18, 4) NULL,
    shipping_cost DECIMAL(18, 4) NULL,
    platform_fee DECIMAL(18, 4) NULL,
    payment_fee DECIMAL(18, 4) NULL,
    advertising_cost DECIMAL(18, 4) NULL,
    after_sales_cost DECIMAL(18, 4) NULL,
    tax_cost DECIMAL(18, 4) NULL,
    other_cost DECIMAL(18, 4) NULL,
    estimated_profit DECIMAL(18, 4) NULL,
    profit_margin DECIMAL(8, 4) NULL,
    estimated_sales BIGINT NULL,
    estimated_revenue DECIMAL(18, 4) NULL,
    estimated_monthly_profit DECIMAL(18, 4) NULL,
    calculation_version VARCHAR(64) NOT NULL,
    calculated_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_profit_analysis_workspace_id (workspace_id),
    KEY ix_profit_analysis_product_id (product_id),
    CONSTRAINT fk_profit_analysis_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_profit_analysis_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE market_analysis (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    demand_score DECIMAL(8, 4) NULL,
    competition_score DECIMAL(8, 4) NULL,
    price_stability_score DECIMAL(8, 4) NULL,
    sales_growth_score DECIMAL(8, 4) NULL,
    estimated_monthly_sales BIGINT NULL,
    estimated_monthly_revenue DECIMAL(18, 4) NULL,
    calculation_version VARCHAR(64) NOT NULL,
    calculated_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_market_analysis_workspace_id (workspace_id),
    KEY ix_market_analysis_product_id (product_id),
    CONSTRAINT fk_market_analysis_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_market_analysis_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE opportunities (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    workspace_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    source_platform VARCHAR(32) NULL,
    target_platform VARCHAR(32) NULL,
    estimated_profit DECIMAL(18, 4) NULL,
    profit_margin DECIMAL(8, 4) NULL,
    estimated_monthly_profit DECIMAL(18, 4) NULL,
    demand_score DECIMAL(8, 4) NULL,
    competition_score DECIMAL(8, 4) NULL,
    stability_score DECIMAL(8, 4) NULL,
    opportunity_score DECIMAL(8, 4) NULL,
    reason_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    calculation_version VARCHAR(64) NOT NULL,
    calculated_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_opportunities_workspace_id (workspace_id),
    KEY ix_opportunities_product_id (product_id),
    KEY ix_opportunities_score (opportunity_score),
    CONSTRAINT fk_opportunities_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_opportunities_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
