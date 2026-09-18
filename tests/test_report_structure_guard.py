from QueryEngine.nodes.report_structure_node import ReportStructureNode
from utils.report_structure_guard import (
    build_topic_preserving_structure,
    looks_like_refusal,
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def stream_invoke_to_string(self, system_prompt, user_prompt, **kwargs):
        self.calls.append((system_prompt, user_prompt, kwargs))
        return self.responses.pop(0)


def test_refusal_is_detected():
    assert looks_like_refusal("抱歉，我无法协助处理这个请求。")
    assert looks_like_refusal("I cannot assist with that request.")
    assert not looks_like_refusal('[{"title":"A","content":"B"}]')


def test_topic_preserving_fallback_keeps_original_query():
    query = "广州大学城随机捅人"
    structure = build_topic_preserving_structure(query)
    assert len(structure) == 5
    assert all(query in item["title"] for item in structure)
    assert all(query in item["content"] for item in structure)


def test_report_structure_retries_once_after_refusal():
    query = "广州大学城随机捅人"
    llm = FakeLLM([
        "抱歉，我无法协助处理这个请求。",
        '[{"title":"事件核实","content":"核实公开信息与时间线"}]',
    ])
    node = ReportStructureNode(llm, query)
    structure = node.run()

    assert len(llm.calls) == 2
    assert structure == [{"title": "事件核实", "content": "核实公开信息与时间线"}]
    assert "公开信息" in llm.calls[1][1]
    assert query in llm.calls[1][1]


def test_double_refusal_falls_back_without_topic_drift():
    query = "广州大学城随机捅人"
    llm = FakeLLM([
        "抱歉，我无法协助处理这个请求。",
        "抱歉，我不能协助处理这个请求。",
    ])
    node = ReportStructureNode(llm, query)
    structure = node.run()

    assert len(llm.calls) == 2
    assert len(structure) == 5
    assert all(query in item["title"] for item in structure)
    assert not any(item["title"] in {"研究概述", "深度分析"} for item in structure)


def test_malformed_output_falls_back_without_topic_drift():
    query = "广州大学城随机捅人"
    node = ReportStructureNode(FakeLLM([]), query)
    structure = node.process_output("not-json-at-all")

    assert len(structure) == 5
    assert all(query in item["title"] for item in structure)
