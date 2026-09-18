"""Centralized System One questions and confidence gates."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger

from .client import get_system_one_client


QUERY_SEARCH_CRITERIA = {
    "basic_search_news": (
        "General-purpose news/web research where no stronger temporal, visual, "
        "or depth-specific signal is present."
    ),
    "deep_search_news": (
        "Needs broad background, multiple perspectives, or deeper context rather "
        "than a quick lookup."
    ),
    "search_news_last_24_hours": (
        "Breaking, today, just announced, current status, or developments where "
        "the last 24 hours are materially important."
    ),
    "search_news_last_week": (
        "Recent developments or a trend over roughly the last seven days."
    ),
    "search_images_for_news": (
        "The task materially requires images, visual evidence, screenshots, "
        "photos, charts, or other visual references."
    ),
}

_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _answers(result: Optional[Dict[str, Any]]) -> Any:
    if not result:
        return None
    answers = result.get("answers")
    if answers is None and isinstance(result.get("data"), dict):
        answers = result["data"].get("answers")
    return answers


def _answer(result: Optional[Dict[str, Any]], question_id: str) -> Optional[Dict[str, Any]]:
    answers = _answers(result)
    if isinstance(answers, dict):
        value = answers.get(question_id)
        if isinstance(value, dict):
            return value
    return None


def _choice_value(answer: Optional[Dict[str, Any]]) -> Optional[str]:
    if not answer:
        return None
    value = answer.get("choice")
    return value if isinstance(value, str) and value else None


def _confidence(answer: Optional[Dict[str, Any]], choice: Optional[str] = None) -> float:
    if not answer:
        return 0.0
    raw = answer.get("confidence")
    if isinstance(raw, (int, float)):
        return float(raw)
    probabilities = answer.get("probabilities")
    if isinstance(probabilities, dict):
        if choice and isinstance(probabilities.get(choice), (int, float)):
            return float(probabilities[choice])
        numeric = [float(v) for v in probabilities.values() if isinstance(v, (int, float))]
        if numeric:
            return max(numeric)
    return 0.0


def _noul_value(answer: Optional[Dict[str, Any]]) -> Optional[float]:
    if not answer:
        return None
    value = answer.get("noul")
    return float(value) if isinstance(value, (int, float)) else None


def extract_explicit_date_range(text: str) -> Optional[Tuple[str, str]]:
    """Return the first two valid ISO dates when the text contains an explicit range."""
    found: List[str] = []
    for raw in _DATE_RE.findall(text or ""):
        try:
            datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            continue
        found.append(raw)
        if len(found) == 2:
            break
    if len(found) != 2:
        return None
    return tuple(sorted(found))  # type: ignore[return-value]


def choose_query_search_tool(
    *,
    input_data: Any,
    generated_query: str,
    phase: str,
) -> Optional[Dict[str, Any]]:
    """Choose one of QueryEngine's closed-set Tavily tools with Jev."""
    if isinstance(input_data, dict):
        input_dict = input_data
    else:
        input_dict = {"input": str(input_data)}

    combined = " ".join(
        str(input_dict.get(k, "")) for k in ("title", "content", "paragraph_latest_state")
    )
    date_range = extract_explicit_date_range(combined)

    criteria = dict(QUERY_SEARCH_CRITERIA)
    if date_range:
        criteria["search_news_by_date"] = (
            f"The requested evidence is explicitly bounded to {date_range[0]} "
            f"through {date_range[1]}."
        )

    result = get_system_one_client().evaluate(
        state={
            "phase": phase,
            "section": input_dict,
            "generated_query": generated_query,
            "available_tools": list(criteria),
        },
        questions={
            "search_tool": {
                "type": "choice",
                "instructions": (
                    "Which single search tool is most likely to retrieve the evidence "
                    "needed for this section? Prefer the basic tool unless a criterion "
                    "for recency, depth, visuals, or an explicit date range is clearly met."
                ),
                "criteria": criteria,
            }
        },
        decision_id=f"query.search_tool.{phase}",
    )
    answer = _answer(result, "search_tool")
    choice = _choice_value(answer)
    confidence = _confidence(answer, choice)
    threshold = _float_env("SYSTEM_ONE_CHOICE_CONFIDENCE", 0.45)

    if not choice or choice not in criteria or confidence < threshold:
        if result is not None:
            logger.info(
                f"System One search routing confidence {confidence:.3f} below "
                f"threshold {threshold:.3f}; preserving LLM/default path"
            )
        return None

    routed: Dict[str, Any] = {
        "search_tool": choice,
        "decision_source": "system_one",
        "system_one_confidence": confidence,
    }
    if choice == "search_news_by_date" and date_range:
        routed["start_date"], routed["end_date"] = date_range
    return routed


def should_continue_research(state: Dict[str, Any]) -> Optional[bool]:
    """Use a Noul probability as an early-stop gate for reflection."""
    result = get_system_one_client().evaluate(
        state=state,
        questions={
            "continue_research": {
                "type": "noul",
                "instructions": (
                    "Would one more targeted web search materially improve the factual "
                    "coverage of this section?"
                ),
                "criteria": {
                    "true": (
                        "There is a clear important evidence gap, unresolved factual "
                        "uncertainty, or missing perspective worth another search."
                    ),
                    "false": (
                        "The current summary already covers the requested scope well "
                        "enough that another search is unlikely to add material value."
                    ),
                },
            }
        },
        decision_id="query.reflection.continue",
    )
    value = _noul_value(_answer(result, "continue_research"))
    if value is None:
        return None

    stop_threshold = _float_env("SYSTEM_ONE_STOP_THRESHOLD", 0.30)
    return False if value < stop_threshold else True


def _report_excerpt(report: Any, limit: int = 1200) -> str:
    if isinstance(report, dict):
        content = report.get("content", str(report))
    elif hasattr(report, "content"):
        content = getattr(report, "content")
    else:
        content = str(report)
    return str(content)[:limit]


def choose_report_template(
    *,
    query: str,
    reports: Sequence[Any],
    forum_logs: str,
    available_templates: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Choose a report template from a finite list; fallback remains the LLM."""
    if not available_templates:
        return None

    criteria: Dict[str, str] = {}
    option_to_template: Dict[str, Dict[str, Any]] = {}
    template_state: List[Dict[str, str]] = []
    for index, template in enumerate(available_templates):
        option = f"template_{index}"
        option_to_template[option] = template
        description = str(template.get("description", "通用报告模板"))
        criteria[option] = (
            f"Use '{template.get('name', option)}' when this description best fits: "
            f"{description}"
        )
        template_state.append(
            {
                "option": option,
                "name": str(template.get("name", option)),
                "description": description,
            }
        )

    result = get_system_one_client().evaluate(
        state={
            "query": query,
            "templates": template_state,
            "report_excerpts": [_report_excerpt(r) for r in reports[:4]],
            "forum_excerpt": (forum_logs or "")[:1200],
        },
        questions={
            "report_template": {
                "type": "choice",
                "instructions": (
                    "Which single report template best matches the user's request and "
                    "the evidence being synthesized?"
                ),
                "criteria": criteria,
            }
        },
        decision_id="report.template",
    )
    answer = _answer(result, "report_template")
    choice = _choice_value(answer)
    confidence = _confidence(answer, choice)
    threshold = _float_env("SYSTEM_ONE_CHOICE_CONFIDENCE", 0.45)

    if not choice or choice not in option_to_template or confidence < threshold:
        return None

    template = option_to_template[choice]
    return {
        "template_name": template["name"],
        "template_content": template["content"],
        "selection_reason": (
            f"System One (Jev) closed-set choice; confidence={confidence:.3f}"
        ),
        "decision_source": "system_one",
        "system_one_confidence": confidence,
    }
