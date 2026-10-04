# Metrics definitions

Shown in UI and used by the aggregator:

| Metric | Definition |
|--------|------------|
| R(t) | Share of runs without system-level failure by horizon |
| MTBF | Operating time / failure count |
| MTTR | Corrective repair time / repair count |
| Ai | MTBF / (MTBF + MTTR) |
| Ao | MTBM / (MTBM + MDT) |
| MTBM | Mean time between all maintenance events (PM+CM) |
| MDT | Mean downtime incl. diagnosis, waits, repair, logistics |
| Production loss | ∫ (nominal − actual) over time |
| Production availability | delivered / nominal |

Confidence intervals: Wilson/Clopper-Pearson for proportions; bootstrap
or t-interval for means. Warm-up period excluded from metrics.
