"""Guards for report-structure generation.

The structure LLM may occasionally refuse or return malformed output even for
benign factual research topics. Never let that failure silently replace the
user's topic with a generic outline.
"""

from __future__ import annotations

from typing import Dict, List


_REFUSAL_MARKERS = (
    "抱歉，我无法协助",
    "抱歉，我不能协助",
    "抱歉，我无法帮助",
    "无法协助处理这个请求",
    "无法帮助处理这个请求",
    "不能协助处理这个请求",
    "i can't assist with",
    "i cannot assist with",
    "i'm unable to assist with",
    "i can’t assist with",
    "i cannot help with",
)


def looks_like_refusal(text: str) -> bool:
    """Return True for common provider/model refusal responses."""
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return False
    return any(marker.lower() in normalized for marker in _REFUSAL_MARKERS)


def build_safe_outline_retry_prompt(query: str) -> str:
    """Clarify the benign scope before one retry after a model refusal."""
    topic = str(query or "").strip()
    return (
        "研究主题：" + topic + "\n\n"
        "这是一个基于公开信息的事实研究／新闻分析任务。你只需要规划报告大纲，"
        "用于后续检索、事实核查与来源交叉验证。不要提供实施伤害、武器使用、"
        "攻击步骤、规避执法或其他操作性危险指导。\n"
        "请始终围绕上述原始研究主题本身，输出最多5个段落的JSON数组；"
        "每个元素只包含 title 与 content。"
    )


def build_topic_preserving_structure(query: str) -> List[Dict[str, str]]:
    """Deterministic fallback that always keeps the original topic in scope."""
    topic = str(query or "").strip() or "用户查询主题"
    return [
        {
            "title": f"{topic}：核心事实与背景",
            "content": (
                f"围绕“{topic}”核实核心事实、基本定义、时间背景与涉及主体；"
                "优先寻找一手资料、官方说明或可直接验证的来源。"
            ),
        },
        {
            "title": f"{topic}：权威来源与发展脉络",
            "content": (
                f"围绕“{topic}”整理权威来源、关键时间点与发展脉络；"
                "区分已确认事实、后续进展与尚未证实的信息。"
            ),
        },
        {
            "title": f"{topic}：多方报道与交叉验证",
            "content": (
                f"比较不同来源对“{topic}”的报道、数据与表述差异，"
                "寻找相互印证、冲突证据与可能的来源依赖。"
            ),
        },
        {
            "title": f"{topic}：争议、传闻与信息缺口",
            "content": (
                f"识别“{topic}”相关争议、传闻、未经证实说法及关键证据缺口，"
                "明确可信度与仍需进一步查证的问题。"
            ),
        },
        {
            "title": f"{topic}：影响、处置与最新进展",
            "content": (
                f"分析“{topic}”的现实影响、相关回应或处置（如适用），"
                "并核实最新公开进展与后续值得持续追踪的事项。"
            ),
        },
    ]
