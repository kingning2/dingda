# Multi-round policy

Three successful searches are the minimum, not the target.

## Distinct strategies

At least one round must use the source image. At least two text rounds must use
materially different queries.

Materially different means a different semantic axis:

- exact attributes
- alternate product name or use case
- supplier, material, or production method

Changing word order or punctuation is not a new round.

## Candidate accounting

- Count unique `item_id` values across all rounds.
- When the same item appears again, merge evidence; do not count it as new.
- If fewer than six comparable candidates remain after deduplication, add a
  fourth round aimed at the missing attribute.

## Stop condition

Do not produce a final recommendation until:

1. `scripts/validate_rounds.py` returns `ok=true`;
2. every surviving candidate is checked against the source card;
3. `dingda-offer-verification` has produced a verdict.

If search failures prevent three completed rounds, report the failed rounds and
stop with insufficient evidence.
