from fastapi import APIRouter

from backend.app.models.schemas import AnalyzeRequest, AnalyzeResponse, FollowupRequest, FollowupResponse
from backend.app.services.pipeline import AnalysisPipeline


router = APIRouter()
pipeline = AnalysisPipeline()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return await pipeline.analyze(request)


@router.post("/followup", response_model=FollowupResponse)
async def followup(request: FollowupRequest) -> FollowupResponse:
    return await pipeline.write_followup(request)

