# Evaluation and scale

> **Draft.** The headings are the ones the brief asks for in Part 3. Section 3 is drafted;
> sections 1 and 2 still have `TODO` lines. None may remain when this is sent.

## 1. Technical evaluation

- **Scorer output on the 10 public requests** (`make run`, 25 November 2026, model: `claude-haiku-5-5`):

  ```
  query   nDCG@5   P@5 leaks self dup     ms  notes
  Q01       0.56  1.00     0    0   0 2935.79  
  Q02       0.70  0.80     0    0   0 2038.1  
  Q03       1.00  1.00     0    0   0 1630.61  
  Q04       1.00  1.00     0    0   0 2343.71  
  Q05       1.00  1.00     0    0   0 2369.73  
  Q06       0.94  1.00     0    0   0 1891.5  
  Q07       0.91  1.00     0    0   0 2192.11  
  Q08       1.00  1.00     0    0   0 1339.71  
  Q09       0.81  1.00     0    0   0 1771.0  
  Q10       1.00  1.00     0    0   0 1351.92  
  ------------------------------------------------------------
  mean nDCG@5        0.893
  mean P@5           0.980
  access violations  0   <- must be 0 (security gate)
  self/own-org recs  0
  duplicates         0
  injection signals  0
  warm paths valid   17/17
  evidence grounded  149/149
  latency p50 / p95  1965 ms / 2936 ms
  SECURITY GATE: PASS
  ```

  The 10 requests cost $0.0048 in model calls in total. `results/run_stats.jsonl` says where each request's time and tokens went.

- **Our own baseline:** keyword search (BM25) on each record's text, behind the access filter. No model, no translation. Each rule added to it is measured alone. Output of `eval/score.py` on the 10 public requests, 25 November 2026 (`make baseline`):

  | Ranking, rules only | nDCG@5 | P@5 | Access violations | Security gate |
  |---|---|---|---|---|
  | Keyword search (the baseline) | 0.683 | 0.800 | 0 | PASS |
  | + taxonomy labels and synonyms, three languages | 0.857 | 0.960 | 0 | PASS |
  | + theme re-ranking alone | 0.744 | 0.860 | 0 | PASS |
  | + both | 0.893 | 0.980 | 0 | PASS |
  | + the two limits: no recent contact (90 days), a person suggested twice at most | 0.893 | 0.980 | 0 | PASS |
  | The system: all of the above, then evidence, warm paths and model-written explanations | 0.893 | 0.980 | 0 | PASS |
  | For comparison: theme tags searched as plain words | 0.855 | 0.960 | 0 | PASS |

  Selection by a model, measured against the rules (`make run` against `uv run matchmaker run --retrieval model`, same day, same model):

  | Who selects the five | nDCG@5 | P@5 | Access violations | Median latency | Slowest | Model cost, 10 requests |
  |---|---|---|---|---|---|---|
  | Rules (the system above) | 0.893 | 0.980 | 0 | 2.0 s | 2.9 s | $0.0048 |
  | A model shown the table of records the user may be offered | 0.929 | 0.960 | 0 | 2.6 s | 3.6 s | $0.0126 |

  Per request, the model's selection is better on Q01, Q02, Q06 and Q09, worse on Q04 and Q07, and equal on the other four. An earlier run, before the two limits were added, gave 0.906: the model's choice is not reproducible from one run to the next.

  The two limits on who is suggested, measured alone and together (no model, same day):

  | No one met in the last | A person is suggested at most | nDCG@5 | P@5 |
  |---|---|---|---|
  | off | off | 0.893 | 0.980 |
  | 90 days | off | 0.893 | 0.980 |
  | 180 days | off | 0.873 | 0.980 |
  | off | twice | 0.876 | 0.955 |
  | 90 days | twice (the system) | 0.893 | 0.980 |
  | 90 days | once | 0.816 | 0.860 |

  With the system's values the score does not move, but the answers do: on Q01 a member is no longer offered a board peer they met on 15 October 2026. At 180 days Q04 falls from 1.00 to 0.80, because the labels count people the requester met in June as good answers (Q-01 in `ASSUMPTIONS.md`). A stricter limit costs score on these labels; the values are set with the relationship managers, not tuned on 10 requests.

  In every row, hidden text is removed from the records, duplicate person records are merged, and organisations, which have no descriptive text, are searched by their theme tags. The system's row has the same ranking as the row above it: the model only writes the explanations.

- **What each component adds over it:** `TODO`
- **The two failure cases that worry us most:** `TODO`
- **Measuring answer quality in production, where there are no labels:** `TODO`

## 2. Business value measurement

- **Activity, separated from outcomes:** `TODO`
- **How a renewal or an upgrade is attributed to better matchmaking:** `TODO`
- **What we would not claim:** `TODO`

## 3. Scale plan (one page)

> **Draft, to confirm.** The measured figures come from the prototype. The phases follow the
> roll-out in the business memo. The diagrams are in [`architecture.md`](architecture.md).

The prototype reads 87 records from files, selects in about 3 ms and spends about 2 seconds
on one model call per request. From there to production:

- **Data pipeline from the CRM and events.** A sync copies records, relationships and access
  fields into one store on every change. Hidden text is removed and reported to a person,
  as today. The pipeline does not repair data: doubtful fields go back to the relationship
  managers.
- **Keeping access rights in sync.** Rights are read from the store on every request, never
  copied into a prompt or a cache. A record whose rights could not be refreshed is treated
  as restricted. The acceptable delay is to be set with Engineering.
- **Indexing and caching for the Summit peak.** A search index with the access filter inside
  the query returns ranked results in milliseconds, with no model. Explanations are the
  bottleneck at 3,000 simultaneous requests: they are cached per record and clearance
  level, and written by rule when the model is late.
- **Cost per request.** Measured: $0.0005 with keyword selection, $0.0013 with selection by
  a model, so $1.50 and $3.80 for 3,000 requests. Every request reports its tokens and cost.
- **CI/CD for prompts and models, with evaluation as a release gate.** Today: prompts
  versioned with the code, 241 offline tests on every push, no real model call in CI. To
  add: a labelled set run with real calls on every change of prompt, model or rule. One
  access violation, or a relevance drop beyond an agreed margin, blocks the release.
- **Monitoring for relevance drift and leaks.** Leaks: every answer is checked in code, and
  planted records that no user may see raise an alert if one appears. Drift: the weekly
  share of suggestions approved, of requests with no result and of fallbacks.
- **Human review before an introduction is sent.** A relationship manager approves every
  suggestion. Each approval or rejection is recorded with its reason. That record becomes
  the labelled set, and the evidence for handing simple cases over.
- **Swiss data protection (nFADP) for member data.** Profiles and notes on named people are
  personal data, processed abroad by the model provider. Before the pilot: a processing
  agreement (Art. 9), transfer safeguards (Art. 16) and an impact assessment (Art. 22). The
  model receives only records this user may see, and a person decides every introduction
  (Art. 21). To be validated by the Forum's data protection adviser.

### Roadmap in three phases

| Phase | What it does | What it must prove |
|---|---|---|
| 1. Pilot, 90 days | A few relationship managers, live CRM data read-only, every suggestion reviewed. | Zero leaks. A good answer within a day, not 3 to 5. An approval rate agreed beforehand. |
| 2. All relationship managers | Sync, access rights and release gate in production. Simple cases defined from the recorded reviews. | Rights changes take effect within the agreed delay. Data upkeep at a workload the managers accept. |
| 3. Self-service for simple cases | Members, then Summit participants. Ambiguous cases stay with a manager. | 3,000 simultaneous requests under 4 seconds. Zero leaks under adversarial tests. Quality holds without review. |
