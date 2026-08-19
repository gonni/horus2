from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.article import Article
from app.llm.gateway import llm_gateway
from app.schemas.llm import LLMGenerateRequest, LLMGenerateResponse, ArticleAnalysisResponse

router = APIRouter(prefix="/llm", tags=["Hybrid LLM"])

@router.post("/generate", response_model=LLMGenerateResponse)
async def generate_text(payload: LLMGenerateRequest):
    result = await llm_gateway.generate(
        prompt=payload.prompt,
        task_type=payload.task_type,
        system_instruction=payload.system_instruction,
        temperature=payload.temperature,
        force_provider=payload.force_provider
    )
    return LLMGenerateResponse(**result)

@router.post("/analyze-article/{article_id}", response_model=ArticleAnalysisResponse)
async def analyze_article(
    article_id: int,
    db: AsyncSession = Depends(get_db)
):
    query = select(Article).where(Article.id == article_id).limit(1)
    res = await db.execute(query)
    article = res.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    prompt = f"""
다음 뉴스 기사를 분석하여 JSON 형식으로 결과를 출력해주세요.

[제목]: {article.title}
[본문]: {article.content[:2000]}

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "summary": "3줄 요약 내용",
  "sentiment_score": 0.5 (범위 -1.0 ~ 1.0),
  "sentiment_label": "긍정 / 중립 / 부정",
  "key_topics": ["토픽1", "토픽2", "토픽3"],
  "entities": ["엔티티1", "엔티티2"],
  "related_stocks": ["관련 종목명 또는 종목코드"]
}}
"""
    result = await llm_gateway.generate(
        prompt=prompt,
        task_type="realtime_api",
        temperature=0.1
    )

    try:
        parsed = json.loads(result["response_text"].strip("` \n").replace("json\n", ""))
        return ArticleAnalysisResponse(
            article_id=article.id,
            title=article.title,
            summary=parsed.get("summary", ""),
            sentiment_score=parsed.get("sentiment_score", 0.0),
            sentiment_label=parsed.get("sentiment_label", "중립"),
            key_topics=parsed.get("key_topics", []),
            entities=parsed.get("entities", []),
            related_stocks=parsed.get("related_stocks", [])
        )
    except Exception:
        return ArticleAnalysisResponse(
            article_id=article.id,
            title=article.title,
            summary=result["response_text"][:200],
            sentiment_score=0.0,
            sentiment_label="중립",
            key_topics=[],
            entities=[],
            related_stocks=[]
        )
