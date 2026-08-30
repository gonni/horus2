from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import re
import logging
from typing import Optional, List

from app.core.database import get_db
from app.models.article import Article
from app.llm.gateway import llm_gateway
from app.schemas.llm import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    ArticleAnalysisRequest,
    ArticleAnalysisResponse,
    LLMModelsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["Hybrid LLM"])

@router.get("/models", response_model=LLMModelsResponse)
async def get_models():
    """
    GPU2 vLLM 및 Local Ollama 가용 모델 목록 및 서버 상태를 반환합니다.
    """
    try:
        data = await llm_gateway.get_available_models()
        return LLMModelsResponse(**data)
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        return LLMModelsResponse(
            default_model="auto",
            gpu2_available=False,
            ollama_available=False,
            gemini_available=False,
            options=[
                {
                    "id": "auto",
                    "name": "Auto (GPU2 우선 → Ollama 자동 폴백)",
                    "provider": "auto",
                    "model": "auto",
                    "is_default": True,
                    "online": False,
                    "description": "서버 상태 확인 불가"
                }
            ]
        )

@router.post("/generate", response_model=LLMGenerateResponse)
async def generate_text(payload: LLMGenerateRequest):
    result = await llm_gateway.generate(
        prompt=payload.prompt,
        task_type=payload.task_type,
        system_instruction=payload.system_instruction,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens or 1024,
        model=payload.model,
        force_provider=payload.force_provider
    )
    return LLMGenerateResponse(**result)

@router.post("/analyze-article/{article_id}", response_model=ArticleAnalysisResponse)
async def analyze_article(
    article_id: int,
    model: Optional[str] = Query(None, description="선택된 모델 ID (auto, gpu2:..., ollama:...)"),
    payload: Optional[ArticleAnalysisRequest] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(Article).where(Article.id == article_id).limit(1)
    res = await db.execute(query)
    article = res.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    target_model = "auto"
    if payload and payload.model:
        target_model = payload.model
    elif model:
        target_model = model

    prompt = f"""당신은 금융/뉴스 전문 분석 AI입니다. 아래 기사를 분석하여 반드시 유효한 JSON 형식으로만 응답하세요.

[제목]: {article.title}
[본문]: {(article.content or article.title)[:2000]}

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
    provider_used = "unknown"
    model_used = target_model
    fallback_used = False

    try:
        result = await llm_gateway.generate(
            prompt=prompt,
            task_type="realtime_api",
            temperature=0.1,
            max_tokens=1024,
            model=target_model
        )
        provider_used = result.get("provider", "unknown")
        model_used = result.get("model", target_model)
        fallback_used = result.get("fallback_used", False)
        response_text = result.get("response_text", "").strip()

        # Clean markdown code blocks if wrapped in ```json ... ```
        if "```" in response_text:
            code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
            if code_block_match:
                response_text = code_block_match.group(1).strip()

        # 1. Direct JSON parse or Regex extract
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            parsed = json.loads(response_text)

        # Sanitize fields
        summary = str(parsed.get("summary") or response_text[:300])
        
        try:
            sentiment_score = float(parsed.get("sentiment_score", 0.0))
        except (ValueError, TypeError):
            sentiment_score = 0.0

        sentiment_label = str(parsed.get("sentiment_label") or "중립")
        
        raw_topics = parsed.get("key_topics", [])
        key_topics = [str(t) for t in raw_topics] if isinstance(raw_topics, list) else []

        raw_entities = parsed.get("entities", [])
        entities = [str(e) for e in raw_entities] if isinstance(raw_entities, list) else []

        raw_stocks = parsed.get("related_stocks", [])
        related_stocks = [str(s) for s in raw_stocks] if isinstance(raw_stocks, list) else []

        return ArticleAnalysisResponse(
            article_id=article.id,
            title=article.title,
            summary=summary,
            sentiment_score=sentiment_score,
            sentiment_label=sentiment_label,
            key_topics=key_topics,
            entities=entities,
            related_stocks=related_stocks,
            model_used=model_used,
            provider_used=provider_used,
            fallback_used=fallback_used
        )
    except Exception as e:
        logger.warning(f"AI Analysis LLM failed or parse error ({e}). Generating fallback summary...")
        
        # Fallback: 로컬 자연어 요약 추출
        content_lines = [line.strip() for line in (article.content or "").split("\n") if len(line.strip()) > 15]
        extractive_summary = "\n".join([f"{i+1}. {line}" for i, line in enumerate(content_lines[:3])]) if content_lines else (article.summary or article.title)
        
        # 키워드 추출 (제목에서 2글자 이상 단어)
        words = [w for w in re.findall(r'[가-힣a-zA-Z0-9]{2,}', article.title) if w not in ["시사", "스페셜", "단독", "종합", "속보", "뉴스", "기자", "게시판"]]

        return ArticleAnalysisResponse(
            article_id=article.id,
            title=article.title,
            summary=extractive_summary,
            sentiment_score=0.0,
            sentiment_label="중립",
            key_topics=words[:5],
            entities=[],
            related_stocks=[],
            model_used=model_used,
            provider_used=provider_used,
            fallback_used=True
        )
