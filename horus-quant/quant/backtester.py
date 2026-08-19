import logging
from datetime import date, timedelta
import FinanceDataReader as fdr
import psycopg2

logger = logging.getLogger(__name__)

class NextDayBacktester:
    def __init__(self, db_url: str = "postgresql://horus:horus_secret@localhost:5432/horus"):
        self.db_url = db_url

    def verify_previous_targets(self):
        """
        09:10 장 시작 직후 전일 추출 종목의 익일 시초가/고가 성과 검증
        """
        conn = psycopg2.connect(self.db_url)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, target_dt, code, closing_price 
            FROM stock_closing_targets 
            WHERE is_success IS NULL AND target_dt < CURRENT_DATE
            ORDER BY target_dt DESC;
        """)
        pending_targets = cursor.fetchall()

        for row in pending_targets:
            target_id, target_dt, code, close_price = row
            try:
                # 다음 거래일 시세 가져오기
                df = fdr.DataReader(code, start=target_dt)
                if len(df) >= 2:
                    next_day_row = df.iloc[1]
                    next_open = int(next_day_row['Open'])
                    next_high = int(next_day_row['High'])
                    next_close = int(next_day_row['Close'])

                    return_open = ((next_open - close_price) / close_price) * 100
                    return_high = ((next_high - close_price) / close_price) * 100
                    is_success = return_high >= 1.5 # 1.5% 이상 수익 시 성공 판정

                    cursor.execute("""
                        UPDATE stock_closing_targets
                        SET next_day_open = %s,
                            next_day_10m_high = %s,
                            next_day_close = %s,
                            return_rate_open = %s,
                            return_rate_high = %s,
                            is_success = %s
                        WHERE id = %s
                    """, (next_open, next_high, next_close, round(return_open, 2), round(return_high, 2), is_success, target_id))
                    logger.info(f"Verified target #{target_id} ({code}): Return High = {return_high:.2f}%, Success = {is_success}")
            except Exception as e:
                logger.error(f"Failed to verify target #{target_id}: {e}")

        conn.commit()
        cursor.close()
        conn.close()
