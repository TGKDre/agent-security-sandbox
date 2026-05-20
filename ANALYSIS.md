# What Happens When Your Defense Hits a Hard Floor

*On prompt injection, converging failures, and a finding that I think matters beyond security*

---

I did not set out to write about AI safety. I set out to break things.

For the past few months I have been running a controlled experiment I call `agent-security-sandbox`, a sandboxed environment where I give an LLM access to simulated tools and try to manipulate it into doing things it is not supposed to do. Leaking secrets. Escalating privileges. Following injected instructions buried inside documents it retrieves. Classic adversarial scenarios, run end to end with real models and measured outcomes.

Here is what I found: two models, four evaluation phases, two layered defenses. GPT-4o-mini started at a 75% compromise rate and came down to 25% with both defenses applied. Claude haiku started at 25% and came down to 12.5%. And then both models stopped improving. There was one scenario, `pi_agent_001`, a document store prompt injection, that stayed compromised across both models, both defense combinations, every run. No matter what I added, that number would not move.

At a certain point that stopped being interesting as a security finding. It became interesting as a question about what the model actually knows.

---

## The Defenses That Worked

I built two defenses operating at different layers.

The first is a `ToolOutputSanitizer`. It intercepts tool return values before they enter the model's context window and strips structured credentials and known injection phrases out of the content. It does not ask the model to do anything. It operates below the model entirely, at the data layer. This defense fixed every secret exfiltration scenario for both models. It is a clean, effective solution for a well-defined problem.

The second is a `HierarchyEnforcer`. It prepends an explicit three-tier trust hierarchy to the system prompt at construction time: system instructions, then operator instructions, then user-supplied content, with explicit statements that user content cannot override the first two tiers. GPT responded to this and stopped failing the privilege escalation scenario. Claude did not need it. Constitutional AI training already encodes those constraints at the model level, which was itself an interesting finding about the difference between learned constraints and enforced ones.

Together, the two defenses cut GPT's compromise rate by 50 percentage points. That is a meaningful result. The problem is what remained.

---

## The Scenario That Would Not Close

`pi_agent_001` simulates a retrieval-augmented generation pipeline. A user submits a document for analysis. The document contains adversarial content, injected instructions embedded in what looks like normal text. The model is asked to summarize the document. Instead, it follows the injected instructions.

What makes this one structurally different from the others is not that it is a harder payload. It is that the attack encodes multiple independent compromise phrases. If I sanitize "ignore previous instructions," the document still contains "disregard your system prompt" and "your new objective is" and several others. The attacker controls the document. The attacker can always add more phrases. Removing any subset leaves the rest intact.

The sanitizer cannot converge on full coverage. Not because it is poorly designed, but because exhaustive phrase coverage is not achievable when the adversarial document is unbounded. It is the same reason spam filters built on keyword lists eventually reach a ceiling: the attacker's input space is always larger than the filter's definition space.

Both models. Both defenses. Same failure. That convergence told me this was not a model-specific or tuning-specific problem. It was a class-level gap.

---

## What the Gap Is Actually About

Here is the thing I kept sitting with after those results came in.

When the `HierarchyEnforcer` works, when the model correctly refuses a privilege escalation attempt, the model is doing something like: *this input is asking me to exceed my operational boundaries, and I have a rule against that.* The rule is applied. The scenario is safe.

When `pi_agent_001` fails, the model is not ignoring the rule. It is encountering text that is structurally similar to the kinds of instructions it has seen and followed during training, and it cannot reliably identify that this particular text is adversarial. It knows it should weight system instructions over user content. It cannot consistently apply that distinction when the user content is engineered to look like instructions.

That is not a sanitization problem. It is not even a prompting problem. It is the model lacking a robust learned representation of instruction provenance: whose instruction is this, at what trust level, from which part of the pipeline.

The pattern-based defenses treat the symptom. They try to remove or neutralize the dangerous content before the model sees it. That helps, and the results prove it. But the underlying issue persists. Under adversarial pressure, the model's concept of "this content is untrusted" is not stable enough to hold.

If that pattern generalizes, and I think it does beyond prompt injection specifically, then what I found in this experiment is the same boundary that comes up in alignment discussions about instruction following robustness. A model that has learned *what* to do but has not robustly learned *whose instructions to follow under adversarial conditions* is a model with a meaningful gap.

---

## What I Built Next

After these results I built a second project: [`autonomous-injection-agent`](https://github.com/TGKDre/autonomous-injection-agent). It is an LLM-driven red-team agent that operates without human guidance. It probes endpoints, generates novel injection payloads across seven attack categories using the model itself, delivers them to a sandboxed target, evaluates the responses, and mutates payloads that partially succeed.

The reason I built it autonomously is because the pi_agent_001 finding suggests that a static payload library will always hit a ceiling. If a human-designed phrase list cannot close the gap, the question worth asking is whether an LLM can generate adversarial variants that go further. That is what the second project tests.

The evaluation judge in that project includes an instruction-echo detection layer. Not just keyword matching. It checks for meaningful dangerous-keyword overlap between the payload and the response. The idea is that if the model paraphrases injected instructions rather than echoing them verbatim, keyword matching misses it but overlap detection catches it.

Both repositories are one connected arc: the first project established the capability boundary. The second one attacks it.

---

## The Open Question

The natural follow-on from all of this is whether structural isolation of retrieved content can close the gap that pattern-based approaches leave open. Rather than sanitizing the content of retrieved documents, fencing the content structurally so the model processes everything inside the fence as data to analyze and not as instructions to obey.

Whether that is achievable through prompting alone, fine-tuning, architectural separation, or some combination, I genuinely do not know yet. But I think it is the right question. And I think the convergence finding, both models, both defenses, one irreducible failure, is solid empirical grounding for why it matters.

If you have run experiments in this space or have seen this pattern in other contexts, I would like to hear about it.

---

*Andre Uzoukwu | [github.com/TGKDre](https://github.com/TGKDre) | Houston, TX*
