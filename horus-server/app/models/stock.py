from sqlalchemy import Column, Integer, BigInteger, String, Float, Date, Boolean, Text, DateTime, func
from app.core.database import Base

class StockDaily(Base):
    __tablename__ = "stock_daily"

    target_dt = Column(Date, primary_key=True, nullable=False)
    code = Column(String(20), primary_key=True, nullable=False)
    name = Column(String(100), nullable=True)
    open_price = Column(Integer, nullable=True)
    high_price = Column(Integer, nullable=True)
    low_price = Column(Integer, nullable=True)
    close_price = Column(Integer, nullable=True)
    volume = Column(BigInteger, nullable=True)
    individual = Column(BigInteger, nullable=True)
    foreigner = Column(BigInteger, nullable=True)
    institution = Column(BigInteger, nullable=True)
    pension = Column(BigInteger, nullable=True)

class StockClosingTarget(Base):
    __tablename__ = "stock_closing_targets"

    id = Column(Integer, primary_key=True, index=True)
    target_dt = Column(Date, nullable=False, index=True)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    strategy_name = Column(String(50), nullable=False)
    target_score = Column(Float, nullable=True)
    closing_price = Column(Integer, nullable=False)
    next_day_open = Column(Integer, nullable=True)
    next_day_10m_high = Column(Integer, nullable=True)
    next_day_close = Column(Integer, nullable=True)
    return_rate_open = Column(Float, nullable=True)
    return_rate_high = Column(Float, nullable=True)
    is_success = Column(Boolean, nullable=True)
    analysis_report = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
