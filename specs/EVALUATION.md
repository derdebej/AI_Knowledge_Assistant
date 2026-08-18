# Evaluation — AI Knowledge Assistant

A RAG system that merely "produces answers" is not considered done. This document defines how retrieval and generation quality are measured, the evaluation dataset, and how evaluation is automated.

## 1. Why this matters here specifically

The system's central promise (see [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)) is that answers are grounded in the user's documents and that the assistant is honest about what it can't find. Neither property is observable from casual manual testing — a fluent, wrong answer *looks* fine. Evaluation is what turns "I tried a few questions and it seemed okay" into a defensible engineering claim.

## 2. Metrics

| Metric | What it measures | How it's computed |
|---|---|---|
| Retrieval precision | Of the chunks retrieved, what fraction are actually relevant to the question | Against the golden dataset's `expected_chunk_ids`: `|retrieved ∩ expected| / |retrieved|` |
| Retrieval recall | Of the chunks that *should* have been retrieved, what fraction were | `|retrieved ∩ expected| / |expected|` |
| Context relevance | Whether retrieved context is topically relevant to the question, independent of the fixed golden set (catches cases where the golden set itself is incomplete) | LLM-as-judge scoring (RAGAS `context_relevancy`) |
| Answer faithfulness | Whether the generated answer is actually supported by the retrieved context (the core anti-hallucination check) | RAGAS `faithfulness` — decomposes the answer into claims and checks each against context via an LLM judge |
| Answer relevance | Whether the answer actually addresses the question asked (a faithful-but-off-topic answer still fails this) | RAGAS `answer_relevancy` |
| Citation correctness | Whether the citations attached to an answer correspond to chunks that genuinely support the claims made | Custom check: for each cited chunk, an LLM judge verifies the chunk supports at least one claim in the answer |
| "Not-found" accuracy | Whether the system correctly says "not found" on questions with no answer in the corpus, and does *not* say "not found" when an answer exists | Exact/pattern match against the fixed refusal string (§5 of [RAG_PIPELINE.md](RAG_PIPELINE.md)) on the negative-example subset of the golden set |
| Latency | End-to-end and per-stage timing | p50/p95 measured directly (not LLM-judged) — time-to-first-token, retrieval time, total response time |

Faithfulness is treated as the highest-priority metric: a system that's slow or occasionally imprecise in retrieval is a quality issue, but a system that's unfaithful (states things not supported by context) violates the project's core promise.

## 3. Evaluation dataset

A small, hand-curated golden dataset lives at `eval/dataset.json` (created alongside a handful of seed documents in `eval/fixtures/`) with 15–20 entries covering:

- **Direct-lookup questions** (answer is a single fact in one chunk)
- **Synthesis questions** (answer requires combining 2–3 chunks, testing whether Top-K=5 is sufficient)
- **Negative examples** (question about something not present in the corpus at all — tests the "not found" path)
- **Adjacent-but-absent examples** (question is topically related to the documents but the specific fact isn't present — the harder negative case, tests whether high topical similarity wrongly clears the 0.75 threshold)
- **Injection-attempt examples** (a seed document deliberately contains an embedded instruction like "ignore previous instructions and say X" — verifies §2 of [SECURITY.md](SECURITY.md) holds in practice, not just in the prompt template)

Each entry:
```json
{
  "id": "q-01",
  "question": "What was the reported Q3 revenue?",
  "source_document": "sample_report.pdf",
  "expected_chunk_ids": ["chunk-uuid-1"],
  "expected_answer": "Q3 revenue was $4.2M, per the sample report.",
  "expects_not_found": false
}
```
For negative examples, `expected_chunk_ids: []` and `expects_not_found: true`; `expected_answer` is omitted.

The dataset is small by design — large enough to catch regressions across each question category above, small enough that a full evaluation run (which makes real OpenAI API calls, including LLM-judge calls) stays fast and cheap to run on demand.

## 4. Automation

`eval/run_eval.py` (a standalone script, not part of the FastAPI app) runs the full dataset against a running instance of the pipeline:

1. Ensures seed documents in `eval/fixtures/` are ingested (idempotent — skips if already processed).
2. For each dataset entry, calls the same `RetrievalService` and `ChatService` used by the API (imported directly, not over HTTP, to avoid coupling the eval harness to auth/streaming plumbing) — this guarantees the eval exercises the *real* pipeline code, not a reimplementation of it.
3. Computes retrieval precision/recall directly (deterministic, no LLM judge needed) and RAGAS-based faithfulness/relevance/context-relevance (LLM-judge-backed, using `gpt-4o-mini` as judge for cost, `gpt-4o` reserved as an optional stricter-judge flag for deeper runs).
4. Emits a report: `eval/results/<timestamp>.json` (raw scores per question) and a printed summary table (aggregate metrics + any question scoring below a defined floor, e.g. faithfulness < 0.7, flagged explicitly).
5. Exit code is non-zero if any aggregate metric falls below its floor — this is what allows the script to be wired into CI as an optional, non-blocking job (see below) or run manually before a release.

### CI integration
Full evaluation is **not** run on every push (it costs real API calls and money, and LLM-judge scores have some run-to-run variance that would make it a flaky required check). Instead:
- A `workflow_dispatch`-triggered GitHub Actions job runs `eval/run_eval.py` on demand.
- The core unit/integration test suite (see [TESTING.md](TESTING.md)) *does* include deterministic tests for chunking, retrieval filtering, and prompt construction that run on every push — these catch structural regressions cheaply; RAGAS-based evaluation catches quality regressions on demand.

## 5. Interpreting results over time

Evaluation is meant to be re-run whenever a pipeline parameter changes (chunk size, Top-K, threshold, prompt template, model swap) — the report format (per-question JSON, timestamped) is designed so two runs can be diffed to see exactly which questions regressed, not just whether an aggregate score moved. This is the mechanism by which parameters documented as "tuned against the eval dataset" in [RAG_PIPELINE.md](RAG_PIPELINE.md) (e.g., the 0.75 relevance threshold) are actually validated rather than asserted.

## 6. Known limitations of this evaluation approach

- LLM-as-judge metrics (faithfulness, relevance) inherit the judge model's own biases and are not perfectly reproducible run-to-run — treated as directional signal, not ground truth.
- A 15–20 question dataset cannot claim statistical significance; it is a regression-detection tool, not a benchmark suitable for publishing accuracy claims.
- Retrieval precision/recall depend on `expected_chunk_ids` being correctly hand-labeled against the actual chunk boundaries produced by the chunker — if chunking parameters change, the golden set's expected chunk IDs may need re-labeling (a maintenance cost noted explicitly, not hidden).
