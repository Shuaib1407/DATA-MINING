# SetuBid tender deduplication

This folder contains a reproducible prototype for turning repeated tender notices into stable, bookmarkable opportunity cards. It implements the SetuBid brief: conservative similarity, compact approximation, sublinear retrieval, persistent indexing, query measurements, and mitigation of portal skew.

## Contents

| Path | Purpose |
|---|---|
| `notices/part-*.csv` | 12,000 tender notices from 260 portals |
| `labelled_pairs.csv` | 900 human-adjudicated same/different pairs |
| `portal_profiles.md` | Context on portal formats and nodal boilerplate |
| `dedup_analysis.py` | Reproducible pipeline and measurement script |
| `dedup.sqlite` | Persistent notices, index, cards, and memberships |
| `dedup_report.md` | Detailed measured design report |
| `dedup_summary.json` | Machine-readable latest-run summary |
| `retrieval_curve.svg` | Candidate-survival plot |

## Run

The program uses only the Python standard library. Run it from the parent workspace:

```powershell
py -3.13 data_2\dedup_analysis.py
```

It reads the notice CSV files, refreshes the derived LSH access path, merges qualifying cards, and updates the report, summary, and plot. It does not delete the opportunity or membership tables, so card mappings survive reruns.

## Similarity and merge decision

Final scoring is exact Jaccard similarity over cleaned title and body tokens:

```text
J(a, b) = |tokens(a) intersection tokens(b)| / |tokens(a) union tokens(b)|
```

Cleaning lowercases text and removes known portal boilerplate, reference numbers, monetary expressions, dates, and broad tender-generic terms. Portal notes show that the removed fields change when one tender is republished; project, location, material, and agency terms are retained.

The merge threshold is selected from `labelled_pairs.csv` using an explicit **25:1 false-merge cost**. This encodes the product requirement: merging two different opportunities is much worse than showing a duplicate. The chosen threshold and labelled error counts are recorded in `dedup_report.md`.

## Compact signatures and candidate retrieval

Each notice stores a deterministic 64-value, 64-bit MinHash signature: **512 bytes per notice**, or about 5.9 MiB for the corpus. The signature is arranged into **16 bands x 4 rows**. At similarity 0.70, LSH survival is:

```text
1 - (1 - 0.70^4)^16 = 0.9876
```

Candidate generation is a union of two bounded paths:

- LSH buckets, with buckets larger than 60 postings suppressed.
- An inverted-token fallback using up to 12 informative terms with document frequency at most 200.

The fallback protects recall when legitimate copies vary enough that they do not share an LSH band. Every candidate is re-scored with exact Jaccard before a card merge. `retrieval_curve.svg` and the table in `dedup_report.md` give the measured survival, pass-rate, and fan-out results.

## Database design

`dedup.sqlite` persists these relational structures:

| Table | Role |
|---|---|
| `notice` | Source ID, portal metadata, cleaned tokens, MinHash signature |
| `lsh_bucket` | `(band, bucket, notice_id)` retrieval postings |
| `bucket_stat` | LSH posting-list sizes for cap enforcement |
| `opportunity` | Bookmarkable `card_id`, canonical notice, creation order |
| `opportunity_member` | Every notice's current opportunity card |

The B-tree `ix_lsh_lookup` seeks specific `(band, bucket)` posting lists rather than scanning the corpus. The report includes the SQLite query plan, postings examined, indexed timing, and a forced `NOT INDEXED` comparison.

## Stable bookmark IDs

A notice receives a card only if it is not already a member. When a new match connects two cards, the card with the earliest `created_seq` survives and the other card's memberships migrate to it. Thus an existing bookmarked ID stays valid while later copies are absorbed. Only the derived LSH tables are refreshed on a run; card and membership records are retained.

## Portal skew and mitigation

P001-P006 are nodal republishers with a repeated legal preamble. Repeated text produces large LSH buckets and a disproportionate candidate-comparison tail. The pipeline measures fan-out by portal, caps oversized LSH buckets, and reports the quality/cost effect. The bounded token fallback supplies recall after that cap.

`dedup_report.md` contains the measured fan-out distribution, heaviest portal, database benchmark, MinHash error, retrieval curve, and runtime projection for 4,000 new notices against the 20-minute nightly budget.

## Latest result

Open `dedup_summary.json` for the compact current values: notices processed, cards created, selected threshold, signature size, and indexed lookup latency. For the full explanation and evidence, read `dedup_report.md`.
