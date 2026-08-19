from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, func, Index
from app.core.database import Base

class ArticleImage(Base):
    __tablename__ = "article_images"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, nullable=True, index=True)
    article_url = Column(String(1000), nullable=True)
    image_url = Column(String(1000), nullable=False)
    order_index = Column(Integer, default=1)
    placeholder_token = Column(String(500), nullable=False)
    local_path = Column(String(500), nullable=True)
    status = Column(String(20), default="PENDING", index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    description = Column(Text, nullable=True)
    model_used = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_article_images_status_article", "status", "article_id"),
    )
