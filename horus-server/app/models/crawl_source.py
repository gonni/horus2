from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base

class CrawlSource(Base):
    __tablename__ = "crawl_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=False)
    category = Column(String(50), default="news")
    crawl_interval_minutes = Column(Integer, default=15)
    is_active = Column(Boolean, default=True)
    ai_parsing_hints = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
