# SetuBid deduplication: measured, durable design

## Decision

Use exact signal-token Jaccard **≥ 0.88** for merging, after 16×4 MinHash LSH retrieval with bucket cap 60. A false merge is explicitly priced at **25:1** compared with leaving a duplicate card. On the 900 adjudications this selects the threshold with 0 false merges and 180 missed same pairs (labels are case-control sampled, so these are conditional counts). The resulting store has 11,991 durable opportunity cards.

## 1. Mechanical similarity

`T(n)` is the full set of lowercase alphabetic terms in title+body after removing portal boilerplate, reference numbers, dates, money and generic tender terms. Score is `J(a,b)=|T(a)∩T(b)|/|T(a)∪T(b)|`; this full stored set is always used for the final merge. These exclusions follow the corpus notes: each portal invents references and formats dates/money differently, while P001–P006 paste a 1,400-character preamble. For fast candidate retrieval the sketch takes the 24 least-common signal terms, but it never substitutes for final scoring. Representative same `N002919/N002920`: raw 1.000, signal 1.000; hardest different `N008784/N011076`: raw 0.869, signal 0.875.

## 2. Deliberate reduced form

Each notice stores **64 deterministic 64-bit MinHash values = 512 bytes**, or 5.9 MiB for 12,000 notices. At J=0.70, `SE=sqrt(.7*.3/64)=0.057` (95% about ±0.112), appropriate because MinHash is only a retrieval filter while exact Jaccard remains the conservative merge authority. Labelled realised error: MAE 0.028, RMSE 0.042, maximum 0.172.

## 3. Sublinear candidate retrieval and risk

The LSH survival function is `1-(1-s^4)^16`; at 0.70 it is 0.9876. Candidate retrieval is the union of that LSH path and a bounded inverted-token fallback (up to 12 terms whose document frequency is at most 200), which protects wording variants that MinHash misses. The empirical survival curve is [retrieval_curve.svg](retrieval_curve.svg). Bucket-cap comparison:

| cap | same-pair recall | different pass rate | mean candidates |
|---:|---:|---:|---:|
| none | 1.000 | 0.079 | 370.0 |
| 80 | 1.000 | 0.037 | 231.0 |
| 120 | 1.000 | 0.039 | 251.0 |
| 60 | 1.000 | 0.034 | 217.0 |
| 250 | 1.000 | 0.050 | 290.8 |

Cap 60 is the operating point: it controls the LSH tail; the bounded token fallback supplies recall. Exact scoring and the 25:1 threshold protect against the higher-cost error.

## 4. Relational home and lookup evidence

`dedup.sqlite` persists `notice`, `lsh_bucket(band,bucket,notice_id)`, `bucket_stat`, `opportunity`, and `opportunity_member`. The B-tree `ix_lsh_lookup` seeks 16 `(band,bucket)` keys, unlike the rejected scan. Planner: `MULTI-INDEX OR; INDEX 1; SEARCH b USING COVERING INDEX ix_lsh_lookup (band=? AND bucket=?)`. Representative lookup: 98 output rows, 530 posting rows examined, indexed 0.603 ms; forced `NOT INDEXED` scan 27.625 ms.

## 5. Skew, mitigation, and stable IDs

Before/after cap fan-out mean is 200.3/217.0, p95 804/347. `P006` is heaviest (mean 553.5, p95 1014); repeated aggregation text makes equal minima and huge LSH posting lists. Suppressing buckets above 60 migrates that tail; its measured quality price is the cap=60 same-pair recall above. The full build took 52.0s (231.0 notices/s); 4,000 new weekly notices project to 17.3s, below 20 minutes.

Cards are persistent: `opportunity_member` maps notices to bookmarkable `card_id`s. Later copies join an existing card; if cards connect, the earlier `created_seq` card survives and only memberships migrate. Therefore existing bookmarks remain valid over reruns.
