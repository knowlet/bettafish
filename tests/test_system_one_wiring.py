from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_insight_runtime_uses_system_one_plan_and_stop_gate():
    node = source("InsightEngine/nodes/search_node.py")
    agent = source("InsightEngine/agent.py")
    assert "choose_insight_search_plan" in node
    assert "insight.reflection.continue" in agent
    assert 'search_kwargs["enable_sentiment"]' in agent


def test_keyword_optimizer_has_jev_gate():
    optimizer = source("InsightEngine/tools/keyword_optimizer.py")
    assert "should_expand_insight_keywords" in optimizer
    assert "跳过关键词扩展 LLM" in optimizer


def test_forum_runtime_has_system_one_host_gate():
    monitor = source("ForumEngine/monitor.py")
    assert "decide_forum_host" in monitor
    assert "Jev判定无需主持人介入" in monitor


def test_word_budget_prefers_system_one_before_llm():
    node = source("ReportEngine/nodes/word_budget_node.py")
    jev = node.index("system_one_plan = plan_word_budget")
    llm = node.index("self.llm_client.stream_invoke_to_string")
    assert jev < llm
    assert "回退原 LLM 规划" in node


def test_document_layout_overrides_bounded_framework_flags_with_jev():
    node = source("ReportEngine/nodes/document_layout_node.py")
    assert "apply_layout_controls" in node
    assert "SWOT/PEST章节适用性已由 System One / Jev 判定" in node
