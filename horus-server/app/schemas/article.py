from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ArticleBase(BaseModel):
    title: str
    url: str
    content: str
    summary: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    sentiment_score: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    class Config:
        from_attributes = True
        populate_by_name = True

class ArticleCreate(ArticleBase):
    source_id: Optional[int] = None

class ArticleRead(ArticleBase):
    id: int
    source_id: Optional[int] = None
    crawled_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True

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
