from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime

class ArticleBase(BaseModel):
    title: str
    url: str
    content: str
    summary: Optional[str] = None
    author: Optional[str] = None
    published_at: datetime
    category: Optional[str] = None
    sentiment_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class ArticleCreate(ArticleBase):
    source_id: Optional[int] = None

class ArticleRead(ArticleBase):
    id: int
    source_id: Optional[int] = None
    crawled_at: datetime

    class Config:
        from_attributes = True

class ArticleSearchResult(BaseModel):
    total: int
    items: List[ArticleRead]

class TermFrequencyRead(BaseModel):
    time: datetime
    term: str
    frequency: int
    doc_count: int

    class Config:
        from_attributes = True
