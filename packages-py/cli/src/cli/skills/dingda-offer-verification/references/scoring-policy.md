# Offer scoring policy

## Hard gates

Reject a candidate when:

- any source hard constraint is explicitly mismatched;
- the title or product identity is missing;
- the listed price represents a different SKU, quantity, or MOQ and cannot be
  normalized;
- the image is demonstrably a copy of the source image rather than a supplier
  product image.

## Price normalization

Use:

```text
unit_landed_price = (listed_price + confirmed_shipping + required_bundle_cost)
                    / quantity_included
```

If shipping, SKU, or quantity is unknown, keep the candidate `conditional`.

## Merchant evidence

At least one of these must be known before a candidate can be `accept`:

- merchant rating
- repurchase rate
- sold count

Missing values are `unknown`, never favorable defaults.

## Ranking

Order surviving candidates by:

1. hard-constraint match;
2. unit landed price;
3. merchant evidence;
4. stock and MOQ risk.

The cheapest sticker price is not automatically the winner.
