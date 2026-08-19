import logging
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from quant.scanner import ClosingPriceScanner
from quant.backtester import NextDayBacktester

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

scanner = ClosingPriceScanner()
backtester = NextDayBacktester()

def job_scan_closing():
    logger.info("=== Executing 15:10 Closing Price Scan Job ===")
    scanner.scan_today_targets()

def job_verify_nextday():
    logger.info("=== Executing 09:10 Next Day Verification Job ===")
    backtester.verify_previous_targets()

def main():
    logger.info("Starting HorusQuant Scheduler Daemon (BrainStocking 2.0)...")
    
    # 시작 시 1회 즉시 성과 검증 실행
    backtester.verify_previous_targets()

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    
    # 매주 월~금 15:10에 종가매매 추출
    scheduler.add_job(
        job_scan_closing,
        trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=10)
    )
    
    # 매주 월~금 09:10에 전일 성과 검증
    scheduler.add_job(
        job_verify_nextday,
        trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=10)
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("HorusQuant Scheduler stopped.")

if __name__ == "__main__":
    main()
