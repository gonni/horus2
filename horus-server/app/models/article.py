from sqlalchemy import Column, BigInteger, Integer, String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base

class Article(Base):
    __tablename__ = "articles"
    __table_args__ = {"postgresql_partition_by": "RANGE (published_at)"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("crawl_sources.id", ondelete="SET NULL"), nullable=True)
    url = Column(String(1000), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)
    published_at = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())
    category = Column(String(50), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    metadata_ = Column("metadata", JSONB, default={})

class TermFrequency(Base):
    __tablename__ = "term_frequencies"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    source_id = Column(Integer, nullable=True)
    term = Column(String(100), primary_key=True, nullable=False)
    frequency = Column(Integer, nullable=False)
    doc_count = Column(Integer, default=1)
