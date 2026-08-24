from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import re

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

    prompt = f"""당신은 금융/뉴스 전문 분석 AI입니다. 아래 기사를 분석하여 반드시 유효한 JSON 형식으로만 응답하세요.

[제목]: {article.title}
[본문]: {article.content[:2000]}

출력 형식 예시:
{{
  "summary": "1. 첫번째 요약 문장\\n2. 두번째 요약 문장\\n3. 세번째 요약 문장",
  "sentiment_score": 0.5,
  "sentiment_label": "긍정",
  "key_topics": ["반도체", "AI", "수출"],
  "entities": ["삼성전자", "SK하이닉스"],
  "related_stocks": ["005930", "000660"]
}}
"""
    try:
        result = await llm_gateway.generate(
            prompt=prompt,
            task_type="realtime_api",
            temperature=0.1
        )
        response_text = result.get("response_text", "").strip()

        # 1. Direct JSON parse or Regex extract
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            parsed = json.loads(response_text)

        return ArticleAnalysisResponse(
            article_id=article.id,
            title=article.title,
            summary=parsed.get("summary") or response_text[:300],
            sentiment_score=float(parsed.get("sentiment_score", 0.0)),
            sentiment_label=str(parsed.get("sentiment_label", "중립")),
            key_topics=parsed.get("key_topics", []),
            entities=parsed.get("entities", []),
            related_stocks=parsed.get("related_stocks", [])
        )
    except Exception as e:
        # Fallback: 로컬 자연어 요약 추출 (LLM 일시 지연 시)
        content_lines = [line.strip() for line in (article.content or "").split("\n") if len(line.strip()) > 15]
        extractive_summary = "\n".join(content_lines[:3]) if content_lines else (article.summary or article.title)
        
        # 키워드 추출 (제목에서 2글자 이상 명사/단어)
        words = [w for w in re.findall(r'[가-힣a-zA-Z0-9]{2,}', article.title) if w not in ["시사", "스페셜", "단독", "종합", "속보", "뉴스", "기자"]]

        return ArticleAnalysisResponse(
            article_id=article.id,
            title=article.title,
            summary=extractive_summary,
            sentiment_score=0.0,
            sentiment_label="중립",
            key_topics=words[:5],
            entities=[],
            related_stocks=[]
        )
