from __future__ import annotations

from fastapi import HTTPException


def heuristic_analyze(*args, **kwargs):  # pragma: no cover
    raise HTTPException(status_code=503, detail="规则 fallback 已移除，请配置模型服务。")
