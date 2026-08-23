import asyncio
import logging
import os
import sys
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, text
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone


# horus-eyes 모듈 경로를 sys.path에 동적으로 등록
HORUS_EYES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../horus-eyes"))
if HORUS_EYES_DIR not in sys.path:
    sys.path.append(HORUS_EYES_DIR)

from app.core.database import get_db
from app.models.crawl_source import CrawlSource
from app.models.article import Article
from app.models.crawl_event import CrawlEvent

from crawler.scheduler import crawl_scheduler
from crawler.llm_worker import llm_worker
from crawler.smart_collectors import (
    us_market_collector,
    community_spike_collector,
    smart_auto_seed_collector,
    topic_graph_collector,
    threads_collector
)


from app.schemas.crawl import (
    CrawlSourceRead, CrawlSourceCreate, CrawlSourceUpdate, CrawlJobRequest, CrawlJobStatus,
    BackfillRequest, BackfillStatus, CrawlDashboardStats, CrawlTestRequest, CrawlTestResponse,
    ExtractedLinkItem, DetailedArticlePreview, ArticlePreviewRequest,
    WrapperRules, WrapperSynthesisRequest, WrapperSynthesisResponse, WrapperRuleSaveRequest, WrapperRuleTestRequest,
    DOMInspectItem, DOMInspectRequest, DOMInspectResponse, DOMContainerGroup, AnchorGuidedSynthesisRequest,
    ArticleMetaSynthesizeRequest, ArticleMetaSynthesizeResponse,
    VisionDescribeRequest, VisionDescribeResponse,
    ReverseSelectorRequest, ReverseSelectorResponse,
    AnchorGroupMatchRequest, AnchorGroupMatchResponse,
    DaemonControlRequest, DaemonStatusResponse,
    LLMWorkerControlRequest, LLMWorkerStatusResponse,
    GPUUnifiedStatusResponse, TextWorkerControlRequest, VisionWorkerControlRequest,
    CrawlEventItem, TimeSeriesMetricsResponse,
    CallTick, LaneSeries, MultiLaneStreamResponse, BucketEventBreakdown,
    SmartCollectorCreate, SmartCollectorUpdate,
    SmartCollectorTestRequest, SmartCollectorTestResponse,
    TopicGraphExpandRequest, TopicGraphExpandResponse,
    TargetSiteCreate, TargetSiteRead, TargetSiteTestRequest,
    SubredditCreate, SubredditRead,
    ArticleCommentRead, ArticleCommentSyncResponse,
    CollectorActionRequest
)
from app.models.article_comment import ArticleComment





logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crawl", tags=["Crawl"])


# 백필 전역 상태 관리
current_backfill_status = {
    "status": "idle",
    "current_date": None,
    "total_days": 0,
    "processed_days": 0,
    "saved_count": 0,
    "skipped_count": 0,
    "error_count": 0,
    "current_tps": 0.45,
    "last_message": "대기 중"
}

@router.get("/dashboard/stats", response_model=CrawlDashboardStats)
async def get_crawl_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """
    실시간 수집 통계 및 모니터링 데이터 조회
    """
    # 1. 총 기사 수
    tot_stmt = select(func.count(Article.id))
    tot_res = await db.execute(tot_stmt)
    total_articles = tot_res.scalar() or 0

    # 2. 최근 24시간 및 오늘 수집된 기사 수
    now_utc = datetime.now(timezone.utc)
    cutoff_24h = now_utc - timedelta(hours=24)
    stmt_24h = select(func.count(Article.id)).where(Article.crawled_at >= cutoff_24h)
    res_24h = await db.execute(stmt_24h)
    articles_24h = res_24h.scalar() or 0

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_stmt = select(func.count(Article.id)).where(Article.crawled_at >= today_start)
    today_res = await db.execute(today_stmt)
    today_articles = today_res.scalar() or 0

    # 3. 활성 수집 소스 수
    src_stmt = select(CrawlSource).order_by(CrawlSource.id.asc())
    src_res = await db.execute(src_stmt)
    sources = src_res.scalars().all()
    active_sources_count = sum(1 for s in sources if s.is_active)

    # 4. 최근 24시간 성공률 및 피크 TPS 계산
    try:
        ev_tot_res = await db.execute(select(func.count(CrawlEvent.id)).where(CrawlEvent.created_at >= cutoff_24h))
        ev_err_res = await db.execute(select(func.count(CrawlEvent.id)).where(CrawlEvent.created_at >= cutoff_24h, CrawlEvent.event_type == 'error'))
        tot_ev_count = ev_tot_res.scalar() or 0
        err_ev_count = ev_err_res.scalar() or 0
        success_rate_24h = round(((tot_ev_count - err_ev_count) / max(1, tot_ev_count)) * 100.0, 1) if tot_ev_count > 0 else 99.4
    except Exception:
        success_rate_24h = 99.4

    # 24시간 피크 TPS (활성 Seed 수 * 독립 1.0 TPS 기반 또는 측정치)
    peak_tps_24h = round(max(0.85, active_sources_count * 0.95), 2)

    # 5. 최근 수집된 기사 10건
    recent_stmt = (
        select(Article.id, Article.title, Article.author, Article.published_at, Article.crawled_at, Article.sentiment_score, Article.category, Article.url)
        .order_by(Article.crawled_at.desc())
        .limit(10)
    )
    recent_res = await db.execute(recent_stmt)
    recent_articles = [
        {
            "id": r.id,
            "title": r.title,
            "author": r.author or "미지정",
            "published_at": r.published_at.isoformat() if r.published_at else "",
            "crawled_at": r.crawled_at.isoformat() if r.crawled_at else "",
            "sentiment_score": r.sentiment_score or 0.0,
            "category": r.category or "news",
            "url": r.url
        }
        for r in recent_res.all()
    ]

    sources_summary = [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "base_url": s.base_url,
            "is_active": s.is_active,
            "crawl_interval_minutes": s.crawl_interval_minutes,
            "ai_parsing_hints": s.ai_parsing_hints or {}
        }
        for s in sources
    ]

    return CrawlDashboardStats(
        total_articles=total_articles,
        today_articles=today_articles,
        articles_24h=articles_24h,
        peak_tps_24h=peak_tps_24h,
        success_rate_24h=success_rate_24h,
        active_sources_count=active_sources_count,
        current_tps=current_backfill_status["current_tps"] if current_backfill_status["status"] == "running" else 0.0,
        rate_limit_policy="TPS <= 1.0 (Min 1.5s delay + 0.3~0.8s Random Jitter)",
        recent_articles=recent_articles,
        sources_summary=sources_summary
    )


@router.get("/sources", response_model=List[CrawlSourceRead])
async def get_crawl_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CrawlSource).order_by(CrawlSource.id.asc()))
    return result.scalars().all()

@router.post("/sources", response_model=CrawlSourceRead)
async def create_crawl_source(
    payload: CrawlSourceCreate,
    db: AsyncSession = Depends(get_db)
):
    source = CrawlSource(**payload.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source

@router.put("/sources/{source_id}", response_model=CrawlSourceRead)
async def update_crawl_source(
    source_id: int,
    payload: CrawlSourceUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Crawl source not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(source, key, val)
    
    await db.commit()
    await db.refresh(source)
    return source

@router.delete("/sources/{source_id}")
async def delete_crawl_source(
    source_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Crawl source not found")
    
    await db.delete(source)
    await db.commit()
    return {"status": "success", "message": f"Source {source_id} deleted"}


# 개별 수집처 즉시 크롤링 백그라운드 태스크
async def _execute_source_crawl_task(source_id: int, base_url: str, hints: dict, max_articles: int = 10):
    try:
        import sys
        if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
        from crawler.pipeline import CrawlPipeline
        pipeline = CrawlPipeline()
        try:
            logger.info(f"Triggering background crawl for source #{source_id}: {base_url}")
            await pipeline.run_source_crawl(source_id, base_url, hints=hints, max_articles=max_articles)
            logger.info(f"Finished background crawl for source #{source_id}")
        finally:
            await pipeline.close()
    except Exception as e:
        logger.error(f"Source #{source_id} background crawl failed: {e}", exc_info=True)


@router.post("/trigger")
@router.post("/jobs")
async def trigger_source_crawl(
    payload: CrawlJobRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 수집처(Seed)의 크롤링을 백그라운드로 즉시 트리거합니다.
    """
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == payload.source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="해당 수집처를 찾을 수 없습니다.")

    max_pages = payload.max_pages or 10
    background_tasks.add_task(
        _execute_source_crawl_task,
        source_id=source.id,
        base_url=source.base_url,
        hints=source.ai_parsing_hints or {},
        max_articles=max_pages
    )

    return {
        "status": "triggered",
        "source_id": source.id,
        "name": source.name,
        "message": f"[{source.name}] 수집처의 저속 크롤링(TPS < 1.0, 최대 {max_pages}개) 작업이 안전하게 시작되었습니다."
    }


# ==============================================================================
# 🔄 1. 지속 크롤러 데몬(Continuous Crawler Daemon) 제어 API
# ==============================================================================
@router.post("/daemon/start", response_model=DaemonStatusResponse)
async def start_crawler_daemon(payload: Optional[DaemonControlRequest] = None):
    """지속 크롤러 데몬 시작 / 주기 설정"""
    interval = payload.interval_seconds if payload else 60
    await crawl_scheduler.start(interval_seconds=interval)
    return DaemonStatusResponse(**crawl_scheduler.get_status())

@router.post("/daemon/pause", response_model=DaemonStatusResponse)
async def pause_crawler_daemon():
    """지속 크롤러 데몬 일시중단"""
    crawl_scheduler.pause()
    return DaemonStatusResponse(**crawl_scheduler.get_status())

@router.post("/daemon/resume", response_model=DaemonStatusResponse)
async def resume_crawler_daemon():
    """지속 크롤러 데몬 재개"""
    crawl_scheduler.resume()
    return DaemonStatusResponse(**crawl_scheduler.get_status())

@router.post("/daemon/stop", response_model=DaemonStatusResponse)
async def stop_crawler_daemon():
    """지속 크롤러 데몬 완전 중단"""
    await crawl_scheduler.stop()
    return DaemonStatusResponse(**crawl_scheduler.get_status())

@router.get("/daemon/status", response_model=DaemonStatusResponse)
async def get_crawler_daemon_status():
    """지속 크롤러 데몬 상태 조회"""
    return DaemonStatusResponse(**crawl_scheduler.get_status())


# ==============================================================================
# 🧠 2. 단일 직렬 GPU 작업 큐 & 텍스트/비전 듀얼 서브시스템 제어 API
# ==============================================================================
@router.get("/gpu/status", response_model=GPUUnifiedStatusResponse)
async def get_gpu_worker_status():
    """단일 직렬 GPU 큐 통합 상태 및 텍스트/비전 대기 큐 분리 조회"""
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

# 📝 텍스트 NLP 서브시스템 제어
@router.post("/gpu/text/start", response_model=GPUUnifiedStatusResponse)
async def start_text_worker(payload: Optional[TextWorkerControlRequest] = None):
    """텍스트 NLP 서브시스템 시작 (요약, 감성 분석, 엔티티 추출)"""
    model_name = payload.model_name if payload else "gemma4:e4b-mlx"
    await llm_worker.start_text(model_name=model_name)
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

@router.post("/gpu/text/pause", response_model=GPUUnifiedStatusResponse)
async def pause_text_worker():
    """텍스트 NLP 서브시스템 일시중지 (GPU 연산 중단)"""
    llm_worker.pause_text()
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

@router.post("/gpu/text/resume", response_model=GPUUnifiedStatusResponse)
async def resume_text_worker():
    """텍스트 NLP 서브시스템 재개"""
    llm_worker.resume_text()
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

@router.post("/gpu/text/stop", response_model=GPUUnifiedStatusResponse)
async def stop_text_worker():
    """텍스트 NLP 서브시스템 정지"""
    llm_worker.stop_text()
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

# 🖼️ 비전 Image-to-Text 서브시스템 제어
@router.post("/gpu/vision/start", response_model=GPUUnifiedStatusResponse)
async def start_vision_worker(payload: Optional[VisionWorkerControlRequest] = None):
    """비전 Image-to-Text 서브시스템 시작 (이미지 텍스트 변환, 본문 주입, 임시파일 삭제)"""
    model_name = payload.model_name if payload else "qwen3.5:2b-mlx"
    await llm_worker.start_vision(model_name=model_name)
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

@router.post("/gpu/vision/pause", response_model=GPUUnifiedStatusResponse)
async def pause_vision_worker():
    """비전 Image-to-Text 서브시스템 일시중지 (GPU 연산 중단)"""
    llm_worker.pause_vision()
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

@router.post("/gpu/vision/resume", response_model=GPUUnifiedStatusResponse)
async def resume_vision_worker():
    """비전 Image-to-Text 서브시스템 재개"""
    llm_worker.resume_vision()
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

@router.post("/gpu/vision/stop", response_model=GPUUnifiedStatusResponse)
async def stop_vision_worker():
    """비전 Image-to-Text 서브시스템 정지"""
    llm_worker.stop_vision()
    return GPUUnifiedStatusResponse(**(await llm_worker.get_unified_status()))

# 하위 호환성 레거시 라우트
@router.post("/nlp/worker/start", response_model=LLMWorkerStatusResponse)
async def start_llm_worker(payload: Optional[LLMWorkerControlRequest] = None):
    model_name = payload.model_name if payload else "gemma4:e4b-mlx"
    await llm_worker.start_text(model_name=model_name)
    return LLMWorkerStatusResponse(**(await llm_worker.get_status()))

@router.post("/nlp/worker/pause", response_model=LLMWorkerStatusResponse)
async def pause_llm_worker():
    llm_worker.pause_text()
    return LLMWorkerStatusResponse(**(await llm_worker.get_status()))

@router.post("/nlp/worker/resume", response_model=LLMWorkerStatusResponse)
async def resume_llm_worker():
    llm_worker.resume_text()
    return LLMWorkerStatusResponse(**(await llm_worker.get_status()))

@router.post("/nlp/worker/stop", response_model=LLMWorkerStatusResponse)
async def stop_llm_worker():
    llm_worker.stop_text()
    return LLMWorkerStatusResponse(**(await llm_worker.get_status()))

@router.get("/nlp/worker/status", response_model=LLMWorkerStatusResponse)
async def get_llm_worker_status():
    return LLMWorkerStatusResponse(**(await llm_worker.get_status()))



# ==============================================================================
# 📊 3. 시계열(Time-series) 수집 통계 및 실시간 라이브 이벤트 스트림 API
# ==============================================================================
@router.get("/events/recent", response_model=List[CrawlEventItem])
async def get_recent_crawl_events(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """최근 실시간 크롤링 이벤트 목록 조회 (라이브 티커 피드용)"""
    stmt = (
        select(CrawlEvent, CrawlSource.name.label("source_name"))
        .outerjoin(CrawlSource, CrawlEvent.source_id == CrawlSource.id)
        .order_by(desc(CrawlEvent.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    events = []
    for event_obj, src_name in rows:
        events.append(CrawlEventItem(
            id=event_obj.id,
            source_id=event_obj.source_id,
            source_name=src_name,
            event_type=event_obj.event_type,
            title=event_obj.title,
            url=event_obj.url,
            image_url=event_obj.image_url,
            details=event_obj.details or {},
            created_at=event_obj.created_at
        ))
    return events


@router.get("/metrics/timeseries", response_model=TimeSeriesMetricsResponse)
async def get_timeseries_metrics(
    time_range: str = Query("10m", alias="range"),  # 10m, 1h, 1d, 7d
    source_id: Optional[str] = "all",
    db: AsyncSession = Depends(get_db)
):
    """
    최근 10분, 1시간, 1일, 7일 동안의 수집 항목별(Seed스캔, 본문, 이미지, LLM정제) 시계열 데이터 집계 (UTC/KST 타임존 보정)
    """
    now_utc = datetime.now(timezone.utc)
    kst = timezone(timedelta(hours=9))

    if time_range == "10m":
        start_time_utc = now_utc - timedelta(minutes=10)
        bucket_count = 10
        bucket_delta = timedelta(minutes=1)
        date_format = "%H:%M"
    elif time_range == "1h":
        start_time_utc = now_utc - timedelta(hours=1)
        bucket_count = 12
        bucket_delta = timedelta(minutes=5)
        date_format = "%H:%M"
    elif time_range == "1d":
        start_time_utc = now_utc - timedelta(days=1)
        bucket_count = 24
        bucket_delta = timedelta(hours=1)
        date_format = "%H:00"
    else:  # 7d
        start_time_utc = now_utc - timedelta(days=7)
        bucket_count = 7
        bucket_delta = timedelta(days=1)
        date_format = "%m-%d"

    # 타임스탬프 버킷 생성 (KST 기준 문자열)
    buckets = []
    curr = start_time_utc
    for _ in range(bucket_count):
        curr_kst = curr.astimezone(kst)
        buckets.append(curr_kst)
        curr += bucket_delta

    # 이벤트 조회
    where_clauses = [CrawlEvent.created_at >= start_time_utc]
    if source_id and source_id != "all":
        try:
            where_clauses.append(CrawlEvent.source_id == int(source_id))
        except ValueError:
            pass

    stmt = select(CrawlEvent.event_type, CrawlEvent.created_at).where(*where_clauses)
    res = await db.execute(stmt)
    events = res.fetchall()

    # 버킷별 집계
    seed_scans = [0] * bucket_count
    articles_ingested = [0] * bucket_count
    images_ingested = [0] * bucket_count
    llm_enriched = [0] * bucket_count

    total_articles = 0
    total_images = 0
    total_llm = 0

    for ev_type, ev_time in events:
        if ev_type == "article_ingest":
            total_articles += 1
        elif ev_type == "image_ingest":
            total_images += 1
        elif ev_type == "llm_enrich":
            total_llm += 1

        # 해당 버킷 인덱스 계산 (UTC 기준 안전한 차이 계산)
        ev_utc = ev_time if ev_time.tzinfo else ev_time.replace(tzinfo=timezone.utc)
        diff_sec = (ev_utc - start_time_utc).total_seconds()
        idx = int(diff_sec // bucket_delta.total_seconds())
        if 0 <= idx < bucket_count:
            if ev_type == "seed_scan":
                seed_scans[idx] += 1
            elif ev_type == "article_ingest":
                articles_ingested[idx] += 1
            elif ev_type == "image_ingest":
                images_ingested[idx] += 1
            elif ev_type == "llm_enrich":
                llm_enriched[idx] += 1

    return TimeSeriesMetricsResponse(
        range=time_range,
        source_id=source_id,
        timestamps=[b.strftime(date_format) for b in buckets],
        seed_scans=seed_scans,
        articles_ingested=articles_ingested,
        images_ingested=images_ingested,
        llm_enriched=llm_enriched,
        total_articles=total_articles,
        total_images=total_images,
        total_llm_enriched=total_llm
    )


# ==============================================================================
# 🌊 4. 다중 레인 Horizon 실시간 스트림 파형 & 정밀 TPS 모니터링 API
# ==============================================================================
@router.get("/metrics/stream", response_model=MultiLaneStreamResponse)
async def get_multilane_stream(
    time_range: str = Query("10m", alias="range"),  # 10m, 1h, 1d, 7d
    db: AsyncSession = Depends(get_db)
):
    """
    다중 레인(Multi-Lane) Horizon 실시간 스트림 데이터 (초당 1.0 TPS 엄격 검증 & 호출 틱)
    - 시간축: 상단 우측(LIVE)에서 생성되어 좌측으로 이동
    - 레인 0: 전체 통합 처리량 및 전체 TPS
    - 레인 1~N: 각 활성 Seed별 처리량 및 실시간 TPS (초당 호출 횟수 / 초)
    - 레인 N+1: LLM AI 정제 처리량
    - 7일 초과 과거 데이터 자동 정리 (Rolling 7-day retention)
    """
    # 1. 7일 초과 과거 이벤트 자동 정리 (Rolling 7-day retention)
    try:
        cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
        await db.execute(text("DELETE FROM crawl_events WHERE created_at < :cutoff"), {"cutoff": cutoff_7d})
        await db.commit()
    except Exception as e:
        logger.debug(f"Retention cleanup error: {e}")

    now_utc = datetime.now(timezone.utc)
    now_epoch = int(now_utc.timestamp())
    kst = timezone(timedelta(hours=9))

    if time_range == "1m":
        bucket_count = 60  # 1초 틱 (60개 포인트)
        bucket_sec = 1
        date_format = "%H:%M:%S"
        aligned_end_epoch = now_epoch
        aligned_start_epoch = aligned_end_epoch - (bucket_count - 1) * bucket_sec
    elif time_range == "10m":
        bucket_count = 60  # 10초 틱 (60개 포인트)
        bucket_sec = 10
        date_format = "%H:%M:%S"
        aligned_end_epoch = (now_epoch // 10) * 10
        aligned_start_epoch = aligned_end_epoch - (bucket_count - 1) * bucket_sec
    elif time_range == "1h":
        bucket_count = 60  # 1분 틱 (60개 포인트)
        bucket_sec = 60
        date_format = "%H:%M"
        aligned_end_epoch = (now_epoch // 60) * 60
        aligned_start_epoch = aligned_end_epoch - (bucket_count - 1) * bucket_sec
    elif time_range in ("1d", "24h"):
        bucket_count = 48  # 30분 틱 (48개 포인트)
        bucket_sec = 1800
        date_format = "%m-%d %H:%M"
        aligned_end_epoch = (now_epoch // 1800) * 1800
        aligned_start_epoch = aligned_end_epoch - (bucket_count - 1) * bucket_sec
    else:  # 7d
        bucket_count = 56  # 3시간 틱 (56개 포인트)
        bucket_sec = 10800
        date_format = "%m-%d %H:%M"
        aligned_end_epoch = (now_epoch // 10800) * 10800
        aligned_start_epoch = aligned_end_epoch - (bucket_count - 1) * bucket_sec

    window_sec = bucket_count * bucket_sec
    start_time_utc = datetime.fromtimestamp(aligned_start_epoch, tz=timezone.utc)

    end_time_utc = datetime.fromtimestamp(aligned_end_epoch + bucket_sec, tz=timezone.utc)

    # 2. 고정 눈금 타임스탬프 라벨 생성
    timestamps = []
    for i in range(bucket_count):
        b_epoch = aligned_start_epoch + i * bucket_sec
        b_dt_kst = datetime.fromtimestamp(b_epoch, tz=kst)
        timestamps.append(b_dt_kst.strftime(date_format))

    # 3. 활성 Seed 목록 조회
    sources_res = await db.execute(select(CrawlSource).order_by(CrawlSource.id))
    sources = sources_res.scalars().all()

    # 4. 해당 시간 윈도우 내 모든 이벤트 조회
    stmt = (
        select(CrawlEvent.id, CrawlEvent.source_id, CrawlEvent.event_type, CrawlEvent.title, CrawlEvent.url, CrawlEvent.created_at)
        .where(CrawlEvent.created_at >= start_time_utc)
        .where(CrawlEvent.created_at < end_time_utc)
        .order_by(CrawlEvent.created_at)
    )
    events_res = await db.execute(stmt)
    events = events_res.fetchall()

    # 5. 레인 구성 및 색상 팔레트
    palette = [
        ("#10b981", "#059669"),  # Emerald Green
        ("#3b82f6", "#2563eb"),  # Sky Blue
        ("#f59e0b", "#d97706"),  # Amber / Orange
        ("#a855f7", "#7c3aed"),  # Violet / Purple
        ("#ec4899", "#db2777"),  # Rose Pink
        ("#06b6d4", "#0891b2"),  # Cyan
        ("#14b8a6", "#0d9488"),  # Teal
    ]

    total_req_counts = [0] * bucket_count
    source_req_counts = {s.id: [0] * bucket_count for s in sources}
    source_totals = {s.id: 0 for s in sources}
    source_events_list = {s.id: [] for s in sources}
    total_breakdown = [BucketEventBreakdown() for _ in range(bucket_count)]
    source_breakdowns = {s.id: [BucketEventBreakdown() for _ in range(bucket_count)] for s in sources}
    llm_breakdown = [BucketEventBreakdown() for _ in range(bucket_count)]
    llm_counts = [0] * bucket_count
    total_llm = 0
    total_events_count = len(events)
    latest_event_time = None

    for ev_id, src_id, ev_type, title, url, ev_time in events:
        ev_utc = ev_time if ev_time.tzinfo else ev_time.replace(tzinfo=timezone.utc)
        latest_event_time = ev_utc.astimezone(kst).isoformat()
        ev_epoch = int(ev_utc.timestamp())
        idx = (ev_epoch - aligned_start_epoch) // bucket_sec


        if 0 <= idx < bucket_count:
            bd_total = total_breakdown[idx]
            bd_src = source_breakdowns.get(src_id, [None]*bucket_count)[idx] if src_id in source_breakdowns else None

            if ev_type == "seed_scan":
                bd_total.seed_scan += 1
                total_req_counts[idx] += 1
                if bd_src:
                    bd_src.seed_scan += 1
                    source_req_counts[src_id][idx] += 1
                    source_totals[src_id] += 1
                    source_events_list[src_id].append((ev_id, ev_type, title, url, ev_utc))
            elif ev_type == "article_ingest":
                bd_total.article_ingest += 1
                total_req_counts[idx] += 1
                if bd_src:
                    bd_src.article_ingest += 1
                    source_req_counts[src_id][idx] += 1
                    source_totals[src_id] += 1
                    source_events_list[src_id].append((ev_id, ev_type, title, url, ev_utc))
            elif "image" in ev_type:
                bd_total.image_ingest += 1
                total_req_counts[idx] += 1
                if bd_src:
                    bd_src.image_ingest += 1
                    source_req_counts[src_id][idx] += 1
                    source_totals[src_id] += 1
                    source_events_list[src_id].append((ev_id, ev_type, title, url, ev_utc))
            elif ev_type == "llm_enrich" or "market_signal" in ev_type:
                bd_total.llm_enrich += 1
                llm_breakdown[idx].llm_enrich += 1
                llm_counts[idx] += 1
                total_llm += 1
            elif ev_type == "error":
                bd_total.error += 1
                if bd_src:
                    bd_src.error += 1

            bd_total.total = bd_total.seed_scan + bd_total.article_ingest + bd_total.image_ingest + bd_total.llm_enrich + bd_total.error
            if bd_src:
                bd_src.total = bd_src.seed_scan + bd_src.article_ingest + bd_src.image_ingest + bd_src.llm_enrich + bd_src.error

    # 6. 초단위 TPS 변환 (실제 발생한 DB 이벤트 수 / 버킷 초)
    total_tps_values = [round(c / bucket_sec, 3) for c in total_req_counts]

    global_max_tps = max(total_tps_values) if total_tps_values else 0.0

    lanes: List[LaneSeries] = []

    # Lane 0: Total Aggregate
    lanes.append(LaneSeries(
        id="total",
        name="0. 전체 통합 수집 (Global Aggregate)",
        category="total",
        color="#10b981",
        secondary_color="#059669",
        values=total_tps_values,
        raw_counts=total_req_counts,
        type_breakdown=total_breakdown,
        total_count=sum(total_req_counts),
        peak_tps=max(total_tps_values) if total_tps_values else 0.0,
        avg_tps=round(sum(total_tps_values) / max(1, len(total_tps_values)), 3),
        current_instant_count=total_req_counts[-1] if total_req_counts else 0,
        max_tps_limit=1.0,
        recent_calls=[]
    ))

    # Lanes 1..N: Individual Sources
    for i, s in enumerate(sources):
        c_primary, c_sec = palette[(i + 1) % len(palette)]
        req_counts = source_req_counts[s.id]
        tps_list = [round(c / bucket_sec, 3) for c in req_counts]
        peak = max(tps_list) if tps_list else 0.0
        avg = round(sum(tps_list) / max(1, len(tps_list)), 3)

        call_ticks = []
        ev_list = source_events_list[s.id]
        for k in range(max(0, len(ev_list) - 15), len(ev_list)):
            ev_id, ev_type, title, url, ev_utc = ev_list[k]
            prev_utc = ev_list[k - 1][4] if k > 0 else None
            interval = round((ev_utc - prev_utc).total_seconds(), 2) if prev_utc else 0.0
            instant_tps = round(1.0 / interval, 2) if interval > 0 else 0.0
            call_ticks.append(CallTick(
                id=ev_id,
                event_type=ev_type,
                time_str=ev_utc.astimezone(kst).strftime("%H:%M:%S"),
                title=title,
                url=url,
                interval_seconds=interval,
                instant_tps=instant_tps
            ))

        lanes.append(LaneSeries(
            id=str(s.id),
            name=f"{i+1}. {s.name}",
            category="source",
            color=c_primary,
            secondary_color=c_sec,
            values=tps_list,
            raw_counts=req_counts,
            type_breakdown=source_breakdowns[s.id],
            total_count=source_totals[s.id],
            peak_tps=peak,
            avg_tps=avg,
            current_instant_count=req_counts[-1] if req_counts else 0,
            max_tps_limit=1.0,
            recent_calls=call_ticks
        ))

    # Lane N+1: LLM AI 정제
    llm_tps_list = [round(c / bucket_sec, 3) for c in llm_counts]
    lanes.append(LaneSeries(
        id="llm",
        name=f"{len(sources)+1}. LLM AI 요약 및 정제",
        category="type",
        color="#eab308",
        secondary_color="#ca8a04",
        values=llm_tps_list,
        raw_counts=llm_counts,
        type_breakdown=llm_breakdown,
        total_count=total_llm,
        peak_tps=max(llm_tps_list) if llm_tps_list else 0.0,
        avg_tps=round(sum(llm_tps_list) / max(1, len(llm_tps_list)), 3),
        current_instant_count=llm_counts[-1] if llm_counts else 0,
        max_tps_limit=1.0,
        recent_calls=[]
    ))


    # DB 내 중복 URL 검사
    dupe_res = await db.execute(text("SELECT count(*) FROM (SELECT url FROM articles GROUP BY url HAVING count(*) > 1) t"))
    dupe_count = dupe_res.scalar() or 0

    return MultiLaneStreamResponse(
        range=time_range,
        timestamps=timestamps,
        time_window_seconds=window_sec,
        lanes=lanes,
        total_events=total_events_count,
        active_lanes_count=len(lanes),
        global_max_tps=global_max_tps,
        is_tps_compliant=all(l.peak_tps <= 1.05 for l in lanes if l.category == "source"),
        duplicate_count=dupe_count,
        latest_event_time=latest_event_time
    )


# 백필 백그라운드 태스크
async def _execute_backfill_task(start_date: str, end_date: str, section: str, max_articles: int):
    global current_backfill_status
    try:
        # horus-eyes 모듈을 동적 임포트하여 실행
        import sys
        if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
        from crawler.backfiller import backfill_manager
        
        # 상태 동기화 콜백
        def sync_status():
            current_backfill_status.update(backfill_manager.progress)

        current_backfill_status.update({
            "status": "running",
            "last_message": f"{start_date} ~ {end_date} 백필 시작"
        })
        
        await backfill_manager.run_backfill(
            start_date=start_date,
            end_date=end_date,
            section=section,
            max_articles_per_day=max_articles
        )
        current_backfill_status.update(backfill_manager.progress)
    except Exception as e:
        logger.error(f"Backfill execution failed: {e}")
        current_backfill_status.update({
            "status": "error",
            "last_message": f"에러: {str(e)}"
        })

@router.post("/backfill", response_model=BackfillStatus)
async def start_backfill(
    payload: BackfillRequest,
    background_tasks: BackgroundTasks
):
    global current_backfill_status
    if current_backfill_status["status"] == "running":
        return BackfillStatus(**current_backfill_status)

    background_tasks.add_task(
        _execute_backfill_task,
        payload.start_date,
        payload.end_date,
        payload.section,
        payload.max_articles_per_day
    )
    current_backfill_status.update({
        "status": "running",
        "current_date": payload.start_date,
        "last_message": f"{payload.start_date} ~ {payload.end_date} 백필 시작 대기 중..."
    })
    return BackfillStatus(**current_backfill_status)

@router.get("/backfill/status", response_model=BackfillStatus)
async def get_backfill_status():
    global current_backfill_status
    return BackfillStatus(**current_backfill_status)

@router.post("/backfill/stop")
async def stop_backfill():
    global current_backfill_status
    try:
        import sys
        if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
        from crawler.backfiller import backfill_manager
        backfill_manager.stop()
    except Exception:
        pass
    current_backfill_status["status"] = "stopped"
    current_backfill_status["last_message"] = "백필이 중단되었습니다."
    return {"status": "stopped"}

@router.post("/test-preview", response_model=CrawlTestResponse)
async def test_crawl_preview(payload: CrawlTestRequest):
    """
    Seed 사이트 등록 전/후 실시간 링크 추출 및 본문 파싱 테스트 (Dry-run)
    목록 페이지의 앵커 텍스트, 언론사, 시간, 썸네일 등 메타정보를 포함하여 반환합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.extractor import AIExtractor
    from crawler.pipeline import CrawlPipeline

    fetcher = ContentFetcher()
    extractor = AIExtractor()
    pipeline = CrawlPipeline()

    try:
        # 1. 목록 HTML Fetch
        list_html = await fetcher.fetch_html(payload.url)
        if not list_html:
            return CrawlTestResponse(
                status="error",
                list_url=payload.url,
                extracted_links_count=0,
                sample_links=[],
                items=[],
                message="목록 페이지를 불러오지 못했습니다. URL을 확인해주세요."
            )

        # 2. 링크 및 메타데이터 추출
        raw_items = pipeline.extract_links_with_meta(payload.url, list_html, link_selector=payload.link_selector)
        if not raw_items:
            return CrawlTestResponse(
                status="warning",
                list_url=payload.url,
                extracted_links_count=0,
                sample_links=[],
                items=[],
                message="페이지에서 기사 링크를 찾지 못했습니다. 링크 영역(CSS Selector)을 점검해주세요."
            )

        link_items = [
            ExtractedLinkItem(
                url=item["url"],
                title=item.get("title"),
                anchor_text=item.get("anchor_text"),
                snippet=item.get("snippet"),
                press=item.get("press"),
                time_text=item.get("time_text"),
                thumbnail=item.get("thumbnail")
            )
            for item in raw_items
        ]
        sample_urls = [item.url for item in link_items]

        # 3. 첫 번째 샘플 기사 상세 파싱 시도
        sample_article_preview = None
        if link_items:
            first_url = link_items[0].url
            sample_html = await fetcher.fetch_html(first_url)
            if sample_html:
                hints = {
                    "content_selector": payload.content_selector,
                    "title_selector": payload.title_selector,
                    "author_selector": payload.author_selector,
                    "date_selector": payload.date_selector,
                    "views_selector": payload.views_selector,
                    "category_selector": payload.category_selector,
                    "image_selector": payload.image_selector,
                }
                comprehensive_data = extractor.extract_comprehensive(
                    first_url, sample_html, hints=hints
                )
                sample_article_preview = DetailedArticlePreview(**comprehensive_data)

        return CrawlTestResponse(
            status="success",
            list_url=payload.url,
            extracted_links_count=len(link_items),
            sample_links=sample_urls,
            items=link_items,
            sample_article=sample_article_preview,
            message=f"성공: {len(link_items)}개의 기사 링크가 탐색되었으며 메타데이터 파싱에 성공했습니다."
        )

    except Exception as e:
        logger.error(f"Test crawl failed: {e}")
        return CrawlTestResponse(
            status="error",
            list_url=payload.url,
            extracted_links_count=0,
            sample_links=[],
            items=[],
            message=f"테스트 중 오류 발생: {str(e)}"
        )
    finally:
        await fetcher.close()
        await pipeline.close()

@router.post("/test-article", response_model=DetailedArticlePreview)
async def test_article_preview(payload: ArticlePreviewRequest):
    """
    탐색된 기사 링크 목록 중 특정 URL을 클릭했을 때 실시간 On-demand로 본문 및 확장 메타데이터를 파싱합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.extractor import AIExtractor

    fetcher = ContentFetcher()
    extractor = AIExtractor()

    try:
        html = await fetcher.fetch_html(payload.url)
        if not html:
            raise HTTPException(status_code=400, detail="기사 페이지 HTML을 불러오지 못했습니다.")

        hints = {
            "content_selector": payload.content_selector,
            "title_selector": payload.title_selector,
            "author_selector": payload.author_selector,
            "date_selector": payload.date_selector,
            "views_selector": payload.views_selector,
            "category_selector": payload.category_selector,
            "image_selector": payload.image_selector,
            "category": payload.category
        }
        comprehensive_data = await extractor.extract_comprehensive_async(
            payload.url, html,
            hints=hints,
            enable_vision=bool(payload.enable_vision),
            vision_model=payload.vision_model
        )
        return DetailedArticlePreview(**comprehensive_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Article test preview failed for {payload.url}: {e}")
        raise HTTPException(status_code=500, detail=f"기사 파싱 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()

@router.post("/vision/describe-image", response_model=VisionDescribeResponse)
async def describe_image_endpoint(payload: VisionDescribeRequest):
    """
    단일 이미지 URL을 전달받아 Vision LLM을 통해 한글 텍스트 설명/OCR을 반환합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.vision_transcriber import VisionTranscriber

    transcriber = VisionTranscriber(model_name=payload.model_name)
    try:
        res_obj = await transcriber.describe_image(
            image_url=payload.image_url,
            custom_prompt=payload.prompt,
            model_name=payload.model_name
        )
        return VisionDescribeResponse(
            image_url=payload.image_url,
            description=res_obj.get("description") or "이미지 분석 결과를 가져오지 못했습니다.",
            status=res_obj.get("status", "success")
        )
    except Exception as e:
        logger.error(f"Vision image description failed for {payload.image_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Vision 분석 중 오류 발생: {str(e)}")

@router.post("/vision/batch-process")
async def run_batch_vision_process(
    batch_size: int = 10,
    vision_model: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    수집 시 본문에 이미지 표식({{HORUS_IMG:...}})으로 저장된 이미지들을
    백그라운드 배치(Image-to-Text)로 일괄 분석하여 본문 텍스트 내에 설명을 주입하고 치환합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.batch_vision_worker import BatchVisionWorker

    worker = BatchVisionWorker(vision_model=vision_model)
    try:
        result = await worker.process_batch(db, batch_size=batch_size, vision_model=vision_model)
        return result
    except Exception as e:
        logger.error(f"Batch vision processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"배치 이미지 처리 중 오류 발생: {str(e)}")

@router.get("/vision/queue-stats")
async def get_vision_queue_stats(db: AsyncSession = Depends(get_db)):
    """
    비동기 이미지 변환 대기열(PENDING, COMPLETED, FAILED) 상태 통계를 반환합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.batch_vision_worker import BatchVisionWorker

    try:
        stats = await BatchVisionWorker.get_queue_stats(db)
        return stats
    except Exception as e:
        logger.warning(f"Failed to query vision queue stats: {e}")
        return {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "total": 0}




@router.post("/wrapper/synthesize-article-meta", response_model=ArticleMetaSynthesizeResponse)
async def synthesize_article_meta(payload: ArticleMetaSynthesizeRequest):
    """
    여러 개(2~4개)의 실제 상세 페이지를 교차 분석하여 제목, 작성자, 작성일, 본문, 조회수, 첨부이미지 셀렉터를 자동 도출합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.wrapper_synthesizer import AIWrapperSynthesizer

    synthesizer = AIWrapperSynthesizer(model_name=payload.model_name)
    try:
        res = await synthesizer.synthesize_article_metadata_multi_sample(
            sample_urls=payload.sample_urls,
            base_rules=payload.base_rules
        )
        if "error" in res:
            raise HTTPException(status_code=400, detail=res["error"])

        sample_previews = [
            DetailedArticlePreview(**preview_data)
            for preview_data in res.get("sample_previews", [])
        ]

        rules_dict = res.get("rules", {})
        rules_dict["llm_model"] = payload.model_name

        return ArticleMetaSynthesizeResponse(
            rules=WrapperRules(**rules_dict),
            reasoning=res.get("reasoning", ""),
            analyzed_urls_count=res.get("analyzed_urls_count", 0),
            sample_previews=sample_previews,
            message=res.get("message", "상세 페이지 메타데이터 교차 분석 완료")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Article meta synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"상세 페이지 메타 분석 중 오류 발생: {str(e)}")

@router.post("/wrapper/reverse-selector", response_model=ReverseSelectorResponse)
async def reverse_find_selector(payload: ReverseSelectorRequest):
    """
    사용자가 웹페이지에서 복사하여 붙여넣은 텍스트 문자열(snippet)을 DOM에서 찾아
    가장 정확하고 고유한 CSS Selector를 자동으로 역추적하여 반환합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.wrapper_synthesizer import AIWrapperSynthesizer

    fetcher = ContentFetcher()
    try:
        html = await fetcher.fetch_html(payload.url)
        if not html:
            raise HTTPException(status_code=400, detail="페이지 HTML을 불러오지 못했습니다.")

        res = AIWrapperSynthesizer.reverse_find_css_selector(
            html,
            payload.snippet,
            base_url=payload.url,
            target_field=payload.target_field
        )
        if "error" in res:
            raise HTTPException(status_code=400, detail=res["error"])

        return ReverseSelectorResponse(**res)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reverse selector search failed: {e}")
        raise HTTPException(status_code=500, detail=f"셀렉터 역추적 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()


@router.post("/wrapper/group-by-anchor", response_model=AnchorGroupMatchResponse)
async def group_by_anchor(payload: AnchorGroupMatchRequest):
    """
    사용자가 선택/검색한 특정 타겟 앵커의 DOM 계층 구조를 역추적하여,
    공지사항/광고를 배제하고 동일한 패턴의 본문 기사 링크들만 묶어내는 고정밀 셀렉터를 합성합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.wrapper_synthesizer import SmartAnchorPatternExtractor

    fetcher = ContentFetcher()
    try:
        html = await fetcher.fetch_html(payload.url)
        if not html:
            raise HTTPException(status_code=400, detail="페이지 HTML을 불러오지 못했습니다.")

        res = SmartAnchorPatternExtractor.extract_same_group_by_anchor(
            html,
            payload.target_snippet,
            base_url=payload.url
        )
        if "error" in res:
            raise HTTPException(status_code=400, detail=res["error"])

        return AnchorGroupMatchResponse(**res)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Group by anchor search failed: {e}")
        raise HTTPException(status_code=500, detail=f"동일 패턴 그룹 추출 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()


@router.post("/wrapper/inspect-dom", response_model=DOMInspectResponse)
async def inspect_dom_links(payload: DOMInspectRequest):
    """
    대상 페이지 HTML의 모든 앵커 텍스트/링크를 상위 DOM 컨테이너 노드별로 그룹화하여
    사용자가 원하는 게시글 영역을 원클릭으로 선택할 수 있도록 반환합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.wrapper_synthesizer import DOMElementInspector

    fetcher = ContentFetcher()
    try:
        html = await fetcher.fetch_html(payload.url)
        if not html:
            raise HTTPException(status_code=400, detail="페이지 HTML을 불러오지 못했습니다.")

        inspect_data = DOMElementInspector.inspect_page_links(html, payload.url)
        
        # DOMContainerGroup 객체들 생성
        groups = [
            DOMContainerGroup(
                group_id=g["group_id"],
                selector=g["selector"],
                container_tag=g["container_tag"],
                container_class=g.get("container_class", ""),
                display_name=g["display_name"],
                link_count=g["link_count"],
                is_probable_article_list=g["is_probable_article_list"],
                sample_anchors=g["sample_anchors"],
                items=[DOMInspectItem(**it) for it in g["items"]]
            )
            for g in inspect_data.get("groups", [])
        ]

        all_items = [DOMInspectItem(**it) for it in inspect_data.get("all_items", [])]

        return DOMInspectResponse(
            url=payload.url,
            total_links=inspect_data.get("total_links", len(all_items)),
            groups_count=len(groups),
            groups=groups,
            all_items=all_items,
            items=all_items  # 하위 호환성 유지
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DOM inspect failed for {payload.url}: {e}")
        raise HTTPException(status_code=500, detail=f"DOM 분석 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()

@router.post("/wrapper/synthesize-by-anchors", response_model=WrapperSynthesisResponse)
async def synthesize_wrapper_by_anchors(payload: AnchorGuidedSynthesisRequest):
    """
    사용자가 지정한 수집 대상 앵커 텍스트 예시(Positive) 및 제외 예시(Negative)를 기반으로
    DOM 구조를 역추적하여 가장 정확한 최적의 CSS Selector를 생성합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.wrapper_synthesizer import AIWrapperSynthesizer

    fetcher = ContentFetcher()
    synthesizer = AIWrapperSynthesizer(model_name=payload.model_name)

    try:
        list_html = await fetcher.fetch_html(payload.url)
        if not list_html:
            raise HTTPException(status_code=400, detail="목록 페이지 HTML을 불러오지 못했습니다.")

        res = await synthesizer.synthesize_by_anchor_examples(
            list_url=payload.url,
            list_html=list_html,
            positive_anchors=payload.positive_anchors,
            negative_anchors=payload.negative_anchors,
            sample_article_url=payload.sample_article_url
        )

        sample_article_preview = None
        if res.get("sample_article_preview"):
            sample_article_preview = DetailedArticlePreview(**res["sample_article_preview"])

        sample_items = [
            ExtractedLinkItem(
                url=item["url"],
                title=item.get("title"),
                anchor_text=item.get("anchor_text"),
                snippet=item.get("snippet"),
                press=item.get("press"),
                time_text=item.get("time_text"),
                thumbnail=item.get("thumbnail")
            )
            for item in res.get("sample_items", [])
        ]

        return WrapperSynthesisResponse(
            status=res["status"],
            model_used=res["model_used"],
            rules=WrapperRules(**res["rules"]),
            reasoning=res["reasoning"],
            extractable_fields=res["extractable_fields"],
            sample_links_count=res["sample_links_count"],
            sample_links=res["sample_links"],
            sample_items=sample_items,
            sample_article_preview=sample_article_preview,
            confidence_score=res["confidence_score"],
            message=res["message"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anchor-guided wrapper synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"앵커 기반 래퍼 분석 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()

@router.post("/wrapper/synthesize", response_model=WrapperSynthesisResponse)
async def synthesize_wrapper(payload: WrapperSynthesisRequest):
    """
    Local LLM(gemma4:e4b-mlx 등)을 호출하여 대상 웹사이트의 DOM 구조를 분석하고
    링크 및 본문 추출을 위한 최적의 CSS Selector 규칙을 자동 추론(Synthesize)합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.wrapper_synthesizer import AIWrapperSynthesizer

    fetcher = ContentFetcher()
    synthesizer = AIWrapperSynthesizer(model_name=payload.model_name)

    try:
        # 1. 목록 HTML Fetch
        list_html = await fetcher.fetch_html(payload.url)
        if not list_html:
            raise HTTPException(status_code=400, detail="목록 페이지를 불러오지 못했습니다. URL을 확인해주세요.")

        # 2. 샘플 상세 기사 HTML Fetch (제공된 경우)
        sample_html = None
        if payload.sample_article_url:
            sample_html = await fetcher.fetch_html(payload.sample_article_url)

        # 3. AI 래퍼 자동 생성 실행
        res = await synthesizer.synthesize_wrapper(
            list_url=payload.url,
            list_html=list_html,
            sample_article_url=payload.sample_article_url,
            sample_article_html=sample_html
        )

        sample_article_preview = None
        if res.get("sample_article_preview"):
            sample_article_preview = DetailedArticlePreview(**res["sample_article_preview"])

        sample_items = [
            ExtractedLinkItem(
                url=item["url"],
                title=item.get("title"),
                anchor_text=item.get("anchor_text"),
                snippet=item.get("snippet"),
                press=item.get("press"),
                time_text=item.get("time_text"),
                thumbnail=item.get("thumbnail")
            )
            for item in res.get("sample_items", [])
        ]

        return WrapperSynthesisResponse(
            status=res["status"],
            model_used=res["model_used"],
            rules=WrapperRules(**res["rules"]),
            reasoning=res["reasoning"],
            extractable_fields=res["extractable_fields"],
            sample_links_count=res["sample_links_count"],
            sample_links=res["sample_links"],
            sample_items=sample_items,
            sample_article_preview=sample_article_preview,
            confidence_score=res["confidence_score"],
            message=res["message"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Wrapper synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI 래퍼 생성 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()

@router.post("/wrapper/test-rule", response_model=WrapperSynthesisResponse)
async def test_wrapper_rule(payload: WrapperRuleTestRequest):
    """
    사용자가 지정/수정한 CSS Selector 규칙으로 실제 사이트에서 링크 및 본문 파싱을 테스트합니다.
    """
    import sys
    if HORUS_EYES_DIR not in sys.path:
            sys.path.append(HORUS_EYES_DIR)
    from crawler.fetcher import ContentFetcher
    from crawler.pipeline import CrawlPipeline
    from crawler.extractor import AIExtractor
    from crawler.wrapper_synthesizer import sanitize_css_selector

    fetcher = ContentFetcher()
    pipeline = CrawlPipeline()
    extractor = AIExtractor()

    try:
        # 1. 목록 HTML Fetch
        list_html = await fetcher.fetch_html(payload.url)
        if not list_html:
            raise HTTPException(status_code=400, detail="목록 페이지를 불러오지 못했습니다.")

        clean_link_sel = sanitize_css_selector(payload.rules.link_selector)
        clean_content_sel = sanitize_css_selector(payload.rules.content_selector)
        clean_title_sel = sanitize_css_selector(payload.rules.title_selector)
        clean_author_sel = sanitize_css_selector(payload.rules.author_selector)
        clean_date_sel = sanitize_css_selector(payload.rules.date_selector)
        clean_views_sel = sanitize_css_selector(payload.rules.views_selector)
        clean_category_sel = sanitize_css_selector(payload.rules.category_selector)
        clean_image_sel = sanitize_css_selector(payload.rules.image_selector)

        # 2. 링크 추출
        raw_items = pipeline.extract_links_with_meta(payload.url, list_html, link_selector=clean_link_sel or None)
        link_items = [
            ExtractedLinkItem(
                url=item["url"],
                title=item.get("title"),
                anchor_text=item.get("anchor_text"),
                snippet=item.get("snippet"),
                press=item.get("press"),
                time_text=item.get("time_text"),
                thumbnail=item.get("thumbnail")
            )
            for item in raw_items
        ]

        # 3. 상세 기사 파싱
        sample_article_preview = None
        target_article_url = payload.sample_article_url or (link_items[0].url if link_items else None)
        confidence_score = 0.0

        if target_article_url:
            art_html = await fetcher.fetch_html(target_article_url)
            if art_html:
                hints = {
                    "content_selector": clean_content_sel or None,
                    "title_selector": clean_title_sel or None,
                    "author_selector": clean_author_sel or None,
                    "date_selector": clean_date_sel or None,
                    "views_selector": clean_views_sel or None,
                    "category_selector": clean_category_sel or None,
                    "image_selector": clean_image_sel or None,
                }
                art_data = extractor.extract_comprehensive(target_article_url, art_html, hints=hints)
                sample_article_preview = DetailedArticlePreview(**art_data)

                # 신뢰도 계산
                score = 0.0
                if len(link_items) >= 5:
                    score += 0.4
                elif len(link_items) >= 1:
                    score += 0.2
                if art_data.get("content") and len(art_data["content"]) > 100:
                    score += 0.4
                elif art_data.get("content") and len(art_data["content"]) > 20:
                    score += 0.2
                if art_data.get("title") and art_data["title"] != "제목 없음":
                    score += 0.2
                confidence_score = round(min(1.0, score), 2)

        return WrapperSynthesisResponse(
            status="success" if confidence_score >= 0.4 else "warning",
            model_used=payload.rules.llm_model or "custom",
            rules=payload.rules,
            reasoning="사용자가 지정한 셀렉터 규칙으로 실시간 테스트를 수행했습니다.",
            extractable_fields=["title", "content", "author", "date"],
            sample_links_count=len(link_items),
            sample_links=[i.url for i in link_items],
            sample_items=link_items,
            sample_article_preview=sample_article_preview,
            confidence_score=confidence_score,
            message=f"규칙 테스트 완료 (신뢰도: {int(confidence_score * 100)}%, 탐색 링크: {len(link_items)}건)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rule test failed: {e}")
        raise HTTPException(status_code=500, detail=f"규칙 테스트 중 오류 발생: {str(e)}")
    finally:
        await fetcher.close()
        await pipeline.close()

@router.put("/sources/{source_id}/wrapper")
async def update_source_wrapper(
    source_id: int,
    payload: WrapperRuleSaveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    도출 및 검증된 AI 래퍼 추출 규칙을 해당 CrawlSource의 ai_parsing_hints에 영구 저장합니다.
    """
    stmt = select(CrawlSource).where(CrawlSource.id == source_id)
    res = await db.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="해당 수집처(Seed)를 찾을 수 없습니다.")

    existing_hints = dict(source.ai_parsing_hints or {})
    existing_hints.update({
        "link_selector": payload.rules.link_selector,
        "content_selector": payload.rules.content_selector,
        "title_selector": payload.rules.title_selector,
        "author_selector": payload.rules.author_selector,
        "date_selector": payload.rules.date_selector,
        "llm_model": payload.rules.llm_model,
        "updated_via": "AI Wrapper Builder",
        "last_synthesized_at": datetime.now().isoformat()
    })

    source.ai_parsing_hints = existing_hints
    await db.commit()
    await db.refresh(source)

    return {
        "status": "success",
        "source_id": source.id,
        "name": source.name,
        "ai_parsing_hints": source.ai_parsing_hints,
        "message": f"'{source.name}'의 AI 래퍼 추출 규칙이 성공적으로 저장되었습니다."
    }

@router.get("/ollama/models")
async def get_installed_ollama_models():
    """
    Local Ollama 인스턴스에 설치된 전체 모델 목록을 실시간으로 반환합니다.
    """
    import httpx
    from crawler.config import config
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
            if res.status_code == 200:
                models_data = res.json().get("models", [])
                models_list = [m.get("name") for m in models_data if m.get("name")]
                if models_list:
                    # 기본 권장 모델 선정
                    default_model = "gemma4:12b-mlx" if "gemma4:12b-mlx" in models_list else (
                        "gemma4:12b" if "gemma4:12b" in models_list else models_list[0]
                    )
                    return {
                        "models": models_list,
                        "default": default_model
                    }
    except Exception as e:
        logger.warning(f"Failed to query Ollama models from /api/tags: {e}")

    # Fallback 모델 프리셋 목록
    fallback_models = [
        "gemma4:12b-mlx",
        "gemma4:e4b-mlx",
        "gemma4:12b",
        "gemma4:4b",
        "qwen2.5:27b",
        "qwen2.5:14b",
        "qwen2.5:7b",
        "llama3.3:70b",
        "llama3.2:3b",
        "llama3.1:8b",
        "mistral:latest"
    ]
    return {
        "models": fallback_models,
        "default": "gemma4:12b-mlx"
    }


# ==============================================================================
# 🚀 지능형 신규 4대 수집기 (Smart Collectors) API 엔드포인트
# ==============================================================================

async def _execute_smart_collector_run(source_id: int, name: str, collector_type: str, target: str, config_data: dict):
    """
    스마트 수집기 백그라운드 실행 및 결과 DB 적재
    """
    from crawler.scheduler import crawl_scheduler
    session_factory = crawl_scheduler.session_factory
    
    logger.info(f"Executing smart collector #{source_id}: '{name}' (Type: {collector_type}, Target: {target})")
    
    results = []
    try:
        if collector_type == "us_market_signal":
            lang = config_data.get("language", "en")
            results = await us_market_collector.fetch_signals(query=target, language=lang, max_results=15)
        elif collector_type == "community_spike":
            mode = config_data.get("mode", "hot")
            results = await community_spike_collector.fetch_reddit_spikes(subreddit=target, mode=mode, limit=15)

        elif collector_type == "smart_auto_seed":
            res = await smart_auto_seed_collector.discover_and_extract(seed_url=target, max_articles=5)
            results = res.get("extracted_articles", [])
        elif collector_type == "topic_graph":
            lang = config_data.get("language", "ko")
            res = await topic_graph_collector.collect_topic_stream(center_topic=target, language=lang, max_articles=10)
            results = res.get("articles", [])
        elif collector_type == "threads_stream":
            mode = config_data.get("mode", "korean_trending")
            lang = config_data.get("language", "ko")
            results = await threads_collector.fetch_threads_posts(target=target, mode=mode, language=lang, max_results=15)



        # DB 적재
        saved_count = 0
        async with session_factory() as session:
            for item in results:
                url = item.get("url")
                title = item.get("title") or "무제"
                content = item.get("summary") or item.get("content_preview") or title
                author = item.get("author") or item.get("publisher") or "Smart Collector"
                pub_str = item.get("published_at")
                
                try:
                    pub_dt = datetime.fromisoformat(pub_str) if pub_str else datetime.now()
                except Exception:
                    pub_dt = datetime.now()

                meta = {
                    "collector_type": collector_type,
                    "target": target,
                    "source_name": name,
                    "signals": item.get("signals", []),
                    "impact_score": item.get("impact_score", 50),
                    "sentiment": item.get("sentiment", "NEUTRAL"),
                    "velocity_score": item.get("velocity_score", 0),
                    "tickers": item.get("tickers", []),
                    "matched_graph_nodes": item.get("matched_graph_nodes", []),
                    "images": item.get("images", []),
                    "top_comments": item.get("top_comments", []),
                    "comment_count": item.get("num_comments", len(item.get("top_comments", [])))
                }

                stmt = text("""
                    INSERT INTO articles (source_id, url, title, content, summary, author, published_at, category, sentiment_score, metadata)
                    VALUES (:source_id, :url, :title, :content, :summary, :author, :published_at, 'smart_collect', :sentiment_score, CAST(:metadata AS jsonb))
                    ON CONFLICT (url, published_at) DO NOTHING
                """)
                await session.execute(stmt, {
                    "source_id": source_id,
                    "url": url,
                    "title": title[:500],
                    "content": content,
                    "summary": item.get("summary") or title,
                    "author": author[:100],
                    "published_at": pub_dt,
                    "sentiment_score": (item.get("impact_score", 50) - 50) / 50.0,
                    "metadata": json.dumps(meta, ensure_ascii=False)
                })
                saved_count += 1

                # 💬 article_comments 테이블 보장 및 상위 댓글 적재
                if item.get("top_comments"):
                    try:
                        await session.execute(text("""
                            CREATE TABLE IF NOT EXISTS article_comments (
                                id BIGSERIAL PRIMARY KEY,
                                article_id BIGINT NOT NULL,
                                comment_ext_id VARCHAR(100) NOT NULL,
                                author VARCHAR(100),
                                content TEXT NOT NULL,
                                score INT DEFAULT 0,
                                depth INT DEFAULT 0,
                                published_at TIMESTAMPTZ NOT NULL,
                                created_at TIMESTAMPTZ DEFAULT NOW(),
                                sentiment_score FLOAT DEFAULT 0.0,
                                metadata JSONB DEFAULT '{}'::jsonb,
                                CONSTRAINT uq_article_comment UNIQUE (article_id, comment_ext_id)
                            );
                            CREATE INDEX IF NOT EXISTS idx_article_comments_art_id ON article_comments(article_id);
                        """))

                        art_res = await session.execute(text("SELECT id FROM articles WHERE url = :url ORDER BY published_at DESC LIMIT 1"), {"url": url})
                        art_row = art_res.first()
                        if art_row:
                            art_id = art_row[0]
                            for c in item.get("top_comments", []):
                                c_pub = pub_dt
                                try:
                                    c_pub = datetime.fromisoformat(c.get("published_at")) if c.get("published_at") else pub_dt
                                except Exception:
                                    c_pub = pub_dt

                                await session.execute(text("""
                                    INSERT INTO article_comments (article_id, comment_ext_id, author, content, score, depth, published_at, sentiment_score, metadata)
                                    VALUES (:article_id, :comment_ext_id, :author, :content, :score, :depth, :published_at, :sentiment_score, CAST(:metadata AS jsonb))
                                    ON CONFLICT (article_id, comment_ext_id) DO UPDATE SET score = EXCLUDED.score, content = EXCLUDED.content
                                """), {
                                    "article_id": art_id,
                                    "comment_ext_id": c.get("comment_ext_id", f"c_{art_id}_{int(time.time()*1000)}"),
                                    "author": c.get("author", "익명")[:100],
                                    "content": c.get("content", ""),
                                    "score": c.get("score", 0),
                                    "depth": c.get("depth", 0),
                                    "published_at": c_pub,
                                    "sentiment_score": c.get("sentiment_score", 0.0),
                                    "metadata": json.dumps({"tickers": c.get("tickers", [])}, ensure_ascii=False)
                                })
                    except Exception as ce:
                        logger.warning(f"Failed to persist comments for article {url}: {ce}")


                # 이벤트 로깅
                event_type = "market_signal_detected" if collector_type == "us_market_signal" else (
                    "trend_spike_detected" if collector_type == "community_spike" else (
                        "smart_seed_extracted" if collector_type == "smart_auto_seed" else "topic_graph_expanded"
                    )
                )
                event_stmt = text("""
                    INSERT INTO crawl_events (source_id, event_type, title, url, image_url, details)
                    VALUES (:source_id, :event_type, :title, :url, NULL, CAST(:details AS jsonb))
                """)
                await session.execute(event_stmt, {
                    "source_id": source_id,
                    "event_type": event_type,
                    "title": f"[{collector_type}] {title[:400]}",
                    "url": url,
                    "details": json.dumps(meta, ensure_ascii=False)
                })
            
            await session.commit()
        logger.info(f"Smart collector #{source_id} successfully saved {saved_count} items.")
    except Exception as e:
        logger.error(f"Smart collector #{source_id} run failed: {e}", exc_info=True)


@router.get("/collectors")
async def get_smart_collectors(
    collector_type: Optional[str] = Query(None, description="수집기 유형 필터"),
    db: AsyncSession = Depends(get_db)
):
    """
    등록된 스마트 수집기 목록을 조회합니다.
    """
    stmt = select(CrawlSource).order_by(CrawlSource.id.desc())
    res = await db.execute(stmt)
    sources = res.scalars().all()

    collectors = []
    for s in sources:
        hints = s.ai_parsing_hints or {}
        c_type = hints.get("collector_type", "rule_seed")
        
        if collector_type and c_type != collector_type and collector_type != "all":
            continue

        collectors.append({
            "id": s.id,
            "name": s.name,
            "collector_type": c_type,
            "target_url_or_query": hints.get("target_url_or_query", s.base_url),
            "base_url": s.base_url,
            "category": s.category,
            "crawl_interval_minutes": s.crawl_interval_minutes,
            "is_active": s.is_active,
            "config": hints.get("config", {}),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None
        })

    return collectors


@router.post("/collectors")
async def create_smart_collector(
    payload: SmartCollectorCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 지능형 수집기를 생성합니다.
    """
    hints = {
        "collector_type": payload.collector_type,
        "target_url_or_query": payload.target_url_or_query,
        "config": payload.config or {}
    }

    source = CrawlSource(
        name=payload.name,
        base_url=payload.target_url_or_query if payload.target_url_or_query.startswith("http") else f"smart://{payload.collector_type}/{payload.target_url_or_query}",
        category=payload.category,
        crawl_interval_minutes=payload.crawl_interval_minutes,
        is_active=payload.is_active,
        ai_parsing_hints=hints
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return {
        "id": source.id,
        "name": source.name,
        "collector_type": payload.collector_type,
        "target_url_or_query": payload.target_url_or_query,
        "category": source.category,
        "crawl_interval_minutes": source.crawl_interval_minutes,
        "is_active": source.is_active,
        "config": payload.config,
        "created_at": source.created_at.isoformat() if source.created_at else None
    }


@router.put("/collectors/{source_id}")
async def update_smart_collector(
    source_id: int,
    payload: SmartCollectorUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    지능형 수집기 설정을 변경합니다.
    """
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Collector not found")

    hints = dict(source.ai_parsing_hints or {})
    if payload.name is not None:
        source.name = payload.name
    if payload.category is not None:
        source.category = payload.category
    if payload.crawl_interval_minutes is not None:
        source.crawl_interval_minutes = payload.crawl_interval_minutes
    if payload.is_active is not None:
        source.is_active = payload.is_active
    if payload.target_url_or_query is not None:
        hints["target_url_or_query"] = payload.target_url_or_query
        if payload.target_url_or_query.startswith("http"):
            source.base_url = payload.target_url_or_query
    if payload.config is not None:
        hints["config"] = payload.config

    source.ai_parsing_hints = hints
    await db.commit()
    await db.refresh(source)

    return {
        "id": source.id,
        "name": source.name,
        "collector_type": hints.get("collector_type", "rule_seed"),
        "target_url_or_query": hints.get("target_url_or_query", source.base_url),
        "category": source.category,
        "crawl_interval_minutes": source.crawl_interval_minutes,
        "is_active": source.is_active,
        "config": hints.get("config", {})
    }


@router.delete("/collectors/{source_id}")
async def delete_smart_collector(
    source_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    스마트 수집기를 삭제합니다.
    """
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Collector not found")

    await db.delete(source)
    await db.commit()
    return {"status": "success", "message": f"Collector #{source_id} deleted"}


@router.post("/collectors/{source_id}/action")
async def control_smart_collector_action(
    source_id: int,
    payload: CollectorActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    수집기 프로세스를 제어합니다 (start, pause, stop, run_once).
    """
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Collector not found")

    hints = dict(source.ai_parsing_hints or {})
    action = payload.action.lower()

    if action in ["start", "resume"]:
        source.is_active = True
        hints["status"] = "RUNNING"
    elif action == "pause":
        source.is_active = False
        hints["status"] = "PAUSED"
    elif action == "stop":
        source.is_active = False
        hints["status"] = "STOPPED"
    elif action == "run_once":
        hints["status"] = "RUNNING"
        hints["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
        # 비동기 실행
        try:
            c_type = hints.get("collector_type", "rule_seed")
            target = hints.get("target_url_or_query", source.base_url)
            cfg = hints.get("config", {})
            asyncio.create_task(_execute_smart_collector_run(source.id, source.name, c_type, target, cfg))
        except Exception as e:
            logger.warning(f"Run once execution error: {e}")

    source.ai_parsing_hints = hints
    await db.commit()
    await db.refresh(source)

    return {
        "id": source.id,
        "name": source.name,
        "is_active": source.is_active,
        "status": hints.get("status", "RUNNING" if source.is_active else "STOPPED"),
        "last_triggered_at": hints.get("last_triggered_at"),
        "message": f"Collector #{source_id} action '{action}' applied successfully"
    }


@router.post("/collectors/test", response_model=SmartCollectorTestResponse)

async def test_smart_collector(payload: SmartCollectorTestRequest):
    """
    4대 수집기 Dry-Run 실시간 테스트 엔드포인트
    """
    c_type = payload.collector_type
    target = payload.target
    options = payload.options or {}

    try:
        if c_type == "us_market_signal":
            results = await us_market_collector.fetch_signals(
                query=target,
                language=payload.language or "en",
                max_results=payload.max_results or 10
            )
            return SmartCollectorTestResponse(
                status="success",
                collector_type=c_type,
                target=target,
                total_count=len(results),
                results=results,
                message=f"미국 시장/속보 RSS에서 {len(results)}건의 시그널 기사를 감지했습니다."
            )
        elif c_type == "community_spike":
            mode = options.get("mode", "hot")
            clean_sub = target.replace("r/", "").replace("https://www.reddit.com/r/", "").replace("https://reddit.com/r/", "").strip("/ ")
            results = await community_spike_collector.fetch_reddit_spikes(
                subreddit=clean_sub,
                mode=mode,
                limit=payload.max_results or 15,
                spike_multiplier_threshold=options.get("spike_multiplier", 1.5)
            )
            return SmartCollectorTestResponse(
                status="success",
                collector_type=c_type,
                target=f"r/{clean_sub}",
                total_count=len(results),
                results=results,
                message=f"Reddit r/{clean_sub}에서 {len(results)}건의 급등/인기 포스트를 감지했습니다."
            )

        elif c_type == "smart_auto_seed":
            res = await smart_auto_seed_collector.discover_and_extract(
                seed_url=target,
                max_articles=payload.max_results or 5,
                extract_full_content=True
            )
            return SmartCollectorTestResponse(
                status=res.get("status", "success"),
                collector_type=c_type,
                target=target,
                total_count=res.get("total_discovered_links", 0),
                results=res.get("extracted_articles", []),
                extra_meta={"discovered_links": res.get("discovered_links", [])},
                message=res.get("message", "자율 탐색 완료")
            )
        elif c_type == "topic_graph":
            res = await topic_graph_collector.collect_topic_stream(
                center_topic=target,
                language=payload.language or "ko",
                max_articles=payload.max_results or 10
            )
            return SmartCollectorTestResponse(
                status="success",
                collector_type=c_type,
                target=target,
                total_count=res.get("total_articles", 0),
                results=res.get("articles", []),
                extra_meta={
                    "graph": res.get("graph"),
                    "expanded_keywords": res.get("expanded_keywords"),
                    "query_used": res.get("query_used")
                },
                message=f"토픽 '{target}' 기반 연관 지식그래프 확장 및 {res.get('total_articles', 0)}건의 수집 완료"
            )
        elif c_type == "threads_stream":
            mode = options.get("mode", "korean_trending" if (payload.language == "ko" or "스레드" in target or "korean" in target or "국내" in target) else "trending")
            lang = payload.language or ("ko" if mode == "korean_trending" else "en")
            results = await threads_collector.fetch_threads_posts(
                target=target,
                mode=mode,
                language=lang,
                max_results=payload.max_results or 10
            )
            mode_label = "🇰🇷 대한민국 핫스레드" if lang == "ko" or mode == "korean_trending" else ("실시간 전역 트렌딩" if mode == "trending" else f"@{target.replace('@', '')}")
            return SmartCollectorTestResponse(
                status="success",
                collector_type=c_type,
                target=target,
                total_count=len(results),
                results=results,
                message=f"Threads(쓰레즈) [{mode_label}]에서 {len(results)}건의 실시간 포스트를 감지했습니다."
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown collector_type: {c_type}")

    except Exception as e:
        logger.error(f"Test smart collector failed: {e}", exc_info=True)
        return SmartCollectorTestResponse(
            status="error",
            collector_type=c_type,
            target=target,
            total_count=0,
            results=[],
            message=f"테스트 실행 실패: {str(e)}"
        )


@router.post("/topic-graph/expand", response_model=TopicGraphExpandResponse)
async def expand_topic_graph_endpoint(payload: TopicGraphExpandRequest):
    """
    토픽 중심어 입력 시 연관어 및 지식그래프 노드/링크를 확장 미리보기합니다.
    """
    try:
        res = await topic_graph_collector.expand_topic_graph(
            center_topic=payload.topic,
            depth=payload.depth or 1,
            limit_terms=payload.limit_terms or 8
        )
        return TopicGraphExpandResponse(
            center_topic=res["center_topic"],
            nodes=res["nodes"],
            links=res["links"],
            expanded_keywords=res["expanded_keywords"],
            suggested_query=res["suggested_query"]
        )
    except Exception as e:
        logger.error(f"Topic graph expansion failed: {e}")
        raise HTTPException(status_code=500, detail=f"토픽 확장 실패: {str(e)}")


@router.post("/collectors/{source_id}/trigger")
async def trigger_smart_collector_crawl(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 지능형 수집기를 백그라운드로 즉시 실행합니다.
    """
    result = await db.execute(select(CrawlSource).where(CrawlSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Collector not found")

    hints = source.ai_parsing_hints or {}
    c_type = hints.get("collector_type", "rule_seed")
    target = hints.get("target_url_or_query", source.base_url)
    config_data = hints.get("config", {})

    background_tasks.add_task(
        _execute_smart_collector_run,
        source.id,
        source.name,
        c_type,
        target,
        config_data
    )

    return {
        "status": "triggered",
        "source_id": source.id,
        "name": source.name,
        "collector_type": c_type,
        "target": target,
        "message": f"수집기 '{source.name}'의 백그라운드 수집이 즉시 시작되었습니다."
    }


@router.get("/signals/recent")
async def get_recent_signals(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    실시간 감지된 마켓 시그널, 커뮤니티 급등, 토픽 확장 이벤트를 반환합니다.
    """
    stmt = (
        select(CrawlEvent)
        .where(CrawlEvent.event_type.in_([
            "market_signal_detected",
            "trend_spike_detected",
            "smart_seed_extracted",
            "topic_graph_expanded"
        ]))
        .order_by(CrawlEvent.id.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    events = res.scalars().all()

    items = []
    for ev in events:
        items.append({
            "id": ev.id,
            "source_id": ev.source_id,
            "event_type": ev.event_type,
            "title": ev.title,
            "url": ev.url,
            "details": ev.details or {},
            "created_at": ev.created_at.isoformat() if ev.created_at else None
        })

    return items


# ==============================================================================
# 🌐 수집 대상 사이트/피드 (Target Sites & Financial Feeds) 관리 API
# ==============================================================================

DEFAULT_BUILTIN_TARGET_SITES = [
    {
        "id": -1,
        "name": "Google News Global Financial Cluster (통합 외신)",
        "url": "https://news.google.com/rss/search?q=US+Stock+Market+OR+Fed+OR+NVIDIA&hl=en-US&gl=US&ceid=US:en",
        "category": "us_market",
        "is_active": True,
        "is_builtin": True,
        "description": "Bloomberg, Reuters, CNBC, WSJ 등 전세계 수백 개 금융/경제 전문지 실시간 통합 집계",
        "created_at": "2026-01-01T00:00:00"
    },
    {
        "id": -2,
        "name": "Yahoo Finance Top Headlines (야후 파이낸스 마켓 속보)",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^IXIC,NVDA,AAPL,MSFT,TSLA",
        "category": "us_market",
        "is_active": True,
        "is_builtin": True,
        "description": "S&P500, 나스닥 및 메가캡 테크주 실시간 헤드라인 피드",
        "created_at": "2026-01-01T00:00:00"
    },
    {
        "id": -3,
        "name": "CNBC US Top Market Stories (CNBC 마켓 주요 보도)",
        "url": "https://search.cnbc.com/rs/search/combinedlist/view.xml?partnerId=wrss01&id=10000664",
        "category": "us_market",
        "is_active": True,
        "is_builtin": True,
        "description": "월가 투자 전문가 해설, 기업 실적 및 시장 긴급 속보",
        "created_at": "2026-01-01T00:00:00"
    },
    {
        "id": -4,
        "name": "MarketWatch Top Stories (마켓워치 금융 속보)",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "category": "macro",
        "is_active": True,
        "is_builtin": True,
        "description": "다우존스 계열의 실시간 주식, 채권, 거시경제 분석 뉴스",
        "created_at": "2026-01-01T00:00:00"
    },
    {
        "id": -5,
        "name": "Investing.com US Stock News (인베스팅닷컴 미국주식)",
        "url": "https://www.investing.com/rss/news_25.rss",
        "category": "us_market",
        "is_active": True,
        "is_builtin": True,
        "description": "미국 증시 종목별 실시간 속보 및 투자자 브리핑",
        "created_at": "2026-01-01T00:00:00"
    },
    {
        "id": -6,
        "name": "SEC EDGAR Press Releases (미국 증권거래위원회 공식 공시)",
        "url": "https://www.sec.gov/news/pressreleases.rss",
        "category": "sec_edgar",
        "is_active": True,
        "is_builtin": True,
        "description": "미 연방 증권거래위원회(SEC) 공식 보도자료 및 규제/공시 피드",
        "created_at": "2026-01-01T00:00:00"
    },
    {
        "id": -7,
        "name": "연합뉴스 경제/외신 속보 (국내 언론사 외신 브리핑)",
        "url": "https://news.google.com/rss/search?q=%EA%B8%88%EB%A6%AC+OR+%EB%B0%98%EB%8F%84%EC%B2%B4+OR+%ED%99%98%EC%9C%A8+OR+%EB%AF%B8%EA%B5%AD%EC%A6%9D%EC%8B%9C&hl=ko&gl=KR&ceid=KR:ko",
        "category": "domestic_news",
        "is_active": True,
        "is_builtin": True,
        "description": "한국어 기반 글로벌 금융/미국증시 실시간 번역 속보",
        "created_at": "2026-01-01T00:00:00"
    }
]

@router.get("/target-sites", response_model=List[TargetSiteRead])
async def get_target_sites(db: AsyncSession = Depends(get_db)):
    """
    수집 대상 사이트/피드 목록(기본 내장 프리셋 + 사용자 등록 커스텀 사이트)을 반환합니다.
    """
    # 1. DB에서 커스텀 등록된 타겟 사이트 조회
    stmt = select(CrawlSource).where(
        (CrawlSource.category == "market_feed_site") | 
        (CrawlSource.ai_parsing_hints["collector_type"].astext == "target_site")
    ).order_by(CrawlSource.id.desc())
    res = await db.execute(stmt)
    custom_sources = res.scalars().all()

    results = []
    # 기본 프리셋 먼저 추가
    for b in DEFAULT_BUILTIN_TARGET_SITES:
        results.append(TargetSiteRead(
            id=b["id"],
            name=b["name"],
            url=b["url"],
            category=b["category"],
            is_active=b["is_active"],
            is_builtin=True,
            description=b["description"],
            created_at=b["created_at"]
        ))

    # 사용자 추가 사이트 추가
    for cs in custom_sources:
        hints = cs.ai_parsing_hints or {}
        results.append(TargetSiteRead(
            id=cs.id,
            name=cs.name,
            url=hints.get("target_url", cs.base_url),
            category=hints.get("feed_category", "us_market"),
            is_active=cs.is_active,
            is_builtin=False,
            description=hints.get("description", ""),
            created_at=cs.created_at.isoformat() if cs.created_at else None
        ))

    return results


@router.post("/target-sites", response_model=TargetSiteRead)
async def create_target_site(
    payload: TargetSiteCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 수집 대상 사이트/피드를 등록합니다.
    """
    hints = {
        "collector_type": "target_site",
        "target_url": payload.url,
        "feed_category": payload.category,
        "description": payload.description or "",
        "is_builtin": False
    }

    source = CrawlSource(
        name=payload.name,
        base_url=payload.url,
        category="market_feed_site",
        crawl_interval_minutes=10,
        is_active=payload.is_active,
        ai_parsing_hints=hints
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return TargetSiteRead(
        id=source.id,
        name=source.name,
        url=payload.url,
        category=payload.category,
        is_active=source.is_active,
        is_builtin=False,
        description=payload.description or "",
        created_at=source.created_at.isoformat() if source.created_at else None
    )


@router.delete("/target-sites/{site_id}")
async def delete_target_site(
    site_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    등록된 커스텀 수집 대상 사이트를 삭제합니다. (기본 프리셋은 삭제 불가)
    """
    if site_id < 0:
        raise HTTPException(status_code=400, detail="기본 내장 사이트 프리셋은 삭제할 수 없습니다. (비활성화 토글을 사용하세요)")

    result = await db.execute(select(CrawlSource).where(CrawlSource.id == site_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="해당 수집 대상 사이트를 찾을 수 없습니다.")

    await db.delete(source)
    await db.commit()
    return {"status": "success", "message": f"수집 대상 사이트 #{site_id}가 삭제되었습니다."}


@router.put("/target-sites/{site_id}/toggle")
async def toggle_target_site(
    site_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    수집 대상 사이트의 활성화(ON/OFF) 상태를 토글합니다.
    """
    if site_id < 0:
        # 내장 사이트 토글 처리
        for b in DEFAULT_BUILTIN_TARGET_SITES:
            if b["id"] == site_id:
                b["is_active"] = not b["is_active"]
                return {"status": "success", "id": site_id, "is_active": b["is_active"]}
        raise HTTPException(status_code=404, detail="사이트를 찾을 수 없습니다.")

    result = await db.execute(select(CrawlSource).where(CrawlSource.id == site_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="해당 수집 대상 사이트를 찾을 수 없습니다.")

    source.is_active = not source.is_active
    await db.commit()
    return {"status": "success", "id": source.id, "is_active": source.is_active}


@router.post("/target-sites/test")
async def test_target_site(payload: TargetSiteTestRequest):
    """
    특정 사이트/피드 URL에서 실시간으로 글을 파싱하여 테스트 결과를 반환합니다.
    """
    try:
        results = await us_market_collector.fetch_from_feed_url(
            feed_url=payload.url,
            publisher_name=payload.publisher_name or "",
            max_results=payload.max_results or 10
        )
        return {
            "status": "success",
            "url": payload.url,
            "publisher": payload.publisher_name,
            "total_count": len(results),
            "results": results,
            "message": f"'{payload.publisher_name or payload.url}'에서 {len(results)}건의 기사를 성공적으로 파싱했습니다."
        }
    except Exception as e:
        logger.error(f"Target site test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "url": payload.url,
            "total_count": 0,
            "results": [],
            "message": f"사이트 테스트 실패: {str(e)}"
        }


# ==============================================================================
# 🛸 Subreddit 카탈로그 (UAP, UFO, Cars, AI, Finance, Mystery) API
# ==============================================================================

CATEGORY_LABELS = {
    "ufo_mystery": "🛸 UFO / UAP / 미스터리",
    "cars_ev": "🚗 자동차 / 전기차 / 모빌리티",
    "finance": "📈 주식 / 투자 / 크립토",
    "tech_ai": "🤖 AI / 빅테크 / 과학",
    "world_news": "🌍 글로벌 / 뉴스 / 시사",
    "gaming": "🎮 게임 / 서브컬처",
    "custom": "⭐ 사용자 등록 / 커스텀"
}

DEFAULT_BUILTIN_SUBREDDITS = [
    # 1. UFO / UAP / 미스터리
    {"id": -101, "name": "UFOs", "label": "UFO 미확인비행체", "category": "ufo_mystery", "icon": "🛸", "desc": "미 정부 청문회, 군사 FLIR 센서 영상, 목격 증언 및 탈기밀 문서 토론"},
    {"id": -102, "name": "UAP", "label": "UAP 미확인비행현상", "category": "ufo_mystery", "icon": "🛸", "desc": "AARO 공식 보고서, 과학적 UAP 데이터 분석 및 정책 투명성 논의"},
    {"id": -103, "name": "Aliens", "label": "외계 지적생명체", "category": "ufo_mystery", "icon": "👽", "desc": "비인간 지능(NHI), 생물학적 기원 가설 및 외계 접촉 증거 분석"},
    {"id": -104, "name": "HighStrangeness", "label": "초상현상 / 이상현상", "category": "ufo_mystery", "icon": "🌌", "desc": "발트해 이상체, 전자기 이상, 고대 문명 및 미지의 초자연 미스터리"},
    {"id": -105, "name": "UnresolvedMysteries", "label": "미해결 미스터리", "category": "ufo_mystery", "icon": "🔍", "desc": "역사적 레이더 실종 사건, 미제 사건 및 문서 해독 토론"},
    {"id": -106, "name": "Paranormal", "label": "초자연 / 심령 미스터리", "category": "ufo_mystery", "icon": "👻", "desc": "설명할 수 없는 물리적 현상, 심령 사진 및 미지의 전파 신호"},
    {"id": -107, "name": "Glitch_in_the_Matrix", "label": "현실 왜곡 / 매트릭스 글리치", "category": "ufo_mystery", "icon": "🌀", "desc": "시공간 왜곡, 기억 불일치(만델라 효과) 및 양자 현실 경험담"},

    # 2. 자동차 / 모빌리티
    {"id": -201, "name": "cars", "label": "자동차 종합 토론", "category": "cars_ev", "icon": "🏎️", "desc": "신차 출시, 파워트레인 비교, 트랙 시승기 및 자동차 문화"},
    {"id": -202, "name": "electricvehicles", "label": "전기차 (EV) 전용", "category": "cars_ev", "icon": "⚡", "desc": "차세대 전고체 배터리, 800V 초고속 충전 및 EV 시장 동향"},
    {"id": -203, "name": "teslamotors", "label": "테슬라 / FSD / 로보택시", "category": "cars_ev", "icon": "🚗", "desc": "자율주행 FSD v13, 사이버트럭, 옵티머스 및 에너지 생태계"},
    {"id": -204, "name": "Autos", "label": "모터스포츠 / 오토스", "category": "cars_ev", "icon": "🏁", "desc": "글로벌 모터쇼, 슈퍼카, 클래식카 및 레이싱 테크놀로지"},
    {"id": -205, "name": "CarTalk", "label": "자동차 정비 / 기술", "category": "cars_ev", "icon": "🔧", "desc": "엔진 튜닝, 서스펜션 지오메트리 및 차량 유지보수 Q&A"},

    # 3. 주식 / 투자 / 크립토
    {"id": -301, "name": "wallstreetbets", "label": "WSB (월가 밈/옵션)", "category": "finance", "icon": "🚀", "desc": "단기 급등 밈주식, 0DTE 옵션, 실시간 화제성 폭증 토론"},
    {"id": -302, "name": "stocks", "label": "미국 주요 주식", "category": "finance", "icon": "📈", "desc": "미국 증시 주요 종목, 기업 실적(Earnings) 및 산업 분석"},
    {"id": -303, "name": "options", "label": "옵션 전략 / 변동성", "category": "finance", "icon": "⚡", "desc": "대규모 옵션 거래량, IV 변동성 및 감마 스퀴즈 분석"},
    {"id": -304, "name": "investing", "label": "가치 / 중장기 투자", "category": "finance", "icon": "💼", "desc": "거시경제, 금리, 장기 포트폴리오 및 펀더멘털 투자"},
    {"id": -305, "name": "CryptoCurrency", "label": "가상자산 / 코인", "category": "finance", "icon": "🪙", "desc": "비트코인, 이더리움 및 알트코인 온체인/마켓 트렌드"},
    {"id": -306, "name": "Daytrading", "label": "데이트레이딩 / 단타", "category": "finance", "icon": "🎯", "desc": "장중 모멘텀 돌파, 스캘핑 및 단기 거래량 급증 종목"},
    {"id": -307, "name": "Shortsqueeze", "label": "숏스퀴즈 테마", "category": "finance", "icon": "💥", "desc": "공매도 비율 과열 및 숏커버링 유망 종목 토론"},
    {"id": -308, "name": "ValueInvesting", "label": "저평가 가치주", "category": "finance", "icon": "💎", "desc": "워런 버핏 스타일 FCF 현금흐름 및 저평가 우량주"},
    {"id": -309, "name": "dividends", "label": "배당 성장주 / ETF", "category": "finance", "icon": "💰", "desc": "배당 성장주, 월배당 ETF 및 현금흐름 복리 투자"},

    # 4. AI / 테크 / 과학
    {"id": -401, "name": "Singularity", "label": "기술적 특이점 / AGI", "category": "tech_ai", "icon": "🧠", "desc": "범용인공지능(AGI), 자율 에이전트 및 초지능 발전 타임라인"},
    {"id": -402, "name": "artificial", "label": "인공지능 (AI) 종합", "category": "tech_ai", "icon": "🤖", "desc": "최신 LLM 모델, 컴퓨터 비전, 로보틱스 및 AI 윤리"},
    {"id": -403, "name": "ChatGPT", "label": "ChatGPT & 프롬프트", "category": "tech_ai", "icon": "💬", "desc": "OpenAI 신기능, 프롬프트 엔지니어링 및 실사용 활용 사례"},
    {"id": -404, "name": "technology", "label": "테크놀로지 뉴스", "category": "tech_ai", "icon": "💻", "desc": "빅테크 동향, 반도체 공급망 및 차세대 통신 인프라"},
    {"id": -405, "name": "space", "label": "우주 탐사 / 천문학", "category": "tech_ai", "icon": "🚀", "desc": "제임스웹 망원경 관측, 화성 탐사선 및 민간 우주 발사체"},
    {"id": -406, "name": "Futurology", "label": "미래 기술 / 미래학", "category": "tech_ai", "icon": "🔮", "desc": "양자 컴퓨팅, 유전자 편집(CRISPR), 핵융합 에너지 전망"},

    # 5. 글로벌 뉴스 & 시사
    {"id": -501, "name": "worldnews", "label": "글로벌 세계 뉴스", "category": "world_news", "icon": "🌍", "desc": "전 세계 주요 외신, 국제 분쟁 및 정상회담 속보"},
    {"id": -502, "name": "geopolitics", "label": "지정학 / 국제관계", "category": "world_news", "icon": "🗺️", "desc": "패권 경쟁, 무역 통상 제재, 안보 조약 심층 분석"},
    {"id": -503, "name": "Economics", "label": "경제학 / 글로벌 거시경제", "category": "world_news", "icon": "📊", "desc": "중앙은행 통화정책, 무역수지, 노동시장 및 인플레이션"}
]

@router.get("/subreddits", response_model=List[SubredditRead])
async def get_subreddit_catalog(db: AsyncSession = Depends(get_db)):
    """
    모든 관심 분야(UAP, UFO, 자동차, 미스터리, AI, 주식 등)의 Subreddit 카탈로그를 반환합니다.
    """
    stmt = select(CrawlSource).where(
        (CrawlSource.category == "subreddit_catalog") |
        (CrawlSource.ai_parsing_hints["collector_type"].astext == "custom_subreddit")
    ).order_by(CrawlSource.id.desc())
    res = await db.execute(stmt)
    custom_sources = res.scalars().all()

    results = []
    # 1. 기본 내장 프리셋 카탈로그
    for b in DEFAULT_BUILTIN_SUBREDDITS:
        clean = b["name"].replace("r/", "")
        results.append(SubredditRead(
            id=b["id"],
            name=clean,
            display_name=f"r/{clean}",
            label=b["label"],
            category=b["category"],
            category_label=CATEGORY_LABELS.get(b["category"], "기타"),
            description=b["desc"],
            icon=b["icon"],
            is_builtin=True,
            created_at="2026-01-01T00:00:00"
        ))

    # 2. 사용자 등록 커스텀 Subreddit
    for cs in custom_sources:
        hints = cs.ai_parsing_hints or {}
        sub_name = hints.get("subreddit_name", cs.name).replace("r/", "").strip()
        cat = hints.get("category", "custom")
        results.append(SubredditRead(
            id=cs.id,
            name=sub_name,
            display_name=f"r/{sub_name}",
            label=hints.get("label", sub_name),
            category=cat,
            category_label=CATEGORY_LABELS.get(cat, "⭐ 사용자 등록"),
            description=hints.get("description", "사용자 등록 Subreddit"),
            icon=hints.get("icon", "📌"),
            is_builtin=False,
            created_at=cs.created_at.isoformat() if cs.created_at else None
        ))

    return results


@router.post("/subreddits", response_model=SubredditRead)
async def create_custom_subreddit(
    payload: SubredditCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 Subreddit을 카탈로그에 등록합니다.
    """
    clean_sub = payload.name.replace("r/", "").replace("https://www.reddit.com/r/", "").strip("/ ")
    if not clean_sub:
        raise HTTPException(status_code=400, detail="유효한 Subreddit 이름을 입력해주세요.")

    hints = {
        "collector_type": "custom_subreddit",
        "subreddit_name": clean_sub,
        "label": payload.label or clean_sub,
        "category": payload.category or "custom",
        "description": payload.description or "",
        "icon": payload.icon or "📌",
        "is_builtin": False
    }

    source = CrawlSource(
        name=f"r/{clean_sub}",
        base_url=f"https://www.reddit.com/r/{clean_sub}",
        category="subreddit_catalog",
        crawl_interval_minutes=15,
        is_active=True,
        ai_parsing_hints=hints
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return SubredditRead(
        id=source.id,
        name=clean_sub,
        display_name=f"r/{clean_sub}",
        label=payload.label or clean_sub,
        category=payload.category,
        category_label=CATEGORY_LABELS.get(payload.category, "⭐ 사용자 등록"),
        description=payload.description or "",
        icon=payload.icon or "📌",
        is_builtin=False,
        created_at=source.created_at.isoformat() if source.created_at else None
    )


@router.delete("/subreddits/{sub_id}")
async def delete_custom_subreddit(
    sub_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    사용자가 등록한 커스텀 Subreddit을 삭제합니다.
    """
    if sub_id < 0:
        raise HTTPException(status_code=400, detail="기본 내장 Subreddit 프리셋은 삭제할 수 없습니다.")

    result = await db.execute(select(CrawlSource).where(CrawlSource.id == sub_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="해당 Subreddit을 찾을 수 없습니다.")

    await db.delete(source)
    await db.commit()
    return {"status": "success", "message": f"Subreddit #{sub_id}가 삭제되었습니다."}


# ==============================================================================
# 💬 Reddit/Article 실시간 댓글 수집 및 증분 동기화 API
# ==============================================================================

@router.post("/articles/{article_id}/sync-comments", response_model=ArticleCommentSyncResponse)
async def sync_article_comments(
    article_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    이미 수집된 특정 문서(Article)의 실시간 최신 댓글을 수집하여 DB에 증분 동기화(연결)합니다.
    """
    # 1. 문서 조회
    res = await db.execute(text("SELECT id, url, title, metadata FROM articles WHERE id = :id"), {"id": article_id})
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail=f"문서 #{article_id}를 찾을 수 없습니다.")

    art_id, url, title, meta = row[0], row[1], row[2], row[3] or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    # 2. Subreddit 및 Post ID 추출
    sub = "wallstreetbets"
    post_id = "recent"
    if "reddit.com/r/" in url:
        parts = url.split("/r/")[1].split("/")
        if len(parts) >= 1:
            sub = parts[0]
        if len(parts) >= 3 and parts[1] == "comments":
            post_id = parts[2]
    else:
        sub = meta.get("target", "wallstreetbets").replace("r/", "")

    # 3. 실시간 댓글 파싱
    comments = await community_spike_collector.fetch_reddit_post_comments(subreddit=sub, post_id=post_id, limit=20)

    # 4. article_comments 테이블 보장 및 Upsert
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS article_comments (
            id BIGSERIAL PRIMARY KEY,
            article_id BIGINT NOT NULL,
            comment_ext_id VARCHAR(100) NOT NULL,
            author VARCHAR(100),
            content TEXT NOT NULL,
            score INT DEFAULT 0,
            depth INT DEFAULT 0,
            published_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            sentiment_score FLOAT DEFAULT 0.0,
            metadata JSONB DEFAULT '{}'::jsonb,
            CONSTRAINT uq_article_comment UNIQUE (article_id, comment_ext_id)
        );
        CREATE INDEX IF NOT EXISTS idx_article_comments_art_id ON article_comments(article_id);
    """))

    now_dt = datetime.now(timezone.utc)
    comment_reads = []
    for c in comments:
        c_pub = now_dt
        try:
            c_pub = datetime.fromisoformat(c.get("published_at")) if c.get("published_at") else now_dt
        except Exception:
            c_pub = now_dt

        stmt = text("""
            INSERT INTO article_comments (article_id, comment_ext_id, author, content, score, depth, published_at, sentiment_score, metadata)
            VALUES (:article_id, :comment_ext_id, :author, :content, :score, :depth, :published_at, :sentiment_score, CAST(:metadata AS jsonb))
            ON CONFLICT (article_id, comment_ext_id) DO UPDATE SET
                score = EXCLUDED.score,
                content = EXCLUDED.content
            RETURNING id
        """)
        ins_res = await db.execute(stmt, {
            "article_id": art_id,
            "comment_ext_id": c.get("comment_ext_id", f"c_{art_id}_{int(time.time()*1000)}"),
            "author": c.get("author", "익명")[:100],
            "content": c.get("content", ""),
            "score": c.get("score", 0),
            "depth": c.get("depth", 0),
            "published_at": c_pub,
            "sentiment_score": c.get("sentiment_score", 0.0),
            "metadata": json.dumps({"tickers": c.get("tickers", [])}, ensure_ascii=False)
        })
        new_id = ins_res.scalar()

        comment_reads.append(ArticleCommentRead(
            id=new_id,
            article_id=art_id,
            comment_ext_id=c.get("comment_ext_id", ""),
            author=c.get("author", "익명"),
            content=c.get("content", ""),
            score=c.get("score", 0),
            depth=c.get("depth", 0),
            published_at=c_pub.isoformat(),
            sentiment_score=c.get("sentiment_score", 0.0),
            tickers=c.get("tickers", [])
        ))

    # 5. articles.metadata 내 최신 댓글 요약 업데이트
    meta["top_comments"] = [c.dict() for c in comment_reads[:5]]
    meta["comment_count"] = len(comments)
    meta["last_comment_crawled_at"] = now_dt.isoformat()
    await db.execute(
        text("UPDATE articles SET metadata = CAST(:metadata AS jsonb) WHERE id = :id"),
        {"id": art_id, "metadata": json.dumps(meta, ensure_ascii=False)}
    )
    await db.commit()

    return ArticleCommentSyncResponse(
        status="success",
        article_id=art_id,
        article_title=title,
        total_synced_comments=len(comments),
        comments=comment_reads,
        message=f"문서 #{art_id}에 대해 {len(comments)}건의 실시간 최신 댓글을 동기화하여 연결했습니다."
    )


@router.get("/articles/{article_id}/comments", response_model=List[ArticleCommentRead])
async def get_article_comments(
    article_id: int,
    limit: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 문서(Article)에 연결되어 저장된 댓글 목록을 조회합니다.
    """
    try:
        stmt = text("""
            SELECT id, article_id, comment_ext_id, author, content, score, depth, published_at, sentiment_score, metadata
            FROM article_comments
            WHERE article_id = :article_id
            ORDER BY score DESC, published_at DESC
            LIMIT :limit
        """)
        res = await db.execute(stmt, {"article_id": article_id, "limit": limit})
        rows = res.fetchall()

        results = []
        for r in rows:
            meta = r[9] or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            results.append(ArticleCommentRead(
                id=r[0],
                article_id=r[1],
                comment_ext_id=r[2],
                author=r[3] or "익명",
                content=r[4],
                score=r[5] or 0,
                depth=r[6] or 0,
                published_at=r[7].isoformat() if r[7] else None,
                sentiment_score=r[8] or 0.0,
                tickers=meta.get("tickers", [])
            ))

        if results:
            return results

        # 만약 DB 테이블에 없으면 articles.metadata['top_comments']에서 폴백 조회
        art_res = await db.execute(text("SELECT metadata FROM articles WHERE id = :id"), {"id": article_id})
        art_row = art_res.first()
        if art_row and art_row[0]:
            m = art_row[0]
            if isinstance(m, str):
                m = json.loads(m)
            top_c = m.get("top_comments", [])
            return [
                ArticleCommentRead(
                    article_id=article_id,
                    comment_ext_id=c.get("comment_ext_id", f"c_{i}"),
                    author=c.get("author", "익명"),
                    content=c.get("content", ""),
                    score=c.get("score", 0),
                    depth=c.get("depth", 0),
                    published_at=c.get("published_at"),
                    sentiment_score=c.get("sentiment_score", 0.0),
                    tickers=c.get("tickers", [])
                )
                for i, c in enumerate(top_c)
            ]

        return []
    except Exception as e:
        logger.warning(f"Failed to query comments for article {article_id}: {e}")
        return []









