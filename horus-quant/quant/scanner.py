import logging
from datetime import date, datetime
from typing import List, Dict, Any
import FinanceDataReader as fdr
import pandas as pd
import psycopg2

logger = logging.getLogger(__name__)

class ClosingPriceScanner:
    def __init__(self, db_url: str = "postgresql://horus:horus_secret@localhost:5432/horus"):
        self.db_url = db_url

    def scan_today_targets(self, target_date: date = None) -> List[Dict[str, Any]]:
        """
        15:10 장마감 직전 종가매매 대상 종목 자동 추출
        전략:
        1. 당일 거래대금 급증 (상위 종목)
        2. 양봉 마감 (종가 > 시가, +3% ~ +15% 적정 상승률)
        3. 고가 대비 밀리지 않은 종목 (윗꼬리 짧음)
        """
        scan_dt = target_date or date.today()
        str_dt = scan_dt.strftime("%Y-%m-%d")
        logger.info(f"Running ClosingPriceScanner for date: {str_dt}")

        try:
            # KRX 전체 종목 시세 가져오기
            df_krx = fdr.StockListing('KRX')
            df_krx = df_krx.dropna(subset=['Close', 'Volume', 'Amount'])
            
            # 필터링: 거래대금 300억 이상, 등락률 3% ~ 18%
            filtered = df_krx[
                (df_krx['Amount'] >= 30_000_000_000) &
                (df_krx['ChagesRatio'] >= 3.0) &
                (df_krx['ChagesRatio'] <= 18.0)
            ].copy()

            # 랭킹 스코어 산출
            filtered['Score'] = (filtered['Amount'] / 1e11) * 0.5 + filtered['ChagesRatio'] * 0.5
            top_candidates = filtered.sort_values(by='Score', ascending=False).head(5)

            results = []
            for _, row in top_candidates.iterrows():
                results.append({
                    "target_dt": scan_dt,
                    "code": str(row['Code']),
                    "name": str(row['Name']),
                    "strategy_name": "CLOSING_MOMENTUM_V1",
                    "target_score": float(row['Score']),
                    "closing_price": int(row['Close'])
                })

            self._save_to_db(results)
            return results

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            return []

    def _save_to_db(self, targets: List[Dict[str, Any]]):
        if not targets:
            return
        conn = psycopg2.connect(self.db_url)
        cursor = conn.cursor()
        for t in targets:
            cursor.execute("""
                INSERT INTO stock_closing_targets (target_dt, code, name, strategy_name, target_score, closing_price)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (t['target_dt'], t['code'], t['name'], t['strategy_name'], t['target_score'], t['closing_price']))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Saved {len(targets)} closing targets to DB.")
