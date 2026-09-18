# Reconciliation disposition

Compare `monthly_reconciliation` from `01_all_store_pipeline.sql` with this
expected disposition before sending discrepancies to Finance.

| Month | Expected difference | Classification | Action |
|---|---:|---|---|
| 2024-01, 02, 04, 05, 06, 08, 09, 10, 11 | 0.00 | None | No escalation |
| 2024-03 | 486,250.00 | Revenue-definition/scope difference | Take to Finance: finance includes an institutional invoice outside till exports. |
| 2024-07 | 232,131.70 | Source-data gap | Take to Finance: S07 files for Jul 9–11 do not exist; Finance has phone-in totals. |
| 2024-12 | small rounding variance | Revenue-definition difference | Take to Finance: Finance rounds each bill to rupees; pipeline sums paise. |

Any other variance is a pipeline bug until investigated. The primary checks are
business date from filename, deduplication by `(bill_no,line_no)`, full-bill
void exclusion, effective-dated product matching, and effective-dated price
matching.
