# Evaluation and scale

> **Placeholder.** This is written once the build is finished. The headings are the ones the
> brief asks for in Part 3. None of the `TODO` lines may remain when this is sent.

## 1. Technical evaluation

- **Scorer output on the 10 public requests** (`make run`, 25 November 2026, model: `claude-haiku-5-5`):

  ```
  query   nDCG@5   P@5 leaks self dup     ms  notes
  Q01       0.56  1.00     0    0   0 2334.14  
  Q02       0.70  0.80     0    0   0 2304.31  
  Q03       1.00  1.00     0    0   0 1730.16  
  Q04       1.00  1.00     0    0   0 2424.98  
  Q05       1.00  1.00     0    0   0 2914.51  
  Q06       0.94  1.00     0    0   0 1754.69  
  Q07       0.91  1.00     0    0   0 1964.43  
  Q08       1.00  1.00     0    0   0 1180.9  
  Q09       0.81  1.00     0    0   0 1975.14  
  Q10       1.00  1.00     0    0   0 1638.93  
  ------------------------------------------------------------
  mean nDCG@5        0.893
  mean P@5           0.980
  access violations  0   <- must be 0 (security gate)
  self/own-org recs  0
  duplicates         0
  injection signals  0
  warm paths valid   18/18
  evidence grounded  153/153
  latency p50 / p95  1970 ms / 2915 ms
  SECURITY GATE: PASS
  ```

  The 10 requests cost $0.0050 in model calls in total. `results/run_stats.jsonl` says where each request's time and tokens went.

- **Our own baseline:** keyword search (BM25) on each record's text, behind the access filter. No model, no translation. Each rule added to it is measured alone. Output of `eval/score.py` on the 10 public requests, 25 November 2026 (`make baseline`):

  | Ranking, rules only | nDCG@5 | P@5 | Access violations | Security gate |
  |---|---|---|---|---|
  | Keyword search (the baseline) | 0.683 | 0.800 | 0 | PASS |
  | + taxonomy labels and synonyms, three languages | 0.857 | 0.960 | 0 | PASS |
  | + theme re-ranking alone | 0.744 | 0.860 | 0 | PASS |
  | + both | 0.893 | 0.980 | 0 | PASS |
  | The system: both rules, then evidence, warm paths and model-written explanations | 0.893 | 0.980 | 0 | PASS |
  | For comparison: theme tags searched as plain words | 0.855 | 0.960 | 0 | PASS |

  In every row, hidden text is removed from the records, duplicate person records are merged, and organisations, which have no descriptive text, are searched by their theme tags. The system's row has the same ranking as the row above it: the model only writes the explanations.

- **What each component adds over it:** `TODO`
- **The two failure cases that worry us most:** `TODO`
- **Measuring answer quality in production, where there are no labels:** `TODO`

## 2. Business value measurement

- **Activity, separated from outcomes:** `TODO`
- **How a renewal or an upgrade is attributed to better matchmaking:** `TODO`
- **What we would not claim:** `TODO`

## 3. Scale plan (one page)

From this prototype to production:

- **Data pipeline from the CRM and events:** `TODO`
- **Keeping access rights in sync:** `TODO`
- **Indexing and caching for the Summit peak:** `TODO`
- **Cost per request:** `TODO`
- **CI/CD for prompts and models, with evaluation as a release gate:** `TODO`
- **Monitoring for relevance drift and leaks:** `TODO`
- **Human review before an introduction is sent:** `TODO`
- **Swiss data protection (nFADP) for member data:** `TODO`

### Roadmap in three phases

| Phase | What it does | What it must prove |
|---|---|---|
| 1 | `TODO` | `TODO` |
| 2 | `TODO` | `TODO` |
| 3 | `TODO` | `TODO` |
