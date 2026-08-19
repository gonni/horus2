from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class LLMGenerateRequest(BaseModel):
    prompt: str
    task_type: str = "general" # general, extraction, summary, stock_analysis, realtime_api
    system_instruction: Optional[str] = None
    temperature: float = 0.2
    max_tokens: Optional[int] = 2048
    force_provider: Optional[str] = None # ollama, gemini, auto

class LLMGenerateResponse(BaseModel):
    provider: str
    model: str
    response_text: str
    usage_metadata: Optional[Dict[str, Any]] = None

class ArticleAnalysisResponse(BaseModel):
    article_id: int
    title: str
    summary: str
    sentiment_score: float
    sentiment_label: str
    key_topics: List[str]
    entities: List[str]
    related_stocks: List[str]
