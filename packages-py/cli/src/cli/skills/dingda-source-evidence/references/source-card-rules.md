# Source card rules

## Required for comparison

- `platform`
- `item_id` or `url`
- `title`
- `image_url`

If one of these is missing, comparison must stop until the source is resolved.

## Hard constraints

Only include attributes that can change whether the offer is the same product:

- brand and model
- dimensions, capacity, weight limit
- material
- quantity or bundle contents
- required accessories
- new/used condition and visible defects

Color, listing location, and generic marketing words are normally soft preferences.

## Price basis

Keep the source price separate from normalized unit price.

- `quantity_included`: number of sellable units represented by the price
- `condition`: `new`, `used`, or `unknown`
- `shipping`: `included`, `extra`, or `unknown`
- `bundle`: exact bundle description or `unknown`

Never infer shipping or bundle contents from the title alone.
