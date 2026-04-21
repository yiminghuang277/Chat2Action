from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from backend.app.models.schemas import AnalyzeResponse, HeadcountInfo, WorkItem
from backend.app.services.normalizer import MessageTurn
from backend.app.services.time_parser import normalize_time_info


TASK_HINTS = ("需要", "整理", "确认", "同步", "补", "收一下", "推进", "给研发", "排期", "处理", "跟进")
TIME_FRAGMENT_PATTERN = re.compile(
    r"(?:\d{4}年\d{1,2}月|\d{4}年|\d{1,2}[/-]\d{1,2}(?:\s*\d{1,2}:\d{1,2})?|今天|明天|后天|下周[一二三四五六日天]?|本周|这周|周[一二三四五六日天](?:下班前|中午前|上午|下午|晚上|前)?|月底前|月底|尽快|近期|下周左右|明天下午|下班前|中午前|上午|下午|晚上)"
)


@dataclass
class HeuristicContext:
    turns: list[MessageTurn]
    today: date


def heuristic_analyze(turns: list[MessageTurn], today: date | None = None) -> AnalyzeResponse:
    ctx = HeuristicContext(turns=turns, today=today or date.today())
    work_items = extract_work_items(ctx)
    resource_gaps = build_resource_gaps(ctx, work_items)
    review_flags = build_review_flags(work_items)
    return AnalyzeResponse(
        summary=f"当前对话中识别出 {len(work_items)} 个待办事项，需要进一步确认资源和排期。",
        work_items=work_items,
        resource_gaps=resource_gaps,
        review_flags=review_flags,
    )


def extract_work_items(ctx: HeuristicContext) -> list[WorkItem]:
    items: list[WorkItem] = []
    seen_titles: set[str] = set()
    for idx, turn in enumerate(ctx.turns, start=1):
        content = turn.content.strip()
        if not any(token in content for token in TASK_HINTS):
            continue
        title = infer_title(content)
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        schedule_raw = extract_time_fragment(content)
        schedule = normalize_time_info(schedule_raw, context_text=content, today=ctx.today) if schedule_raw else None
        items.append(
            WorkItem(
                id=f"w{idx}",
                title=title,
                description=content.rstrip("。"),
                headcount=infer_headcount(content),
                roles=infer_roles(content),
                schedule=schedule,
                priority=infer_priority(content),
                risks=infer_item_risks(content),
                confidence=0.7 if schedule else 0.6,
                evidence=turn.raw,
            )
        )
    return items


def infer_title(text: str) -> str:
    cleaned = text.strip().rstrip("。")
    for prefix in ("我今天先", "我先", "我们这周要把", "我去", "我们需要", "那", "目前待办事项："):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    parts = [part.strip() for part in re.split(r"[，,]", cleaned) if part.strip()]
    return parts[0] if parts else cleaned


def infer_headcount(text: str) -> HeadcountInfo:
    return HeadcountInfo(
        raw_text=None,
        estimated_min=None,
        estimated_max=None,
        is_uncertain=True,
    )


def infer_roles(text: str) -> list[str]:
    roles: list[str] = []
    mapping = {
        "研发": "研发",
        "前端": "前端",
        "测试": "测试",
        "接口文档": "后端",
        "需求": "产品",
    }
    for keyword, role in mapping.items():
        if keyword in text and role not in roles:
            roles.append(role)
    return roles


def infer_priority(text: str) -> str:
    if any(token in text for token in ("今天", "明天", "延期", "卡住")):
        return "high"
    return "medium"


def infer_item_risks(text: str) -> list[str]:
    risks: list[str] = []
    if "研发" in text:
        risks.append("研发依赖该事项继续推进")
    if "测试环境" in text and "稳定" in text:
        risks.append("测试环境稳定性不足")
    if "接口文档" in text and "出不来" in text:
        risks.append("接口文档缺失会影响前端排期")
    return risks


def extract_time_fragment(text: str) -> str | None:
    matches = list(TIME_FRAGMENT_PATTERN.finditer(text))
    if not matches:
        return None
    return matches[-1].group(0)


def build_resource_gaps(ctx: HeuristicContext, work_items: list[WorkItem]) -> list[str]:
    gaps: list[str] = []
    if any("测试环境" in turn.content for turn in ctx.turns):
        gaps.append("测试环境相关事项需要明确责任人和可用时间。")
    if any("接口文档" in turn.content and "出不来" in turn.content for turn in ctx.turns):
        gaps.append("接口文档交付存在风险，可能需要追加后端或产品支持。")
    if any(item.headcount and item.headcount.is_uncertain for item in work_items):
        gaps.append("对话中未明确提及具体人手，需要人工确认。")
    if any(not item.roles for item in work_items):
        gaps.append("部分事项未明确提及建议角色，需要人工补充。")
    if not work_items:
        gaps.append("未能稳定提取待办事项，建议补充更明确的任务表达。")
    return gaps


def build_review_flags(work_items: list[WorkItem]) -> list[str]:
    flags: list[str] = []
    if any(item.schedule is None for item in work_items):
        flags.append("部分事项缺少明确时间信息。")
    if any(item.headcount and item.headcount.is_uncertain for item in work_items):
        flags.append("部分事项的人手需求未在对话中明确提及。")
    if any(not item.roles for item in work_items):
        flags.append("部分事项的建议角色未在对话中明确提及。")
    return flags
