from sqlalchemy import Column, BigInteger, String, Float, DateTime, func
from app.core.database import Base

class RecoFeedback(Base):
    __tablename__ = "reco_feedbacks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=True)
    article_id = Column(BigInteger, nullable=False, index=True)
    event_type = Column(String(20), nullable=False)  # impression, click
    score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
