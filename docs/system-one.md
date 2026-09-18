# System One / Jev integration

## Audit result

BettaFish mixes open-ended generation with bounded judgment. System One is a
good replacement for the latter, not for arbitrary prose generation.

| Decision site | Fit for Jev | Status | Why |
| --- | --- | --- | --- |
| QueryEngine search-tool routing | Strong | Implemented | Closed set of six Tavily tools |
| QueryEngine reflection continue/stop | Strong | Implemented | Value-of-information gate |
| ReportEngine template selection | Strong | Implemented | Closed set of local templates |
| Search-query generation | Poor | Keep LLM | Arbitrary text |
| First/reflection summaries | Poor | Keep LLM | Evidence synthesis |
| Report structure/layout/word budget | Mixed | Keep LLM for now | Arbitrary structured output |
| Chapter generation | Poor | Keep LLM | Long-form synthesis |
| Forum host speech | Poor | Keep LLM | New prose and synthesis |
| MediaEngine tool routing | Strong | Next | Different closed tool set |
| InsightEngine DB-tool routing | Strong | Next | Different tool set / DB-dependent |
| Evidence relevance / contradiction gates | Strong | Next | Good Score/Noul candidates after evals |

### Existing bug fixed by the split

The QueryEngine prompt asked the LLM for `search_tool`, `start_date`, and
`end_date`, but `search_node.py` only retained `search_query` and
`reasoning`. The caller therefore usually fell back to
`basic_search_news`. Tool routing is now owned by System One; the LLM prompt
only generates the open-ended query.

## Runtime behavior

The integration is fail-open to the legacy path:

- no `TYPESAFE_API_KEY` -> existing behavior;
- request/response error -> existing behavior;
- Choice confidence below `SYSTEM_ONE_CHOICE_CONFIDENCE` -> fallback;
- reflection Noul below `SYSTEM_ONE_STOP_THRESHOLD` -> skip the next expensive
  reflection query + search + summary chain.

Defaults: `SYSTEM_ONE_MODEL=jev-latest`,
`SYSTEM_ONE_CHOICE_CONFIDENCE=0.45`,
`SYSTEM_ONE_STOP_THRESHOLD=0.30`, `SYSTEM_ONE_TIMEOUT=30`.

Set `SYSTEM_ONE_TRACE_PATH` to write JSONL traces. By default traces contain a
state hash, answers, and latency rather than the full state.

## Manual GitHub Action

Workflow: **Manual Research (System One)**

Inputs: `query`, `max_reflections` (0..3), and `use_system_one`.

Configuration wired by the workflow:

Repository secrets:
- `MODEL_API_KEY`
- `TAVILY_API_KEY`
- `ANSPIRE_API_KEY`
- `TYPESAFE_API_KEY`

Repository variables:
- `MODEL_BASE_URL`
- `MODEL_NAME`

The current headless job runs QueryEngine, so Tavily is the active search API.
Anspire is wired for the rest of BettaFish but is not invoked by this job.
Artifacts contain `result.md`, `metadata.json`, and (when used)
`system_one_trace.jsonl`.
