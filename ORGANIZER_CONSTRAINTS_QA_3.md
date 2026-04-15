# LOCALSCRIPT — ORGANIZER CONSTRAINTS & Q&A KNOWLEDGE BASE
# Version: 3
# Last updated: 2026-04-13 (added checkpoint-2 official post-call Q&A from Telegram)
# Purpose: Single source of truth for ALL official project constraints, organizer answers,
#           checkpoint Q&A, support bot responses, and rule clarifications.
#           Feed this file to Cursor/AI alongside README and ONBOARDING for full context.
# Impact flags: [BREAKING] | [CONFIRM] | [NEW] | [INFO] | [RELAXED]

---

## 1. HARD TECHNICAL CONSTRAINTS (from task description)

| Constraint | Value | Notes |
|---|---|---|
| Max GPU VRAM | 8 GB | Model must fully fit. GPU is optional — CPU/RAM fallback acceptable. |
| Inference engine | Ollama only | No alternative backends |
| External API calls | Forbidden | Must work fully offline/local |
| Single-command launch | Required | docker-compose up --build |
| Model auto-pull on start | Required | Must not require manual setup |
| Backend language | Any (Python preferred) | Must work in required Docker scheme |
| Output | Lua script, ready to use | No partial output |
| Mandatory endpoint | /generate | Must exist and work correctly |
| Response time | No hard limit. Soft guideline: ≤10 min total. | [RELAXED — confirmed checkpoint-2 post-call] |
| Token limit (256) | Guideline only, not a hard cap | [RELAXED — confirmed checkpoint-2 post-call] |

---

## 2. CHECKPOINT 1 Q&A (from Telegram #справочные_данные, 2026-04-12)

### Infrastructure
- **Must use Ollama?** Yes. [CONFIRM]
- **Only Ollama registry models?** No. External open-source models allowed. [NEW]
- **Must supply Ollama with solution?** Yes. Everything in one docker-compose, no external Ollama assumed. [BREAKING]
- **Model pull must be part of launch?** Yes. [BREAKING — model-puller service required]

### API Contract
- **How strict is the API contract?** Baseline YAML is a baseline only. Extensible. [CONFIRM]
- **Can we add fields, sessions, extra endpoints?** Yes. [NEW]
- **Can prompt and context be passed separately?** Yes. [CONFIRM]
- **Can context be empty?** Yes. [CONFIRM]

### Evaluation & Scoring
- **Must consider public examples structure?** Yes. [CONFIRM]
- **Can multiple models be used?** Yes. Different models for different stages. [NEW]
- **Is fine-tuning allowed?** Yes, within technical constraints. [NEW]
- **Is simplicity important?** Yes. At equal quality, simpler scores better. [CONFIRM]
- **Will hidden sample include code editing tasks?** Yes, may appear. [BREAKING — context field must work]

### Evaluation Process
- **How is evaluation done?** First: does it launch. If not — no further evaluation. [BREAKING — launch must be flawless]
- **Scale of generated code?** Smaller applied scripts, not large systems. [CONFIRM]

---

## 3. OPENING CEREMONY Q&A

- **External AI APIs?** Forbidden. Fully local. [BREAKING]
- **GPU limit (8 GB)?** Model must fully fit in 8 GB GPU. [CONFIRM]
- **Intended use case?** Local tool for generating low-code scripts from user spec. [CONFIRM]
- **At ambiguous request — clarify or guess?** Clarification preferred. [INFO]
- **Local knowledge base or templates allowed?** Yes, if delivered with solution. [CONFIRM]

---

## 4. CHECKPOINT 2 Q&A — LIVE CALL (from recording, manually verified by Tim, 2026-04-13)

### Q0: GPU Architecture on Evaluation Server
**Resolution:** Target NVIDIA. If server is not NVIDIA and container fails — not our fault, noted in README. [CONFIRM — keep driver: nvidia]

### Q1: Task Scope — MWS-specific Lua Only, or Arbitrary Lua?
**A:** ANY Lua. Including pure algorithmic Lua (Fibonacci, sorting, etc.) with no wf.vars context. [BREAKING — add pure Lua examples to system prompt]

### Q2: context Field in JSON
**A:** Separate field is fine. Contract is flexible. [CONFIRM]

### Q3: Web UI
**A:** Bonus only. Code quality is everything. Web UI is tiebreaker at equal quality. [CONFIRM]

### Q4: Docker installed on eval server, long startup OK?
**A:** Yes to both. 10-15 min startup is acceptable. [CONFIRM]

### Q5: Evaluation Metric
**A:** Functional equivalence, NOT exact match. temperature=0 and fixed seed not required. [CONFIRM]

### Q6: Prompt Injection and Stress Tests
**A:** YES — will be tested. Expect anything. [NEW — prompt injection defense required]

### Q7: Nested JSON in wf.vars
**A:** Don't rely specifically on JSON. Public sample is just an example. [INFO]

### Q8: Response Streaming
**A:** Optional, up to the team. [INFO]

### Q9: GitLab — Open Code Allowed
**A:** Yes, request via support chat-bot. [INFO]

---

## 5. CHECKPOINT 2 Q&A — OFFICIAL POST-CALL TELEGRAM (2026-04-13, from Alina G.)

Source: Telegram #справочные_данные message from Алина Гараева, 20:52–20:53 on 2026-04-13.

### Q: Is GPU required?
**A:** No. Solution can run without GPU, including on RAM/CPU, if that gives acceptable results.
**Impact:** [RELAXED] — driver: nvidia in docker-compose is still preferred (NVIDIA is "most likely"), but a CPU fallback path is valid and acceptable to organizers. No action needed.

### Q: Is there a hard time limit per response?
**A:** No hard limit. The guideline is "don't go significantly over 10 minutes for generation."
If significantly slower, it becomes a problem for evaluation and general perception.
**Impact:** [RELAXED — INFO] — Our model on NVIDIA loads in ~15s and generates in ~3-10s per request. Well within limits. No action needed.

### Q: What does the 256-token limit mean?
**A:** Not an absolute ban. It is a guideline and reference value to aim for. More important that the system ultimately solves the task well.

### Q: Is 256 tokens a hard ceiling?
**A:** No. It is more of a guideline for a single step or request, not an absolute rule for the entire pipeline.

### Q: What if the task doesn't fit in such a small context?
**A:** Expected approach: decompose the task into steps, distribute context between agents,
narrow context, collect intermediate results — stay within limits that way.
One of the key expected approaches: **do NOT try to solve everything in one huge request.
Decompose the task and distribute it between agents or stages.**
**Impact:** [NEW — ARCHITECTURE GUIDANCE] — This validates our multi-agent approach (PromptBuilder → Agent → Validator). Keep MAX_RETRIES and the retry loop. For very large tasks, decomposition into sub-tasks is a scoring differentiator.

---

## 6. SUPPORT BOT / OTHER OFFICIAL SOURCES

> ⚠️ Add answers from the support bot or any other official communications here as they arrive.

---

## 7. PENDING UNKNOWNS

| Question | Priority | Status |
|---|---|---|
| Exact GPU model on eval server | 🟡 MEDIUM | Answered: "orient to NVIDIA" |
| Pure algorithmic Lua in hidden tests | 🔴 RESOLVED | Yes — any Lua |
| Prompt injection will be tested | 🔴 RESOLVED | Yes |
| Functional equivalence metric | 🟢 RESOLVED | Yes |
| GPU required | 🟢 RESOLVED | No — CPU fallback acceptable |
| 256-token hard limit | 🟢 RESOLVED | No — guideline only |
| Decomposition/multi-agent approach | 🟢 RESOLVED | Yes — explicitly encouraged |
