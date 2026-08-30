from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class LLMGenerateRequest(BaseModel):
    prompt: str
    task_type: str = "general" # general, extraction, summary, stock_analysis, realtime_api
    system_instruction: Optional[str] = None
    temperature: float = 0.1
    max_tokens: Optional[int] = 1024
    model: Optional[str] = "auto"
    force_provider: Optional[str] = None # ollama, gpu2, gemini, auto

class LLMGenerateResponse(BaseModel):
    provider: str
    model: str
    response_text: str
    usage_metadata: Optional[Dict[str, Any]] = None
    fallback_used: Optional[bool] = False

class LLMModelOption(BaseModel):
    id: str
    name: str
    provider: str
    model: Optional[str] = None
    is_default: Optional[bool] = False
    online: bool = True
    description: Optional[str] = None

class LLMModelsResponse(BaseModel):
    default_model: str
    gpu2_available: bool
    ollama_available: bool
    gemini_available: bool
    options: List[LLMModelOption]

class ArticleAnalysisRequest(BaseModel):
    model: Optional[str] = Field(default="auto", description="분석에 사용할 LLM 모델 ID (auto, gpu2:..., ollama:...)")

class ArticleAnalysisResponse(BaseModel):
    article_id: int
    title: str
    summary: str
    sentiment_score: float
    sentiment_label: str
    key_topics: List[str] = []
    entities: List[str] = []
    related_stocks: List[str] = []
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    fallback_used: Optional[bool] = False
