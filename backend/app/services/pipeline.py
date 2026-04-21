from __future__ import annotations

from difflib import SequenceMatcher

from fastapi import HTTPException

from backend.app.models.schemas import AnalyzeRequest, AnalyzeResponse, FollowupRequest, FollowupResponse, WorkItem
from backend.app.services.llm_client import DashScopeClient
from backend.app.services.normalizer import normalize_text
from backend.app.services.time_parser import normalize_time_info


EXTRACTION_SYSTEM_PROMPT = """You extract structured planning events from pasted WeChat chat logs.

Return valid JSON only.
Do not add markdown.
Do not invent missing facts.

Your output is rendered directly by the frontend, so every work item must already be presentation-ready.
Focus only on these fields:
- summary: short Chinese event summary
- details: one-sentence Chinese explanation
- people: directly related people names from the chat
- schedule: structured time object
- status
- priority
- risks
- evidence

Do not put these into work_items:
- greetings
- vague asks
- emotional expressions
- filler such as "推进一点了"
- pure progress acknowledgements such as "okok"

If a person is only mentioned as a possible future dependency, prefer putting that into resource_gaps instead of work_items.
"""

EXTRACTION_USER_PROMPT = """Analyze the chat below and return JSON with exactly these top-level fields:
- summary: string
- work_items: [{{id, summary, details, people, schedule, status, priority, risks, confidence, evidence}}]
- resource_gaps: string[]
- review_flags: string[]

Rules:
1. summary must be a short Chinese event summary, not a copied half sentence.
2. details must explain the actual work in one Chinese sentence.
3. people must preserve names or roles directly tied to the event, for example: 我, 端阳, 奕铭.
4. If time is present, schedule must use this exact shape:
   {{raw_text, normalized_value, range_start, range_end, granularity, relation, is_uncertain, certainty_level}}
5. status must be one of: in_progress, pending, blocked, unknown
6. priority must be one of: high, medium, low
7. If text only says someone may help later, put that in resource_gaps instead of work_items.
8. Do not create work items from greetings, vague questions, or filler.
9. If chat has no clear actionable events, return an empty work_items array.

Examples for this chat style:
- "benchmark and method are connected and are being debugged with scoring" => active work item
- "I am revising the judge prompt" => active work item
- "Duanyang is optimizing the method" => active work item
- "Yiming may need to review the code later" => usually resource gap, unless it is already active now
- "Do you need me to do anything" => not a work item
- "推进一点了" => not a work item

Chat:
{content}
"""

LOW_QUALITY_SUMMARIES = {
    "推进一点了",
    "有没有什么需要我做的",
    "最近怎么样",
    "确认相关事项",
    "推进当前事项",
}

NOISE_MARKERS = (
    "有没有什么需要我做的",
    "最近怎么样",
    "谢谢师兄",
    "推进一点了",
    "okok",
)


class AnalysisPipeline:
    def __init__(self) -> None:
        self.llm_client = DashScopeClient()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        if not self.llm_client.enabled:
            raise HTTPException(status_code=503, detail="模型服务未配置，无法完成分析。")

        normalized = normalize_text(request.raw_text)
        if not normalized.strip():
            raise HTTPException(status_code=422, detail="输入内容不能为空。")

        try:
            result = await self._extract_with_llm(normalized)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"模型服务调用失败：{exc}") from exc

        processed = self._post_process(result, normalized)
        return processed

    async def write_followup(self, request: FollowupRequest) -> FollowupResponse:
        normalized_request = self._post_process_followup(request)
        return FollowupResponse(message=self._render_followup(normalized_request))

    async def _extract_with_llm(self, normalized: str) -> AnalyzeResponse:
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": EXTRACTION_USER_PROMPT.format(content=normalized)},
        ]
        payload = await self.llm_client.json_chat(messages)
        payload = self._normalize_llm_payload(payload)
        return AnalyzeResponse.model_validate(payload)

    @classmethod
    def _normalize_llm_payload(cls, payload: dict) -> dict:
        work_items = payload.get("work_items") or []
        for item in work_items:
            if not isinstance(item, dict):
                continue
            item["confidence"] = cls._normalize_confidence(item.get("confidence"))
            schedule = item.get("schedule")
            if not isinstance(schedule, dict):
                continue
            item["schedule"] = cls._normalize_schedule_dict(schedule)
        return payload

    @staticmethod
    def _normalize_confidence(value) -> float:
        if isinstance(value, (int, float)):
            numeric = float(value)
            return max(0.0, min(1.0, numeric))

        text = str(value or "").strip().lower()
        confidence_map = {
            "high": 0.9,
            "medium": 0.7,
            "low": 0.4,
            "unknown": 0.5,
        }
        return confidence_map.get(text, 0.5)

    @staticmethod
    def _normalize_schedule_dict(schedule: dict) -> dict:
        granularity = str(schedule.get("granularity") or "").strip().lower()
        relation = str(schedule.get("relation") or "").strip().lower()

        granularity_map = {
            "year": "year",
            "month": "month",
            "day": "day",
            "date": "day",
            "hour": "hour",
            "time": "hour",
            "afternoon": "day",
            "morning": "day",
            "evening": "day",
            "noon": "day",
            "workday_end": "day",
            "week": "range",
            "range": "range",
            "period": "range",
            "window": "range",
            "unknown": "unknown",
        }
        relation_map = {
            "deadline": "deadline",
            "due": "deadline",
            "due_time": "deadline",
            "by": "deadline",
            "before": "deadline",
            "start_time": "start_time",
            "start": "start_time",
            "begin": "start_time",
            "kickoff": "start_time",
            "sync_time": "sync_time",
            "sync": "sync_time",
            "follow_up": "sync_time",
            "on": "unknown",
            "at": "unknown",
            "unknown": "unknown",
        }

        schedule["granularity"] = granularity_map.get(granularity, "unknown")
        schedule["relation"] = relation_map.get(relation, "unknown")

        certainty = str(schedule.get("certainty_level") or "").strip().lower()
        if certainty not in {"high", "medium", "low"}:
            schedule["certainty_level"] = "medium"

        return schedule

    def _post_process(self, response: AnalyzeResponse, normalized_text: str) -> AnalyzeResponse:
        cleaned_items: list[WorkItem] = []
        review_flags = list(response.review_flags)

        for index, item in enumerate(response.work_items, start=1):
            item.id = f"w{index}"
            item.summary = self._normalize_summary(item.summary)
            item.details = self._normalize_details(item.details, item.evidence)
            item.people = self._normalize_people(item.people)
            item = self._clean_schedule(item)

            if not self._is_valid_item(item):
                continue

            if item.schedule:
                item.schedule = normalize_time_info(
                    item.schedule.raw_text,
                    context_text=f"{item.summary} {item.details} {item.evidence}",
                    relation=item.schedule.relation,
                )
                if item.schedule and item.schedule.is_uncertain and item.schedule.raw_text:
                    review_flags.append(f"事件“{item.summary}”的时间较模糊：{item.schedule.raw_text}")
            else:
                review_flags.append(f"事件“{item.summary}”缺少明确时间信息。")

            if not item.people:
                review_flags.append(f"事件“{item.summary}”未明确提及具体人员。")

            cleaned_items.append(item)

        response.work_items = self._dedupe_items(cleaned_items)
        response.summary = self._normalize_board_summary(response.summary, response.work_items)
        response.resource_gaps = self._normalize_gap_list(
            self._supplement_resource_gaps(response.resource_gaps, response.work_items, normalized_text)
        )
        response.review_flags = list(dict.fromkeys(review_flags))

        if not response.work_items and not response.resource_gaps and normalized_text.strip():
            response.summary = response.summary or "当前对话以进展同步为主，暂未识别出可稳定抽取的事件。"
            response.review_flags.append("模型未稳定抽取到有效事件，请人工复核。")
            response.review_flags = list(dict.fromkeys(response.review_flags))
        return response

    def _post_process_followup(self, request: FollowupRequest) -> FollowupRequest:
        normalized_items: list[WorkItem] = []
        for index, item in enumerate(request.work_items, start=1):
            item.id = f"w{index}"
            item.summary = self._normalize_summary(item.summary)
            item.details = self._normalize_details(item.details, item.evidence)
            item.people = self._normalize_people(item.people)
            item = self._clean_schedule(item)
            if item.schedule:
                item.schedule = normalize_time_info(
                    item.schedule.raw_text,
                    context_text=f"{item.summary} {item.details} {item.evidence}",
                    relation=item.schedule.relation,
                )
            if self._is_valid_item(item):
                normalized_items.append(item)

        request.work_items = self._dedupe_items(normalized_items)
        request.summary = self._normalize_board_summary(request.summary, request.work_items)
        request.resource_gaps = self._normalize_gap_list(
            self._supplement_resource_gaps(request.resource_gaps, request.work_items, "")
        )
        return request

    @staticmethod
    def _normalize_summary(summary: str) -> str:
        text = (summary or "").strip()
        text = text.replace("judgeprompt", "judge prompt").replace("Judge prompt", "judge prompt")
        return text[:40]

    @staticmethod
    def _normalize_details(details: str, evidence: str) -> str:
        text = (details or "").strip() or (evidence or "").strip()
        text = " ".join(text.split()).strip(" 。")
        if not text:
            return "未提及，待确认。"
        if not text.endswith("。"):
            text = f"{text}。"
        return text

    @staticmethod
    def _normalize_people(people: list[str]) -> list[str]:
        cleaned: list[str] = []
        for person in people:
            value = person.strip()
            if value and value not in cleaned:
                cleaned.append(value)
        return cleaned

    @staticmethod
    def _clean_schedule(item: WorkItem) -> WorkItem:
        if not item.schedule:
            return item
        raw_text = (item.schedule.raw_text or "").strip().lower()
        if raw_text in {"当前进行中", "进行中", "当前", "ongoing", "in progress"}:
            item.schedule = None
        return item

    def _is_valid_item(self, item: WorkItem) -> bool:
        if not item.summary or len(item.summary) < 3:
            return False
        if item.summary in LOW_QUALITY_SUMMARIES:
            return False
        if item.summary.endswith("？") or item.summary.endswith("?"):
            return False
        combined = f"{item.summary} {item.details} {item.evidence}"
        if any(marker in combined for marker in NOISE_MARKERS):
            return False
        return True

    @staticmethod
    def _dedupe_items(items: list[WorkItem]) -> list[WorkItem]:
        result: list[WorkItem] = []
        seen: set[str] = set()
        for item in items:
            key = f"{item.summary}::{item.evidence}".strip()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        for index, item in enumerate(result, start=1):
            item.id = f"w{index}"
        return result

    @staticmethod
    def _supplement_resource_gaps(resource_gaps: list[str], work_items: list[WorkItem], normalized_text: str) -> list[str]:
        collected: list[str] = [gap for gap in resource_gaps if (gap or "").strip()]

        risk_markers = (
            "\u8fd8\u6ca1\u786e\u8ba4",
            "\u8fd8\u6ca1\u5b8c\u5168\u5bf9\u9f50",
            "\u53ef\u80fd\u4f1a\u5f71\u54cd",
            "\u53ef\u80fd\u4f1a\u88ab\u5361\u4f4f",
            "\u4f1a\u88ab\u5361\u4f4f",
            "\u53ef\u80fd\u4f1a\u5ef6\u671f",
            "\u53ef\u80fd\u4f1a\u5361\u4f4f",
            "\u5f71\u54cd\u8054\u8c03\u65f6\u95f4",
            "\u9700\u8981\u540c\u6b65\u7ed3\u679c",
        )
        for line in normalized_text.splitlines():
            text = line.strip()
            if text and any(marker in text for marker in risk_markers):
                collected.append(text)

        return list(dict.fromkeys(collected))

    @staticmethod
    def _normalize_gap_list(resource_gaps: list[str]) -> list[str]:
        cleaned: list[str] = []
        normalized_seen: list[str] = []

        for gap in resource_gaps:
            text = (gap or "").strip().strip("。？！?")
            if not text:
                continue

            candidate = f"{text}。"
            normalized_candidate = AnalysisPipeline._normalize_gap_text(text)

            duplicate_index = None
            for index, existing in enumerate(normalized_seen):
                if AnalysisPipeline._is_similar_gap(normalized_candidate, existing):
                    duplicate_index = index
                    break

            if duplicate_index is None:
                cleaned.append(candidate)
                normalized_seen.append(normalized_candidate)
                continue

            if len(candidate) > len(cleaned[duplicate_index]):
                cleaned[duplicate_index] = candidate
                normalized_seen[duplicate_index] = normalized_candidate

        return cleaned

    @staticmethod
    def _normalize_gap_text(text: str) -> str:
        normalized = text.replace("。", "").replace("？", "").replace("?", "").replace("，", "").replace("、", "").replace(" ", "")
        for marker in ("可能", "会", "将", "直接", "整体", "最终", "需要", "同步结果", "还没", "完全", "今天", "前端", "排期"):
            normalized = normalized.replace(marker, "")
        return normalized

    @staticmethod
    def _is_similar_gap(left: str, right: str) -> bool:
        if not left or not right:
            return False
        if left in right or right in left:
            return True
        return SequenceMatcher(None, left, right).ratio() >= 0.63

    @staticmethod
    def _normalize_board_summary(summary: str, work_items: list[WorkItem]) -> str:
        text = (summary or "").strip()
        if text:
            return text
        if not work_items:
            return "当前对话以进展同步为主，暂未识别出明确事件。"
        names = "、".join(item.summary for item in work_items[:3])
        return f"当前对话主要围绕 {names} 等事件推进。"

    @staticmethod
    def _schedule_display(item: WorkItem) -> str:
        if not item.schedule:
            return "未提及，待确认"
        raw_text = item.schedule.raw_text
        normalized_value = item.schedule.normalized_value
        if raw_text and normalized_value and raw_text != normalized_value:
            return f"{raw_text}（解析为 {normalized_value}）"
        return raw_text or normalized_value or "未提及，待确认"

    def _render_followup(self, request: FollowupRequest) -> str:
        lines: list[str] = []
        if request.summary:
            lines.append(f"当前进展：{request.summary}")

        if request.work_items:
            lines.append("")
            lines.append("当前事件：")
            for index, item in enumerate(request.work_items, start=1):
                people_text = "、".join(item.people) if item.people else "未提及，待确认"
                status_text = item.status.value if hasattr(item.status, "value") else str(item.status)
                lines.append(
                    f"{index}. {item.summary}：{item.details}；人员：{people_text}；时间：{self._schedule_display(item)}；状态：{status_text}。"
                )
        else:
            lines.append("")
            lines.append("当前暂无明确新增事件，现阶段以进展同步为主。")

        if request.resource_gaps:
            lines.append("")
            lines.append("资源缺口 / 风险：")
            for gap in request.resource_gaps:
                lines.append(f"- {gap}")

        return "\n".join(lines).strip()
