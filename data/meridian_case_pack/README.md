# Meridian Forum — Matchmaking case data pack

All people, organisations, initiatives and notes in this pack are fictional. Any resemblance to real people is coincidental.

The Meridian Forum is an international membership institution based in Geneva. Its value to members is access to the right peers. This pack is a small, realistic slice of its network knowledge, built for a 3-hour agentic matchmaking build.

## Contents

| Path | What it is | Count |
|---|---|---|
| `people/P-xxx.md` | Person profiles: YAML-style front matter + free-text bio (EN, FR or ES) | 50 |
| `organizations.json` | Member organisations | 25 |
| `initiatives/I-xx.md` | Multi-stakeholder initiatives and coalitions | 12 |
| `notes/N-xx.md` | Session summaries and account notes (Chatham House) | 9 |
| `documents/` | A PDF report, a draft PDF memo and Word meeting minutes; classification is stated inside each file | 3 |
| `inbox/` | Emails (.eml) to and from the Secretariat; classification in the `X-Meridian-Classification` header | 3 |
| `relationships.csv` | Relationship graph edges between people | 229 |
| `taxonomy.json` | 12 themes with EN/FR/ES labels and synonyms | 12 |
| `users.json` | The 5 users who send requests, with their clearance | 5 |
| `ACCESS_POLICY.md` | The rules your system must enforce | 1 |
| `eval/queries_public.jsonl` | 10 test requests with graded relevance labels | 10 |
| `eval/score.py` | Scorer (standard-library Python 3) | 1 |
| `eval/sample_results.jsonl` | Example of the expected output format | 1 |

## Key fields

- `visibility` on every record and edge: `public` < `members` < `staff` < `restricted`.
- `opt_out_matchmaking` on people: the person must not be suggested to members or guests.
- `themes` use the ids in `taxonomy.json`. Bios are written in the person's working language.
- `relationships.csv`: `source`, `target`, `type` (colleague, worked_with, board_peer, co_member_initiative, co_attended_session, introduced_by_staff, staff_account_contact, negotiation), `strength` 1–5, `last_interaction`, `visibility`, `evidence_doc`, `note`.

The data is deliberately imperfect, like real CRM data. Expect duplicates, stale records, mixed languages and formats, and content you should not trust. Some rules the Secretariat relies on live only in documents and emails, not in the structured fields.

## Output format

Write one JSON line per query:

```json
{"query_id": "Q01", "latency_ms": 910,
 "results": [{"id": "P-004", "rank": 1,
              "explanation": "Why this match, in one or two sentences",
              "evidence": ["P-004", "N-01", "I-01"],
              "warm_path": ["P-005", "P-004"]}]}
```

- `id`: a person (P-), organisation (O-) or initiative (I-). At most 5 results.
- `evidence`: ids of the records that support the explanation (P-, O-, I-, N-, E- edge ids, D- documents or M- emails).
- `warm_path` (people only, optional): a chain of person ids from the requester to the target, each step an edge in `relationships.csv`. For member users it starts with their own `person_id`.
- `latency_ms`: end-to-end time for that request on your machine.
- Returning no results is a valid answer when nothing visible fits.

## Scoring

```
python eval/score.py --results my_results.jsonl
```

It reports nDCG@5, Precision@5, access violations, self/own-org recommendations, duplicates, a prompt-injection signal, warm-path validity, evidence grounding and latency. **Any access violation fails the security gate, whatever the relevance score.** We will run the same scorer on 10 hidden requests during the debrief.
