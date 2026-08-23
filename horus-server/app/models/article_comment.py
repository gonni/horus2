from sqlalchemy import Column, BigInteger, Integer, String, Text, Float, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base

class ArticleComment(Base):
    """
    Reddit 등 수집된 문서(Article)에 달리는 댓글(Comments) 저장 테이블
    """
    __tablename__ = "article_comments"
    __table_args__ = (
        UniqueConstraint("article_id", "comment_ext_id", name="uq_article_comment"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, nullable=False, index=True)
    comment_ext_id = Column(String(100), nullable=False, index=True)  # e.g., t1_k9abc12 or c_wallstreetbets_0_1
    author = Column(String(100), nullable=True)
    content = Column(Text, nullable=False)
    score = Column(Integer, default=0)  # 추천수 / Upvotes
    depth = Column(Integer, default=0)  # 0=댓글, 1=대댓글
    published_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sentiment_score = Column(Float, nullable=True, default=0.0)
    metadata_ = Column("metadata", JSONB, default={})
