from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base

class CrawlEvent(Base):
    __tablename__ = "crawl_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("crawl_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # seed_scan, article_ingest, image_ingest, llm_enrich, duplicate_skip, error
    title = Column(String(500), nullable=True)
    url = Column(String(1000), nullable=True)
    image_url = Column(String(1000), nullable=True)
    details = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

