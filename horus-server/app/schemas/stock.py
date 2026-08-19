from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class StockDailyRead(BaseModel):
    target_dt: date
    code: str
    name: Optional[str] = None
    open_price: Optional[int] = None
    high_price: Optional[int] = None
    low_price: Optional[int] = None
    close_price: Optional[int] = None
    volume: Optional[int] = None
    individual: Optional[int] = None
    foreigner: Optional[int] = None
    institution: Optional[int] = None
    pension: Optional[int] = None

    class Config:
        from_attributes = True

class StockClosingTargetRead(BaseModel):
    id: int
    target_dt: date
    code: str
    name: str
    strategy_name: str
    target_score: Optional[float] = None
    closing_price: int
    next_day_open: Optional[int] = None
    next_day_10m_high: Optional[int] = None
    next_day_close: Optional[int] = None
    return_rate_open: Optional[float] = None
    return_rate_high: Optional[float] = None
    is_success: Optional[bool] = None
    analysis_report: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class QuantStatsRead(BaseModel):
    total_trades: int
    success_trades: int
    win_rate: float
    avg_return_rate_open: float
    avg_return_rate_high: float
