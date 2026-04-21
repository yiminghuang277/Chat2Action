from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402
from backend.app.routers.api import pipeline  # noqa: E402


client = TestClient(app)


WECHAT_SAMPLE = (
    "最近是 benchmark 和 method 已经连上了，method 的状态识别在跨数据集的表现还是一般，但是在我们自己的数据集上表现很好，在跑跑分进一步调试。\n"
    "我这边在改 judge prompt，让评分更符合我们要求。我这边暂时还没什么需要做的，可能等评分差不多之后，开始找别的 method 来对比的时候需要奕铭去看下代码，不过现阶段还只能单线程做。\n"
    "端阳那边在优化 method，其实他那边可能也有点难分任务出来。\n"
    "可能得等项目再稍微推进一点了。"
)


def test_analyze_extracts_events_and_people(monkeypatch) -> None:
    async def fake_json_chat(messages):
        return {
            "summary": "当前对话主要围绕调试 benchmark 与 method、优化 judge prompt 和优化 method 展开。",
            "work_items": [
                {
                    "id": "x1",
                    "summary": "调试 benchmark 与 method",
                    "details": "继续调试 benchmark 与 method，并结合跑分结果观察效果表现。",
                    "people": ["我"],
                    "schedule": {
                        "raw_text": "近期",
                        "normalized_value": None,
                        "range_start": None,
                        "range_end": None,
                        "granularity": "unknown",
                        "relation": "unknown",
                        "is_uncertain": True,
                        "certainty_level": "low",
                    },
                    "status": "in_progress",
                    "priority": "medium",
                    "risks": ["跨数据集表现仍需继续验证。"],
                    "confidence": 0.88,
                    "evidence": "最近是 benchmark 和 method 已经连上了，在跑跑分进一步调试。",
                },
                {
                    "id": "x2",
                    "summary": "优化 judge prompt",
                    "details": "调整 judge prompt，使评分结果更符合当前要求。",
                    "people": ["我"],
                    "schedule": None,
                    "status": "in_progress",
                    "priority": "medium",
                    "risks": [],
                    "confidence": 0.9,
                    "evidence": "我这边在改 judge prompt，让评分更符合我们要求。",
                },
                {
                    "id": "x3",
                    "summary": "优化 method",
                    "details": "端阳正在优化 method，但当前阶段可拆分任务较少。",
                    "people": ["端阳"],
                    "schedule": None,
                    "status": "in_progress",
                    "priority": "medium",
                    "risks": ["当前阶段可拆分任务较少。"],
                    "confidence": 0.83,
                    "evidence": "端阳那边在优化 method，其实他那边可能也有点难分任务出来。",
                },
                {
                    "id": "x4",
                    "summary": "推进一点了",
                    "details": "项目得再推进一点。",
                    "people": [],
                    "schedule": None,
                    "status": "pending",
                    "priority": "low",
                    "risks": [],
                    "confidence": 0.3,
                    "evidence": "可能得等项目再稍微推进一点了。",
                },
            ],
            "resource_gaps": ["后续 method 对比阶段可能需要奕铭参与代码查看，但当前尚未形成明确事项。"],
            "review_flags": [],
        }

    monkeypatch.setattr(pipeline.llm_client, "json_chat", fake_json_chat)
    monkeypatch.setattr(type(pipeline.llm_client), "enabled", property(lambda self: True))

    response = client.post(
        "/api/analyze",
        json={"source_type": "wechat", "raw_text": WECHAT_SAMPLE, "language": "zh-CN"},
    )
    assert response.status_code == 200
    data = response.json()
    summaries = [item["summary"] for item in data["work_items"]]
    assert "调试 benchmark 与 method" in summaries
    assert "优化 judge prompt" in summaries
    assert "优化 method" in summaries
    assert "推进一点了" not in summaries
    assert any("端阳" in item["people"] for item in data["work_items"])
    assert any("奕铭" in gap for gap in data["resource_gaps"])


def test_analyze_returns_502_for_invalid_model_output(monkeypatch) -> None:
    async def fake_json_chat(messages):
        return {"summary": "bad", "work_items": [{"summary": 123}]}

    monkeypatch.setattr(pipeline.llm_client, "json_chat", fake_json_chat)
    monkeypatch.setattr(type(pipeline.llm_client), "enabled", property(lambda self: True))

    response = client.post(
        "/api/analyze",
        json={"source_type": "wechat", "raw_text": WECHAT_SAMPLE, "language": "zh-CN"},
    )
    assert response.status_code == 502
    assert "模型服务调用失败" in response.text


def test_followup_uses_people_and_time_fields() -> None:
    payload = {
        "summary": "当前对话主要围绕调试 benchmark 与 method、优化 judge prompt 和优化 method 展开。",
        "work_items": [
            {
                "id": "w1",
                "summary": "优化 judge prompt",
                "details": "调整 judge prompt，使评分结果更符合当前要求。",
                "people": ["我"],
                "schedule": {
                    "raw_text": "近期",
                    "normalized_value": None,
                    "range_start": None,
                    "range_end": None,
                    "granularity": "unknown",
                    "relation": "unknown",
                    "is_uncertain": True,
                    "certainty_level": "low",
                },
                "status": "in_progress",
                "priority": "medium",
                "risks": [],
                "confidence": 0.8,
                "evidence": "我这边在改 judge prompt，让评分更符合我们要求。",
            }
        ],
        "resource_gaps": ["后续 method 对比阶段可能需要奕铭参与代码查看，但当前尚未形成明确事项。"],
        "tone": "formal",
    }
    response = client.post("/api/followup", json=payload)
    assert response.status_code == 200
    message = response.json()["message"]
    assert "优化 judge prompt" in message
    assert "我" in message
    assert "近期" in message
    assert "奕铭" in message


def test_analyze_rejects_empty_text() -> None:
    response = client.post(
        "/api/analyze",
        json={"source_type": "wechat", "raw_text": "   ", "language": "zh-CN"},
    )
    assert response.status_code == 422
