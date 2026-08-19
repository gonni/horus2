from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.feedback import RecoFeedback
from app.recommender.mab import mab_engine
from app.schemas.article import ArticleRead

router = APIRouter(prefix="/reco", tags=["Recommender & MAB"])

class RecommendedItem(BaseModel):
    article: ArticleRead
    mab_score: float

class FeedbackRequest(BaseModel):
    user_id: Optional[str] = "anonymous"
    article_id: int
    event_type: str # impression, click

@router.get("/pick", response_model=List[RecommendedItem])
async def get_mab_recommendations(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Multi-Armed Bandit (Thompson Sampling) 기반 추천 기사 서빙
    """
    items = await mab_engine.get_recommended_articles(db, limit=limit)
    return [
        RecommendedItem(article=ArticleRead.model_validate(art), mab_score=round(score, 4))
        for art, score in items
    ]

@router.post("/feedback")
async def record_feedback(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    feedback = RecoFeedback(
        user_id=payload.user_id,
        article_id=payload.article_id,
        event_type=payload.event_type,
        score=1.0 if payload.event_type == "click" else 0.0
    )
    db.add(feedback)
    await db.commit()
    return {"status": "success", "event_type": payload.event_type}
