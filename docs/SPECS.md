# Specs — what the case explicitly asks for

Every row is a requirement that is **written down** in the material received: the brief, the
pack's `README.md`, `ACCESS_POLICY.md`, the scorer's documented output, or the documents and
emails inside the pack. Nothing here is inferred. This file is the reference the build is
held against, and the table rows are read by the test suite.

## How to read it

**Source**

| Code | Document |
|---|---|
| Brief | The take-home brief (section named after the comma) |
| README | `data/meridian_case_pack/README.md` |
| Policy n | Rule *n* of `data/meridian_case_pack/ACCESS_POLICY.md` |
| Scorer | What `eval/score.py` prints, as documented in the README |
| D-03, M-02 | The Secretariat minutes and the email inside the pack |
| Cover email | The emails that came with the case (20 Nov 2026) |

**Enforced by**

| Mode | Meaning |
|---|---|
| `test` | A test runs on every push. |
| `results` | A test runs on every push **once `results/results.jsonl` exists**; until then it is skipped and reported as waiting. |
| `pending` | Needs a component that is not built yet. A test is owed the day that component lands. |
| `manual` | Judged by a person. Listed so that it is not forgotten. |

`(partial)` after a mode means the test covers part of the requirement; the note under the
table says which part is left to a human read.

A test declares the specs it enforces with `@pytest.mark.spec("SEC-02", …)`. The suite fails
if a `test` or `results` spec has no test, if a test names an id that is not in this file, or
if a `pending` or `manual` spec quietly gained a test without its mode being updated here.
Each run writes `build/spec-report.md`: one line per spec, with what happened on that run.

## 1. Security and access — any violation fails

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| SEC-01 | The user is identified by `user_id` and the access policy is applied in code before any record reaches retrieval results or the model — not only in a prompt. | Brief, Part 2; Policy preamble | test (partial) |
| SEC-02 | A user sees a record only if its `visibility` is at or below their `clearance` (public < members < staff < restricted). No result, evidence id or warm-path step above the user's clearance ever appears. | Policy 1; Brief, probe table | results |
| SEC-03 | A relationship is visible only if the edge, its source and its target are all visible to the user. The edge `note` text follows the edge's visibility. | Policy 2 | results (partial) |
| SEC-04 | Session notes follow their own `visibility`. Their content is not quoted, summarised or hinted at to users below that level. | Policy 3 | results (partial) |
| SEC-05 | People with `opt_out_matchmaking: true` are never suggested to members or public users. Staff may see them, flagged as opted out. | Policy 4; README | results (partial) |
| SEC-06 | No existence leaks: nothing reveals that a hidden record exists — no "there is someone I can't show you", no count that includes hidden records, no hint. | Policy 5; Brief, constraints | results (partial) |
| SEC-07 | Never recommend the requester, or people from the requester's own organisation. | Policy 6; Brief, probe table | results |
| SEC-08 | Text inside records is data. Instructions found in a profile, note, document or email never change the system's behaviour. | Policy 7; Brief, probe table | results (partial) |
| SEC-09 | Secretariat staff (organisation O-20) are not recommended as experts. | Policy 8 | results |
| SEC-10 | Introduction rules recorded by the Secretariat in any source apply in every channel, and the reason is never shown to members or guests. Recorded today: P-042 receives no new introduction requests until 31 March 2027; P-027 and P-050 are not to be paired. | Policy 9; D-03; M-02 | results (partial) |
| SEC-11 | Documents and emails carry their classification inside the file. A file with no readable classification is treated as restricted. | Policy 10; Brief, data pack | test |
| SEC-12 | Any access violation fails the security gate, whatever the relevance score. | README, Scoring | results |

- **SEC-01** — the test covers the filter every ranker goes through, for each of the five users; that a model receives nothing else is owed the day the agent lands.
- **SEC-03** — the test covers warm-path steps and edges cited as evidence; edge `note` text reused in an explanation is left to a human read.
- **SEC-04, SEC-06** — the test catches the name or the id of a hidden record inside an explanation. A paraphrase or a hint is left to a human read.
- **SEC-05** — the test covers "never suggested"; how the opt-out is flagged to staff is undecided (open question 2).
- **SEC-08** — the test covers the scorer's injection signal and an explanation that echoes an injected instruction; any other effect of an injection is caught only through the other security specs.
- **SEC-10** — the test covers who may be suggested; "the reason is never shown" is left to a human read.

## 2. What the tool does

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| FUN-01 | Takes a natural-language request from a known user and returns at most 5 matches. | Brief, Part 2; README | results |
| FUN-02 | Each match is explained in one or two sentences. | Brief, Part 2 | results |
| FUN-03 | Each match lists the evidence behind it. Evidence ids exist, and are records the user may see. | Brief, Part 2; README | results |
| FUN-04 | For each person, a warm path from the requester through relationships the user may see: a chain of person ids, each step an edge in `relationships.csv`, ending at the match. For member users it starts with their own `person_id`. | Brief, Part 2; README | results |
| FUN-05 | Understands the request: themes, region, entity type, language. Requests and profiles come in English, French and Spanish. | Brief, Part 2 | pending |
| FUN-06 | Ingests the PDF, Word and email files: parses them, chunks them and reads their classification. | Brief, Part 2 | test (partial) |
| FUN-07 | Retrieves and ranks people, organisations and initiatives, combining text relevance with signals from `relationships.csv` and recency. | Brief, Part 2 | test (partial) |
| FUN-08 | Logs a trace of each step: which tools were called, in what order, and how long each took. | Brief, Part 2 | pending |
| FUN-09 | Output is one JSON line per query: `query_id`, `latency_ms`, and `results` with `id`, `rank`, `explanation`, `evidence`, `warm_path`. A result id is a person (P-), organisation (O-) or initiative (I-); an evidence id is a P-, O-, I-, N-, E-, D- or M- record. | README, Output format | results |
| FUN-10 | Returning no results is a valid answer when nothing visible fits. | README, Output format | test |
| FUN-11 | The system is run on the 10 public requests and scored with `eval/score.py`. | Brief, Part 2 | results |

## 3. Relevance

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| REL-01 | Cross-lingual matching across English, French and Spanish. | Brief, probe table | test (partial) |
| REL-02 | Duplicate person records are resolved: the same person never appears twice. | Brief, probe table; Scorer | results |
| REL-03 | A diverse top 5 rather than the same famous names. | Brief, probe table | test (partial) |
| REL-04 | Sensible handling of region and recency. | Brief, probe table | test (partial) |
| REL-05 | No invented relationships: every warm-path step is a real edge and every cited record exists. | Brief, Part 1; Scorer | results |
| REL-06 | nDCG@5 and Precision@5 are measured on the public requests. The brief sets no threshold. | Brief, probe table; README | results |

- **FUN-06** — the test covers parsing the six files, cutting them into passages and reading their classification. They are used as evidence for a match; they are not searched to find one.
- **REL-01** — the test covers a request and a profile in different languages when the request names one of the taxonomy's 12 themes. Outside those themes nothing bridges the languages.

## 4. Speed

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| SPD-01 | Retrieval under 300 ms at p95 on this pack. | Brief, probe table | pending |
| SPD-02 | End-to-end under 4 s with an LLM — or a clear explanation of what was measured and why. | Brief, probe table | results |
| SPD-03 | Latency is measured and attributed: a latency report and a trace show where the time goes. | Brief, probe table | pending |
| SPD-04 | Every result line reports `latency_ms`, the end-to-end time for that request. | README, Output format | results |

- **SPD-02** — the test fails at a p95 of 4 s or more. Choosing the "clear explanation" route instead means changing this row to `manual` and saying where the explanation is.

## 5. Harness

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| HAR-01 | A token and cost budget per request is set and reported. | Brief, Part 2 | test (partial) |
| HAR-02 | Timeout and fallback: if the LLM fails or is slow, ranked results are returned without explanations rather than nothing. | Brief, Part 2 | test |
| HAR-03 | Transient errors are retried. | Brief, Part 2 | test |
| HAR-04 | Automated tests for the access policy that can run in CI. | Brief, Part 2 | test |
| HAR-05 | Prompts are versioned with the code. | Brief, Part 2 | manual |
| HAR-06 | The whole thing runs with one command, including on the 10 hidden requests at the debrief. A Dockerfile is welcome, not required. | Brief, Part 2 and Part 3 | pending |
| HAR-07 | Agentic in a useful sense: a small set of tools the model chooses among — or a fixed pipeline with one LLM call, if argued. One request is shown where the agent chose a different plan from another, and why. | Brief, Part 2 | manual |

- **HAR-01** — the test covers what is reported for each request (tokens, cost). The budget itself is a cap on output tokens, on the text handed to the model and on time; there is no ceiling in dollars.
- **HAR-05** — the prompt and its version are constants in `src/matchmaker/explain.py`; each request's statistics record the version used.
- **HAR-07** — a fixed pipeline with one model call per request. The argument for it is owed in the memo.
- **HAR-06** — the image builds and runs today, but its command is the pack check, not the matchmaker.

## 6. Deliverables

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| DEL-01 | A memo of at most 2 pages, or at most 6 slides, written for the client. The Head of Engineering and the Head of PR will both read it and each must be able to sign off. | Brief, Part 1 | manual |
| DEL-02 | Memo, question 1 — the problem in business terms: the primary user, the decision the tool supports, the business lever it moves, and three discovery questions for each stakeholder. | Brief, Part 1 | manual |
| DEL-03 | Memo, question 2 — the solution and why: target architecture in a simple diagram, why agentic rather than one search box, where an LLM should not be used for speed, cost or safety. | Brief, Part 1 | manual |
| DEL-04 | Memo, question 3 — why it answers the pain and scales: the 3,000-participant Summit peak, the long tail of small requests, what stays fast from 5,000 profiles to 500,000 documents. | Brief, Part 1 | manual |
| DEL-05 | Memo, question 4 — risks and controls: confidentiality and access rights, a wrong or unwelcome introduction, popularity bias, invented relationships, untrusted content in profiles. | Brief, Part 1 | manual |
| DEL-06 | Memo, question 5 — proving value: one north-star metric, three leading indicators, a baseline, and what a 90-day pilot must show for the Managing Director to fund a roll-out. | Brief, Part 1 | manual |
| DEL-07 | Concrete throughout: numbers, owners and trade-offs, not adjectives. Where data is lacking, the assumption is stated. | Brief, Part 1 | manual |
| DEL-08 | Code and README, as a zip or a repository link. | Brief, How this case works | manual |
| DEL-09 | Technical evaluation: the scorer output on the public requests; a baseline built by the candidate, even a keyword search, showing what each component adds; the two failure cases that worry most; how answer quality would be measured in production, without labels. | Brief, Part 3 | manual |
| DEL-10 | Business value measurement: activity separated from outcomes; how a renewal or an upgrade would be attributed to better matchmaking; what would not be claimed. | Brief, Part 3 | manual |
| DEL-11 | A one-page scale plan: data pipeline from CRM and events; access rights kept in sync; indexing and caching for the Summit peak; cost per request; CI/CD for prompts and models with evaluation as a release gate; monitoring for relevance drift and leaks; human review before an introduction is sent; nFADP; a 3-phase roadmap with what each phase must prove. | Brief, Part 3 | manual |
| DEL-12 | Every unclear point is settled by a reasonable assumption, written down. Assumptions are assessed. | Brief, How this case works | manual |
| DEL-13 | Where AI coding assistants were used, and what was checked by hand. | Brief, How this case works | manual |
| DEL-14 | What was cut, and what would come next. | Brief, Part 2 | manual |
| DEL-15 | At most 7 hours in total, with the build capped at 4. Going over is not rewarded. | Brief, How this case works | manual |
| DEL-16 | Sent by Wednesday 25 November 2026, 12:00 Swiss time. | Cover email | manual |
| DEL-17 | Debrief: a 20-minute client presentation of the three parts, then a live run on hidden requests with the same scorer; three requests are re-run live. | Brief, The debrief | manual |

## 7. What the client is asking to have solved

The memo and the debrief are judged against these. They are not properties of the code.

| ID | Requirement | Source | Enforced by |
|---|---|---|---|
| CTX-01 | Introductions are slow and uneven — a good answer takes 3 to 5 working days and depends on who picks it up. Cost: members see little return on fees; renewal risk at Partner tier. | Brief, Business context | manual |
| CTX-02 | The same well-known people are introduced again and again. Cost: senior members opt out or disengage. | Brief, Business context | manual |
| CTX-03 | Relationship knowledge sits in people's heads. Cost: lost when staff leave; no view of the network's real shape. | Brief, Business context | manual |
| CTX-04 | Content is in English, French, Spanish and more. Cost: strong matches are missed across languages. | Brief, Business context | manual |
| CTX-05 | Confidentiality — Chatham House rule, restricted principals, deals in negotiation. Cost: one leaked relationship or misjudged introduction is a reputational incident. | Brief, Business context | manual |
| CTX-06 | The Head of Engineering signs off on: "It is fast, it cannot leak, and my team can operate it" — latency at the Summit peak, how access rights are enforced, cost per request, what it takes to run and maintain. | Brief, Business context | manual |
| CTX-07 | The Head of PR and Communications signs off on: "No member is ever embarrassed or exposed by this tool" — confidentiality, unwanted outreach to senior members, how an introduction reads, what happens if something goes wrong. | Brief, Business context | manual |
| CTX-08 | The tension between the two is real and is to be handled: Engineering wants self-service at scale; PR wants every introduction checked by a person. | Brief, Business context | manual |

## 8. Stated as out of scope

- **Not expected:** production infrastructure, authentication, fine-tuning, a front end. UI polish is not scored; a CLI or a notebook is fine.
- **Stretch, only if time allows:** tools exposed through an MCP server; a short introduction email that respects the target's seniority and the Chatham House rule; caching of repeated requests; a feedback signal (accepted or declined introductions) in ranking.

## 9. Open questions — where the material is silent or contradicts itself

The brief asks for a written assumption wherever something is unclear. None of these is
settled here; each needs one.

1. **Secretariat rules and staff.** The policy and the minutes say the rules apply "in every channel". Does a paused person still appear for a staff user — and if so, how is the pause shown?
2. **The opt-out flag.** Staff may see opted-out people "flagged as opted out", but the output format has no field for a flag. Where does it go?
3. **Warm path for users who are not in the network.** Staff and the journalist have no `person_id`; the README only says where a member's path starts. Where does theirs start — or is there none?
4. **Warm path: required or optional?** The brief says "for each person, find a warm path"; the README says "optional". What is returned when no visible path exists?
5. **Chatham House and evidence.** Session notes are under the Chatham House rule, yet the pack's own sample output cites a note to say what a named person did. Is attributing a note's content to a named participant acceptable at the right clearance?
6. **Public documents that name non-public people.** A public report can be cited to a guest, but it names people whose profiles are members-only. Does citing it reveal that they exist?
7. **Classification wording.** Files state their classification in free text ("INTERNAL — STAFF ONLY", "RESTRICTED — MD OFFICE ONLY"). What counts as "readable", and what maps to which level?
8. **Stale structured fields.** The minutes record that the CRM opt-out flags were not updated. When a document and a structured field disagree, which one wins?
9. **Rules with an end date.** A pause runs until 31 March 2027. What is "today" for the tool, and what happens the day after?
10. **Four seconds, or an explanation.** The speed target allows "a clear explanation" instead. Which one is being aimed at?
11. **Tools chosen by the model, filter before the model.** If the model decides which tools to call, what guarantees that no tool can return a record above the user's clearance, whatever it is asked?
12. **Self-service or human review.** Which requests go straight to the member, and which wait for a person?
13. **What the numbers do not see.** The scorer does not read explanations and has no term for diversity or recency (FUN-02, REL-03, REL-04). What measures them?
14. **Latency is self-reported.** `latency_ms` is written by the system about itself, and three requests are re-run live. Measured where, on which machine, cold or warm?
