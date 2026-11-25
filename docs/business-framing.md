# Business framing — cross-network matchmaking

*Memo for the Head of Engineering and the Head of PR & Communications, Meridian Forum.*

> **Draft 1.** Lines marked `TODO` wait for the build to finish. None may remain when this is sent.

## 1. The problem in business terms

Today a good introduction takes 3 to 5 working days. Its quality depends on which relationship manager picks up the request, and what a manager knows leaves with them.

We propose an MVP that proves value first. The Forum's business model does not change.

- **Primary user:** the relationship manager, and only the relationship manager. The MVP has no member self-service.
- **Decision supported:** which introduction to propose to a member. The manager decides; the tool prepares the answer.
- **Target:** a good answer in 1 hour to 1 day, instead of 3 to 5 days. The exact figure is set with the relationship managers (assumption A1).
- **Business lever:** staff productivity first, because it shows within weeks. Renewal is the end goal: it rests on the question our north-star metric asks (section 5).

What the MVP gives the relationship managers, beyond speed:

- **A person reviews every suggestion.** Nothing reaches a member without a manager's approval.
- **One place for what they know.** Managers record there the context that today sits in memory, spreadsheets and conversations with colleagues. Each entry improves the answers that follow.
- **An even service.** A junior manager works from the same context as a senior one, so a member gets the same quality whoever picks up the request.

**Discovery questions, before building anything:**

| Topic | What we need to learn |
|---|---|
| **Capacity** | How many organisations or members does each relationship manager handle? Does it differ by seniority or by sector? |
| **Data maintenance** | Is the extract we received produced automatically or built by hand? What effort keeps it up to date, the confidentiality fields above all? How are relationships that change over time tracked? If members supply the data, quality problems start at the source: who is responsible for what? |
| **Map of the knowledge** | Where exactly does the knowledge sit today: CRM, spreadsheets, other tools, memory? We want one map of it all. |
| **The manager's job** | What does a relationship manager do, step by step, and how do they follow up with members? What does it mean when they make a recommendation, what happens when one goes wrong, and which risks are they comfortable taking? What do today's systems measure, and what stays subjective (phone calls, face-to-face meetings)? This tells us what workload we can ask of them, how to assess impact more broadly, and which signals no tool will ever capture. |

Each is one large question that covers many smaller ones. The relationship managers answer them: where the tool can be handed off is theirs to say.

## 2. The solution, and why

> `TODO` — architecture diagram, drawn once the build is finished.

- **Why an agent rather than one search box:** `TODO`
- **Where a language model is not used, for speed, cost or safety:** `TODO`

## 3. Why it answers the pain, and how it scales

**Built for every user, rolled out to relationship managers first.** The prototype answers every role in the data pack (relationship manager, member on the portal, Summit guest) and is tested as if it were open to all. We do not recommend opening it to Summit participants yet, even where it technically could be:

- **Accuracy has to be validated over time first.** Our own tests cannot do that. We hold an extract, not the full data, and we do not know how that data is maintained.
- **The relationship managers carry that judgement.** They are the ones who say whether the tool is right, and where it can safely be handed off.

Scale then comes in steps:

1. **MVP.** A manager reviews every suggestion.
2. **Simple cases.** The tool handles simple introductions on its own. What counts as simple is still to be defined (assumption A2).
3. **Ambiguous cases.** These stay with a manager, at every stage.

The share of requests the tool handles alone grows over time, and each large Summit becomes easier to prepare than the one before.

**What we do not promise:** a tool that prepares a 3,000-participant Summit on its own.

`TODO` — the Summit peak, the long tail of small requests, and what stays fast from 5,000 profiles to 500,000 documents. These come from the build.

## 4. Risks and how we control them

Every suggestion ends in one of four outcomes.

| Suggestion | Manager | What it means | Control |
|---|---|---|---|
| Wrong | Approves | The risk: a wrong introduction reaches a member. | The manager's review, before anything is sent. |
| Wrong | Rejects | The review did its job. | The rejection is recorded. It shows where the tool cannot be trusted yet. |
| Right | Approves | The tool was correct. | The approval is recorded. It shows, case after case, where the tool can be trusted. |
| Right | Rejects | `TODO` | `TODO` |

**What the tool cannot see.** A right introduction has value only if the two members actually connect. The tool cannot measure that. Only the relationship manager can, by following up after each introduction.

`TODO` — the other risks, once the build is finished: confidentiality and access rights, an unwelcome introduction, popularity bias, invented relationships, untrusted content in profiles.

## 5. How we prove value

**North-star metric:** the share of introductions made by a relationship manager that the member judges to be a high-quality connection they could not have reached on their own.

Three leading indicators:

| Indicator | Level | What it shows | Measured by (to confirm) |
|---|---|---|---|
| **Speed** | Request | How long a member waits for a good answer. | Time from request to an answer ready to send. Today: 3 to 5 working days. |
| **Trust and adoption** | Relationship manager | Managers use the tool because they can trust what it suggests. | Share of requests handled with the tool; share of suggestions approved. |
| **Shared know-how** | Team | Know-how is centralised, so the team is less exposed when someone is absent or leaves. | `TODO` |

- **Baseline:** `TODO`
- **What a 90-day pilot must show for the Managing Director to fund a roll-out:** `TODO`

## Assumptions

- **A1 — Volume per manager.** We do not know how many requests each relationship manager handles. The target turnaround is therefore a range, 1 hour to 1 day, to be fixed with them.
- **A2 — Simple and ambiguous cases.** The line between the two is not defined yet. Until it is, every suggestion is reviewed.
- **A3 — Roll-out.** The prototype answers every role. The roll-out starts with relationship managers only, and nothing reaches a member without their approval.
- **A4 — Data.** We hold an extract and do not know how it is maintained.
