from __future__ import annotations

import json
from datetime import date

from backend.app.models.schemas import AnalyzeRequest, AnalyzeResponse, FollowupRequest, FollowupResponse
from backend.app.services.fallback_analyzer import heuristic_analyze
from backend.app.services.llm_client import DashScopeClient
from backend.app.services.normalizer import normalize_text, split_turns
from backend.app.services.time_parser import normalize_time_info


ANALYSIS_SYSTEM_PROMPT = """You analyze pasted WeChat chat logs and convert them into structured task-planning output.
Focus on current work items, headcount, schedule, and resource gaps.
Do not invent facts. If the chat does not mention something clearly, leave it uncertain or empty.
Always return valid JSON."""

ANALYSIS_USER_PROMPT = """Analyze the following WeChat chat text and return JSON with these top-level fields:
- summary: string
- work_items: [{id, title, description, headcount, roles, schedule, priority, risks, confidence, evidence}]
- resource_gaps: string[]
- review_flags: string[]

For each work item:
- title should be a concise task name
- description should explain the concrete requirement
- headcount should include {raw_text, estimated_min, estimated_max, is_uncertain}
- if headcount is not explicit, do not invent a number; return raw_text=null, estimated_min=null, estimated_max=null, is_uncertain=true
- roles should be a list like 产品, 前端, 后端, 测试, 项目经理; if not explicit, return []
- schedule should use the structured time object shape {raw_text, normalized_value, range_start, range_end, granularity, relation, is_uncertain, certainty_level}
- if schedule is vague such as 尽快, 近期, 下周左右, keep it vague and do not fake exact dates
- risks should contain resource or delivery risks tied to this item

Also extract resource_gaps such as:
- unclear ownership
- missing staffing
- blocked dependencies
- unstable schedule

Chat text:
{content}
"""

FOLLOWUP_SYSTEM_PROMPT = """You write concise Chinese planning follow-up messages from structured work items.
Focus on current work items, headcount needs, schedule, and resource gaps.
If something is not mentioned in the chat, say 待确认 instead of inventing details.
Do not use markdown."""

FOLLOWUP_USER_PROMPT = """Generate a {tone_label} Chinese follow-up message from this structured task-planning result.
Requirements:
1. Summarize the current planning status.
2. List work items with schedule and headcount needs.
3. Mention resource gaps clearly.
4. Preserve vague schedule or headcount when the source is vague.
5. Do not fabricate missing roles or staffing.

Structured result:
{content}
"""


class AnalysisPipeline:
    def __init__(self) -> None:
        self.llm_client = DashScopeClient()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        normalized = normalize_text(request.raw_text)
        turns = split_turns(normalized)
        if not self.llm_client.enabled:
            return heuristic_analyze(turns, today=date.today())

        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": ANALYSIS_USER_PROMPT.format(content=normalized)},
        ]
        try:
            payload = await self.llm_client.json_chat(messages)
            result = AnalyzeResponse.model_validate(payload)
            return self._post_process(result)
        except Exception:
            return heuristic_analyze(turns, today=date.today())

    async def write_followup(self, request: FollowupRequest) -> FollowupResponse:
        tone_label = "formal" if request.tone.value == "formal" else "concise"
        normalized_request = self._post_process_followup(request)
        if not self.llm_client.enabled:
            return FollowupResponse(message=self._fallback_followup(normalized_request))

        messages = [
            {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": FOLLOWUP_USER_PROMPT.format(
                    tone_label=tone_label,
                    content=json.dumps(normalized_request.model_dump(mode="json"), ensure_ascii=False, indent=2),
                ),
            },
        ]
        try:
            content = await self.llm_client.chat(messages)
            return FollowupResponse(message=content.strip())
        except Exception:
            return FollowupResponse(message=self._fallback_followup(normalized_request))

    def _post_process(self, response: AnalyzeResponse) -> AnalyzeResponse:
        review_flags = list(response.review_flags)
        for item in response.work_items:
            if item.schedule:
                item.schedule = normalize_time_info(
                    item.schedule.raw_text,
                    context_text=f"{item.title} {item.description} {item.evidence}",
                    relation=item.schedule.relation,
                )
            if item.schedule and item.schedule.is_uncertain:
                review_flags.append(f"事项 {item.id} 的时间较模糊：{item.schedule.raw_text}")
            if item.headcount and item.headcount.is_uncertain:
                review_flags.append(f"事项 {item.id} 的人手需求未明确提及。")
            if not item.roles:
                review_flags.append(f"事项 {item.id} 的建议角色未明确提及。")
        response.review_flags = list(dict.fromkeys(review_flags))
        response.resource_gaps = list(dict.fromkeys(response.resource_gaps))
        return response

    def _post_process_followup(self, request: FollowupRequest) -> FollowupRequest:
        for item in request.work_items:
            if item.schedule:
                item.schedule = normalize_time_info(
                    item.schedule.raw_text,
                    context_text=f"{item.title} {item.description} {item.evidence}",
                    relation=item.schedule.relation,
                )
        return request

    @staticmethod
    def _schedule_display(raw_text: str | None, normalized_value: str | None) -> str:
        if raw_text and normalized_value and raw_text != normalized_value:
            return f"{raw_text} ({normalized_value})"
        return raw_text or normalized_value or "未提及，待确认"

    @staticmethod
    def _headcount_display(raw_text: str | None, estimated_min: int | None, estimated_max: int | None) -> str:
        if raw_text:
            return raw_text
        if estimated_min is None and estimated_max is None:
            return "未提及，待确认"
        if estimated_min == estimated_max:
            return f"{estimated_min}人"
        return f"{estimated_min or 0}-{estimated_max or 0}人"

    def _fallback_followup(self, request: FollowupRequest) -> str:
        lines = ["各位好，基于当前微信讨论，整理后的任务需求与排期如下：", ""]
        if request.summary:
            lines.append(f"概述：{request.summary}")
        if request.work_items:
            lines.append("当前待办：")
            for index, item in enumerate(request.work_items, start=1):
                schedule_text = self._schedule_display(
                    item.schedule.raw_text if item.schedule else None,
                    item.schedule.normalized_value if item.schedule else None,
                )
                headcount_text = self._headcount_display(
                    item.headcount.raw_text if item.headcount else None,
                    item.headcount.estimated_min if item.headcount else None,
                    item.headcount.estimated_max if item.headcount else None,
                )
                role_text = "、".join(item.roles) if item.roles else "未提及，待确认"
                lines.append(
                    f"{index}. {item.title}：{item.description}；预计人手 {headcount_text}；建议角色 {role_text}；时间 {schedule_text}"
                )
        else:
            lines.append("当前待办：暂时无明确事项。")

        if request.resource_gaps:
            lines.append("资源缺口/风险：")
            for gap in request.resource_gaps:
                lines.append(f"- {gap}")

        return "\n".join(lines)
