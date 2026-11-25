# Business framing — cross-network matchmaking

*Memo for the Head of Engineering and the Head of PR & Communications, Meridian Forum.*

## 1. The problem in business terms

Today a good introduction takes 3 to 5 working days. Its quality depends on which relationship manager picks up the request, and what a manager knows leaves with them.

We propose an MVP that proves value first. The Forum's business model does not change.

- **Primary user:** the relationship manager first. Self-service for members is technically ready and deliberately not opened yet (section 3).
- **Decision supported:** which introduction to propose to a member. The manager decides; the tool prepares the answer.
- **Target:** a good answer in 1 hour to 1 day, instead of 3 to 5 days. The figure is set with the managers (A1).
- **Business lever:** staff productivity first, because it shows within weeks. Renewal is the end goal (section 5).

The MVP also gives managers one place to record what they know, so a junior manager works from the same context as a senior one.

**Three discovery questions:**

| Topic | What we need to learn |
|---|---|
| **Data and knowledge map** | Where does the knowledge sit today: CRM, spreadsheets, other tools, memory? Is the extract we received produced automatically or by hand? What effort keeps it up to date, the confidentiality fields above all, and who is responsible when members supply the data? |
| **Process map** | How many organisations or members does each manager handle, by seniority or sector? What does a manager do, step by step, and what stays subjective, such as phone calls and meetings? |
| **Recommendation and risk** | What does a recommendation mean, what happens when one goes wrong, and which risks are the managers comfortable taking? |

## 2. The solution, and why

```mermaid
flowchart LR
    ask(["Manager asks<br/>in plain language"])
    data[("CRM, events,<br/>documents")]
    access["Access rights<br/>and limits"]
    search["Search, evidence,<br/>warm path"]
    explain["Explanations"]
    verify["Check<br/>the answer"]
    review(["Manager approves<br/>or rejects,<br/>records context"])
    member(["Member"])

    ask --> access --> search --> explain --> verify --> review --> member
    data --> access

    classDef model stroke-dasharray: 6 4,stroke-width:2px
    class explain model
```

The dashed step is the only one that calls a language model.

- **Why more than one search box.** A search box returns records. An introduction also needs this user's access rights applied first, the evidence behind each match, a warm path to the person, and an explanation a manager can check.
- **Why a fixed workflow, for now.** Each step is a separate function, and the same functions could be given to a model as tools to call. We chose a predictable workflow instead: every step is visible, the same request gives the same answer, and control is handed to a model progressively, only where it proves safe and useful.
- **Where a language model is not used.** Access rights, ranking, evidence and warm paths are code: about 5 ms together, and nothing written in a profile can change them. The model only writes the explanations: about 2 seconds and $0.0005 a request.

## 3. Why it answers the pain, and how it scales

**The MVP can already run in self-service.** What a member would receive is the same output a manager reviews, under that member's own access rights. Opening it is a decision, not a new build.

**What is missing is evidence, not technology.** The prototype is tested on 10 requests and an extract of the data. That sample is too small to show that the tool works at scale and protects the Forum's reputation, and it may be biased. The MVP phase builds the proof in two ways:

- **From the data.** Every request is traced, so we can analyse what fails, where and why.
- **From the relationship managers.** They confirm the value that data cannot measure, such as whether two members actually connected, and they say where the tool can be handed off.

Once both hold, self-service starts with simple cases; ambiguous ones stay with a manager (A2). We do not promise a tool that prepares a 3,000-participant Summit on its own.

**What scales as built, and what does not.** The access rights, the limits and the checks around the model are code: a few milliseconds, whatever the volume. Matching by keywords and a hand-kept taxonomy will not hold from 5,000 profiles to 500,000 documents: it needs an index, chosen on real data. A request costs about $0.0005; the explanation, one model call of about 2 seconds, is the part to load-test before a Summit peak. Details are in [`evaluation-and-scale.md`](evaluation-and-scale.md).

## 4. Risks and how we control them

Every suggestion ends in one of four outcomes.

| Suggestion | Manager | What it means | Control |
|---|---|---|---|
| Wrong | Approves | The risk: a wrong introduction reaches a member. | The manager's review, before anything is sent. |
| Wrong | Rejects | The review did its job. | The rejection is recorded. It shows where the tool cannot be trusted yet. |
| Right | Approves | The tool was correct. | The approval is recorded. It shows where the tool can be trusted. |
| Right | Rejects | The manager knows something the data does not. | The reason is recorded and becomes context for the next answers. |

| Risk | Control |
|---|---|
| Confidentiality and access rights | Rights are applied in code before any search; every answer is checked before it leaves. 0 violations on the 10 test requests. |
| A wrong or unwelcome introduction | A manager approves every suggestion. Opt-outs and the Secretariat's rules are applied in code. |
| Popularity bias | No person is suggested more than twice in a run, and no one the member met in the last 90 days. |
| Invented relationships | Evidence and warm paths are looked up in the data by code. The model cannot add one. |
| Untrusted content in profiles | Text in a profile is data, never an instruction. Hidden text is removed and reported to a person. |

## 5. How we prove value

**North-star metric:** the share of introductions made by a relationship manager that the member judges to be a high-quality connection they could not have reached on their own.

Three leading indicators:

- **Speed:** how long a member waits for a good answer.
- **Trust, adoption and shared know-how:** managers use the tool because they can trust it, and record in it what they know, so the team is less exposed when someone is absent or leaves.
- **A more even spread of recommendations:** introductions reach across the network, and the same few people are no longer solicited by everyone.

These indicators are deliberately qualitative at this stage. We build them with the relationship managers and validate them during discovery, to see which ones make sense as figures.

- **Baseline:** 3 to 5 working days per answer. Today's quality is not measured: the pilot's first weeks measure it on requests handled without the tool.
- **What a 90-day pilot must show:** zero leaks, a good answer within a day, the managers confirming the value on what data cannot measure, and enough traced requests to judge whether self-service is safe.

**Assumptions.** A1: the volume per manager is unknown, so the target is a range. A2: simple and ambiguous cases are not defined yet. A3: during the MVP, nothing reaches a member without a manager's approval. A4: we hold an extract and do not know how it is maintained. Full list: [`ASSUMPTIONS.md`](ASSUMPTIONS.md).
