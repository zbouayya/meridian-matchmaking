# Assumptions, open questions and improvement areas

What we assumed in order to move forward, what looked strange in the material, and what a
better version of this MVP would add. The brief asks for a written assumption wherever
something is unclear; this file is where they live. It grows as the build goes.

- **Decided** — a choice we made and build on.
- **Working** — a default taken to keep moving; to confirm or change.
- **Open** — a question we cannot answer from the material. It goes to the client.

The points where the brief, the policy and the pack are silent or contradict each other are
listed in [`SPECS.md`](SPECS.md), section 9. This file says which of them are now settled.

## 1. Assumptions we build on

| # | Topic | Assumption | Status |
|---|---|---|---|
| A-01 | Who the MVP is for | The relationship manager, and only them. The prototype still answers every role in the pack, so that it can be tested as if open to all. | Decided |
| A-02 | Access before ranking | The access policy runs in code, first. What ranks records only ever receives what this user may be offered. | Decided |
| A-03 | People first | We recommend people first; organisations and initiatives when the request asks for them. | Decided |
| A-04 | Opted-out person | The profile field is the truth. The tool never assumes that someone has stopped opting out. It can miss someone who opted out when the data does not say so: that risk is carried by the relationship manager. | Decided |
| A-05 | Data quality | Keeping the data right is the relationship managers' job, not the tool's. Data quality management and solution design are kept separate. | Decided |
| A-06 | Routing through the organisation | The minutes say a request for an opted-out person goes through their institute. Suggesting a colleague or the organisation instead is a nice-to-have and is not built. | Decided |
| A-07 | Paused person | Hidden from members and guests. Shown to staff with the pause stated, so that they can ask the person whether to lift it and update the data. | Decided |
| A-08 | No dialogue in the prototype | The output is one line per request, so "do you want to lift the pause?" appears as a flag in the explanation, not as a question the tool waits on. | Working |
| A-09 | Ranking by rules | Keyword search on a record's text. Theme tags are not part of the match: they re-rank what the search found. The taxonomy's labels and synonyms widen the search across languages. | Decided |
| A-10 | People first, evidence after | Rules choose the people; evidence is gathered and explanations are written afterwards. If the model fails, the ranked results still come back. | Decided |
| A-11 | No embeddings in the prototype | Access rights and themes already keep the set of possible answers small (84 records at most here). Embeddings are argued in the scale plan, not built now. | Decided |
| A-12 | Rules found only in documents | The pause and the do-not-pair rule are structured data, in `data/secretariat_rules.json` beside the pack: who is concerned, until when, and the source. A person writes and approves each entry; no model writes that file, and the reason for a rule is not in it. Entries are copied by hand from the minutes (D-03) and an email (M-02). | Decided |
| A-13 | Kind of answer wanted | The request's `entity_types` field is used when present. When it is absent, people, organisations and initiatives are all searched and the answer says so, in a `note`. Asking the requester first is an improvement for after the MVP, not part of it. | Decided |
| A-14 | "Today" | The day the tool runs. The pause ends by itself after 31 March 2027. | Working |
| A-15 | Opt-out shown to staff | The output format has no field for it, so the flag is a sentence in the explanation. | Working |
| A-16 | Duplicate person records | Two person records are one person when they share an organisation and one name contains the other. The most recently engaged record is offered; the text of both is searched. | Working |
| A-22 | Organisations and themes | Theme tags stay out of the match (A-09), except for records with no free text. Every organisation is in that case: its themes are all it says about itself, so they are searched. | Decided |
| A-23 | Do-not-pair, organisations included | The minutes name two people, and give as the reason a dispute between their two organisations. The tool keeps the organisations apart too: neither is offered to the other side as a partner, and nobody is routed through them. | Working |
| A-24 | Which text has authority | Only that rules file changes what the tool does. Text found in a profile, a note, a document, an email or a request is data: it is searched and quoted, never obeyed. | Decided |
| A-25 | Hidden text | HTML comments, elements that are not displayed and characters that do not display are removed when the pack is loaded and from every request, before anything is searched or sent to a model. What was removed is reported for a person to check. This is hygiene, not a defence: a planted sentence a reader can see goes through. | Decided |
| A-26 | Documents and emails | The code parses the PDFs, the Word minutes and the emails, cuts them into passages and reads the classification written inside each file; anything unreadable is restricted. They are evidence for a match, cited by their own id, at their own clearance. They are not searched to find a match, and no relationship is derived from them. | Decided |
| A-27 | Reading a classification | An email: its `X-Meridian-Classification` header, exactly one of the four levels. A document: a line saying "Classification:" or a banner in capitals among its first five lines. Several levels on that line give the most closed one. | Working |
| A-17 | One model call, no ranking by the model | Code ranks and code looks up the evidence. The model only writes the explanations, from facts already filtered for the user. A planted instruction can therefore not move a rank or reach a record. | Working |
| A-18 | Session notes as evidence | A note is used at or above its visibility. The explanation may say that a person took part and what the session was about; it never attributes a statement to a named person. | Working |
| A-19 | Someone the requester already knows | Kept in the answer, and the explanation says they already know each other (see Q-02). | Working |
| A-20 | Warm path | The shortest chain of visible relationships from the requester, three steps at most, never through a paused person. Staff and guests have no place in the network, so they get none. | Working |
| A-21 | Time budget | The model has 3 seconds per request. Past that, the ranked results come back with explanations written by rule. | Working |

Settled from `SPECS.md` section 9: question 1 (A-07), 2 (A-15), 3 (A-20), 5 (A-18), 7 (A-27), 8 (A-04), 9 (A-14), 11 (A-17), 12 (A-01).

## 2. What looked strange, and stays open

| # | What we saw | Why it matters | Status |
|---|---|---|---|
| Q-01 | **The labels count people the requester already knows as good answers.** On request Q01, both people our keyword search suggests already have a direct relationship with the requester; one is a board peer, last met on 15 October 2026. The scorer marks both as relevant. | The members' question is the opposite: "did the Forum connect me to people I could not have reached myself?" We do not know how the labels were made or sampled. A different answer from ours is not necessarily a wrong one. | Open |
| Q-02 | **What to do with someone the requester already knows.** Nothing in the policy says: exclude, rank lower, or show with a note. | It decides whether the tool creates new reach or repeats the existing network. | Open |
| Q-03 | **Relationship strength is not explained.** It goes from 1 to 5, but in the data it mostly follows the type: all 75 shared sessions are 2, all 71 shared initiatives are 3, all 49 staff contacts are 3. Only 32 of 229 rows vary. | We cannot treat it as a measure of how well two people know each other without knowing who sets it and how. | Open |
| Q-04 | **Who maintains the taxonomy.** 12 themes, three to six synonyms each, no regions. A request that names a theme only in part ("hydrogen projects") is not recognised. | The rule-based ranking is only as good as this file. | Open |
| Q-05 | **The opt-out field can be stale.** The minutes record that the CRM flags were not updated as of 12 November. | See A-04: the risk is accepted and carried by the relationship manager. | Open |
| Q-06 | **The same people come back.** One person appears in 4 of our 10 answers. A member asked for a pause after eleven introduction requests in a month. The prototype keeps no memory between requests. | No cap per person and per period exists, and none is defined. | Open |
| Q-07 | **The public requests are easy for rules.** Keyword search with the taxonomy reaches 0.89 nDCG@5 with no model. | There is little room left to show a gain on these 10 requests, and the hidden ones may differ. | Open |
| Q-09 | **The kind of answer wanted does not follow the wording.** Each public request carries a field listing the kinds accepted. Q01 says "I want to meet people" and accepts people, organisations and initiatives; Q09 says "connect me with people" and accepts initiatives too. | The field cannot be rebuilt from the text, by a rule or by a model. We do not know who sets it, nor whether the hidden requests carry it (see A-13). | Open |
| Q-10 | **Nothing guarantees a mix.** When several kinds are accepted, the top five is whatever scores highest: on Q04 it is five people. The scorer does not reward a mix. | Whether a member who accepts three kinds expects to see three is a product choice. | Open |
| Q-08 | **Organisations have no descriptive text.** Only a name, a type, a country, a region and theme tags. With tags out of the match they almost vanished: on Q04 and Q07 no organisation was in our top five, while 8 and 5 are labelled relevant. | Handled by A-22. The question for the client remains: where is an organisation described? | Open |

## 3. Improvement areas

What a better version of this MVP would add. None of it is built; each line says why it
was left out now.

| # | Improvement | Why it matters | Why not now |
|---|---|---|---|
| I-01 | **A maintenance loop for the data.** Emails and documents are parsed once into notes, and a relationship manager approves each one before it counts. | The tool then feeds on a few canonical sources that people keep right, instead of many scattered ones. | The minutes show the manual update of the CRM already failing. The loop needs an owner and a routine first: a discovery question. |
| I-02 | **Pause and do-not-pair as real fields in the CRM.** A pause belongs to a person, a do-not-pair to a pair of people or organisations. | Today the CRM has one opt-out flag for everything; our rules file is a stand-in for the missing fields. | It changes the client's data model. |
| I-03 | **Relationships derived from documents.** For instance "she suggested him" in an email. | More warm paths. | The pack justifies about one new relationship, and a warm path must use the pack's own relationships to be valid. |
| I-04 | **An injection classifier when data is loaded,** with flagged records sent to a person. | Catches planted instructions written in plain sight, which the cleaning does not. | Probabilistic and bypassable: a complement to the controls in code, never a replacement. |
| I-05 | **Keyword stuffing.** A profile that repeats the right words ranks higher in a keyword search. | Ranking can be gamed without any instruction. | Needs a signal that does not come from the profile's own text. |
| I-06 | **A red-team suite as a release gate.** | Proves that paraphrased or translated injections change nothing. | Our tests cover the pack's planted instruction and a few variants only. |
| I-07 | **Asking the requester when the request is unclear,** for instance about the kind of answer wanted. | Better than assuming. | The prototype answers in one pass; today it searches all kinds and says so. |
| I-08 | **A guaranteed mix** when several kinds of answer are accepted. | A member who accepts three kinds may expect to see three. | A product choice, not yet made (Q-10). |
| I-09 | **Memory between requests:** a cap on how often one person is suggested, and no repeat of someone already suggested or already known. | Protects over-solicited members (Q-02, Q-06). | The prototype keeps no state. |
| I-10 | **Region, recency and diversity in the ranking.** | The brief asks for all three. | Not built; the scorer does not measure them. |
| I-11 | **Tools the model chooses among.** | More flexible plans for unusual requests. | Each choice is one more model round trip, and one more thing an injection can target. |
| I-12 | **Embeddings.** | Bridges languages outside the taxonomy's 12 themes, and keeps retrieval small as the data grows. | Not needed at this size (A-11); argued in the scale plan. |
