# Evaluation and scale

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

- **The two failure cases that worry us most:**

  1. **Data that is not kept up to date.** The tool is not responsible for data quality, and should not be. It applies what the data says. If a relationship manager does not update a relationship, an access right, an opt-out or a pause, the tool applies the old value, correctly and with confidence. No test on our side catches that: the control sits in the managers' process, not in the code.
  2. **A weak match that reads well.** The tool returns whatever shares words or a theme with the request, with a fluent explanation, and it has no threshold below which a weak match is held back. Matching rests on shared words and on a taxonomy kept by hand, so a request outside both gets plausible suggestions that are wrong, and nothing signals it. We measured on 10 requests that rules handle well, so we do not know how often this happens. During the MVP the manager's review catches it. In self-service nothing would.

- **Measuring answer quality in production, where there are no labels:**

  - **Traces.** Every request is traced step by step, to a file and to the Phoenix viewer: what was called, in what order, how long it took and what it cost. This allows offline analysis of what fails, where and why.
  - **The managers' decisions.** Each approval or rejection, with its reason, is a label. Quality without labels only becomes a question in self-service, and by then the MVP phase has produced that feedback.

## 2. Business value measurement

- **Activity, separated from outcomes.** Activity is what the tool can count: requests, suggestions, approvals, time to an answer. The outcome is whether the two members connected, and whether the member judged the connection valuable. Today's data records neither: the extract holds no trace of introductions made, or of what came of them.
- **How a renewal or an upgrade is attributed to better matchmaking.** Not with today's data model. Part of what matters lives in emails and documents, not in fields: a pause, two people who must not be paired. Attribution needs a canonical set of data, kept up to date, where every action or piece of information that a relationship manager should know about a member is logged: introductions proposed, made and followed up, and their outcome. Helping managers log this with little friction is probably a separate product. It could sit in the same tool, but it is a different algorithm from the matchmaking proposed here.
- **What we would not claim:**
  - That an introduction caused a renewal. At best, members who received introductions they valued renew more often.
  - That a score on 10 labelled requests measures value for members. The labels count people a member already knows as good answers (Q-01 in `ASSUMPTIONS.md`).
  - That the tool measures the quality of a connection. Only the member and the manager can.

## 3. Scale plan (one page)

We do not draw a production architecture here. That choice has to be made on the full data, not on an extract of 87 records. What we can state is what scales as built, what does not, and what follows.

**What scales as built: the guardrails around retrieval and around the model.** Access rights applied in code before any search, the two limits on who is suggested, the Secretariat's rules, the check of every answer, the fallback when the model is late, and the trace of every step. They take a few milliseconds per request and do not depend on how the matching is done.

**What does not scale:**

- **The relationships file.** It grows faster than the number of participants and organisations: 229 relationships for 50 people here. The prototype reads it whole on every request, which will not hold.
- **Matching by a model that reads everything.** The model reads about 110 tokens per record. At 5,000 profiles that is about 550,000 tokens per request. Cost and latency rise with the network, and a model given that much context becomes less reliable (context rot).
- **The taxonomy and the languages.** Matching across English, French and Spanish rests on 12 themes and their synonyms, kept by hand. That upkeep does not survive the full data.

**The likely direction** is retrieval over an index (a RAG approach), with the access filter applied inside the search. Which index, and whether it holds at a Summit peak of 3,000 simultaneous requests, is decided on data: measured on the full network, with the scorer and the managers' feedback as the gate.

**The points the brief asks for:**

- **Data pipeline and access rights in sync.** The tool reads what the systems of record say and repairs nothing. Rights are read at request time and never copied into a prompt. A record whose rights cannot be read is treated as restricted.
- **Indexing and caching for the Summit peak.** An index chosen on data, as above. Ranked results need no model. The explanation is the slow part, and is written by rule when the model is late.
- **Cost per request.** Measured: $0.0005 with keyword selection, $0.0013 with selection by a model.
- **CI/CD for prompts and models, with evaluation as a release gate.** Today: prompts versioned with the code, 241 offline tests on every push, no real model call in CI. To add: the labelled requests produced by the managers' reviews, run on every change of prompt, model or rule. One access violation blocks the release.
- **Monitoring for relevance drift and leaks.** Every answer is checked in code before it leaves. Traces show what failed and where. The managers' approval rate shows drift.
- **Human review before an introduction is sent.** In the MVP a relationship manager approves every suggestion. Self-service opens only when the evidence described in the business memo exists.
- **Swiss data protection (nFADP).** Profiles and notes on named people are personal data, processed abroad by the model provider. A processing agreement (Art. 9), transfer safeguards (Art. 16) and an impact assessment (Art. 22) come before the pilot. To be validated by the Forum's data protection adviser.
