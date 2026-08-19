from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
from datetime import date

from app.core.database import get_db
from app.models.stock import StockDaily, StockClosingTarget
from app.schemas.stock import StockDailyRead, StockClosingTargetRead, QuantStatsRead

router = APIRouter(prefix="/stock", tags=["Stock & Quant"])

@router.get("/daily", response_model=List[StockDailyRead])
async def get_stock_daily(
    code: str = Query("005930", description="종목코드"),
    limit: int = Query(60, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(StockDaily)
        .where(StockDaily.code == code)
        .order_by(desc(StockDaily.target_dt))
        .limit(limit)
    )
    result = await db.execute(query)
    records = result.scalars().all()
    return list(reversed(records))

@router.get("/closing-targets", response_model=List[StockClosingTargetRead])
async def get_closing_targets(
    target_dt: Optional[date] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(StockClosingTarget)
    if target_dt:
        query = query.where(StockClosingTarget.target_dt == target_dt)
    query = query.order_by(desc(StockClosingTarget.target_dt), desc(StockClosingTarget.target_score)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/quant-stats", response_model=QuantStatsRead)
async def get_quant_stats(db: AsyncSession = Depends(get_db)):
    stmt = select(
        func.count(StockClosingTarget.id).label("total"),
        func.count(StockClosingTarget.id).filter(StockClosingTarget.is_success == True).label("success"),
        func.avg(StockClosingTarget.return_rate_open).label("avg_open"),
        func.avg(StockClosingTarget.return_rate_high).label("avg_high")
    )
    res = await db.execute(stmt)
    row = res.one()

    total = row.total or 0
    success = row.success or 0
    win_rate = (success / total * 100) if total > 0 else 0.0

    return QuantStatsRead(
        total_trades=total,
        success_trades=success,
        win_rate=round(win_rate, 2),
        avg_return_rate_open=round(row.avg_open or 0.0, 2),
        avg_return_rate_high=round(row.avg_high or 0.0, 2)
    )
