from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402


client = TestClient(app)


WECHAT_SAMPLE = (
    "我们这周要把支付改版需求收一下。\n"
    "我今天先整理接口变更清单，明天下午给研发。\n"
    "联调可能会延期，测试环境现在还没完全稳定。\n"
    "那测试环境谁来确认最终可用时间？\n"
    "我去找测试同学确认，周三下班前同步。\n"
    "如果接口文档今天出不来，前端排期会卡住。"
)


def test_analyze_returns_work_items_for_task_planning() -> None:
    response = client.post(
        "/api/analyze",
        json={"source_type": "wechat", "raw_text": WECHAT_SAMPLE, "language": "zh-CN"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]
    assert len(data["work_items"]) >= 2
    first_item = data["work_items"][0]
    assert "title" in first_item
    assert "headcount" in first_item
    assert "schedule" in first_item
    assert first_item["headcount"] is not None
    assert first_item["headcount"]["estimated_min"] is None
    assert first_item["headcount"]["estimated_max"] is None
    assert first_item["headcount"]["is_uncertain"] is True
    assert data["resource_gaps"]


def test_unmentioned_fields_stay_uncertain_instead_of_fabricated() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "source_type": "wechat",
            "raw_text": "这个事情尽快推进，具体几个人和谁来做还没定。",
            "language": "zh-CN",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["work_items"]
    item = data["work_items"][0]
    assert item["headcount"]["estimated_min"] is None
    assert item["headcount"]["estimated_max"] is None
    assert item["roles"] == []
    assert item["schedule"]["raw_text"] == "尽快"
    assert item["schedule"]["is_uncertain"] is True


def test_followup_summarizes_work_items_and_headcount() -> None:
    payload = {
        "summary": "当前对话中识别出 2 个待办事项，需要进一步确认资源和排期。",
        "work_items": [
            {
                "id": "w1",
                "title": "整理接口变更清单",
                "description": "整理接口变更清单并发给研发。",
                "headcount": {
                    "raw_text": None,
                    "estimated_min": None,
                    "estimated_max": None,
                    "is_uncertain": True,
                },
                "roles": [],
                "schedule": {
                    "raw_text": "明天下午",
                    "normalized_value": "2026-04-22 15:00",
                    "range_start": "2026-04-22 00:00",
                    "range_end": "2026-04-22 15:00",
                    "granularity": "day",
                    "relation": "deadline",
                    "is_uncertain": False,
                    "certainty_level": "high",
                },
                "priority": "high",
                "risks": ["研发依赖该事项继续推进"],
                "confidence": 0.8,
                "evidence": "我今天先整理接口变更清单，明天下午给研发。",
            }
        ],
        "resource_gaps": ["对话中未明确提及具体人手，需要人工确认。"],
        "tone": "formal",
    }
    response = client.post("/api/followup", json=payload)
    assert response.status_code == 200
    message = response.json()["message"]
    assert "整理接口变更清单" in message
    assert "未提及，待确认" in message
    assert "明天下午" in message
    assert "资源缺口" in message


def test_analyze_rejects_empty_text() -> None:
    response = client.post(
        "/api/analyze",
        json={"source_type": "wechat", "raw_text": "   ", "language": "zh-CN"},
    )
    assert response.status_code == 422
