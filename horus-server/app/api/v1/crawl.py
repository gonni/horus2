import asyncio
import logging
import os
import sys
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
    CallTick, LaneSeries, MultiLaneStreamResponse
)

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

    # 2. 오늘 수집된 기사 수
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_stmt = select(func.count(Article.id)).where(Article.crawled_at >= today_start)
    today_res = await db.execute(today_stmt)
    today_articles = today_res.scalar() or 0

    # 3. 활성 수집 소스 수
    src_stmt = select(CrawlSource).order_by(CrawlSource.id.asc())
    src_res = await db.execute(src_stmt)
    sources = src_res.scalars().all()
    active_sources_count = sum(1 for s in sources if s.is_active)

    # 4. 최근 수집된 기사 10건
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
    kst = timezone(timedelta(hours=9))

    if time_range == "10m":
        start_time_utc = now_utc - timedelta(minutes=10)
        bucket_count = 60  # 10초 틱 (60개 포인트)
        bucket_delta = timedelta(seconds=10)
        date_format = "%H:%M:%S"
        window_sec = 600
    elif time_range == "1h":
        start_time_utc = now_utc - timedelta(hours=1)
        bucket_count = 60  # 1분 틱 (60개 포인트)
        bucket_delta = timedelta(minutes=1)
        date_format = "%H:%M"
        window_sec = 3600
    elif time_range == "1d":
        start_time_utc = now_utc - timedelta(days=1)
        bucket_count = 48  # 30분 틱 (48개 포인트)
        bucket_delta = timedelta(minutes=30)
        date_format = "%m-%d %H:00"
        window_sec = 86400
    else:  # 7d
        start_time_utc = now_utc - timedelta(days=7)
        bucket_count = 56  # 3시간 틱 (56개 포인트)
        bucket_delta = timedelta(hours=3)
        date_format = "%m-%d %H:00"
        window_sec = 86400 * 7

    bucket_sec = max(1.0, bucket_delta.total_seconds())

    # 2. 타임스탬프 버킷 생성 (KST 기준 문자열 포맷)
    timestamps = []
    curr = start_time_utc
    for _ in range(bucket_count):
        curr_kst = curr.astimezone(kst)
        timestamps.append(curr_kst.strftime(date_format))
        curr += bucket_delta

    # 3. 활성 Seed 목록 조회
    sources_res = await db.execute(select(CrawlSource).order_by(CrawlSource.id))
    sources = sources_res.scalars().all()

    # 4. 해당 시간 윈도우 내 모든 이벤트 조회
    stmt = (
        select(CrawlEvent.id, CrawlEvent.source_id, CrawlEvent.event_type, CrawlEvent.title, CrawlEvent.url, CrawlEvent.created_at)
        .where(CrawlEvent.created_at >= start_time_utc)
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
    llm_counts = [0] * bucket_count
    total_llm = 0
    total_events_count = len(events)
    latest_event_time = None

    for ev_id, src_id, ev_type, title, url, ev_time in events:
        ev_utc = ev_time if ev_time.tzinfo else ev_time.replace(tzinfo=timezone.utc)
        latest_event_time = ev_utc.astimezone(kst).isoformat()
        diff_sec = (ev_utc - start_time_utc).total_seconds()
        idx = int(diff_sec // bucket_sec)

        if 0 <= idx < bucket_count:
            if ev_type in ("seed_scan", "article_ingest"):
                total_req_counts[idx] += 1
                if src_id in source_req_counts:
                    source_req_counts[src_id][idx] += 1
                    source_totals[src_id] += 1
                    source_events_list[src_id].append((ev_id, ev_type, title, url, ev_utc))
            elif ev_type == "llm_enrich":
                llm_counts[idx] += 1
                total_llm += 1

    # 6. 초단위 TPS 변환 (요청 수 / 버킷 초)
    total_tps_values = [round(c / bucket_sec, 3) for c in total_req_counts]
    global_max_tps = max(total_tps_values) if total_tps_values else 0.0

    lanes: List[LaneSeries] = []

    # Lane 0: Total Aggregate
    lanes.append(LaneSeries(
        id="total",
        name="0. 전체 통합 수집 파형 (Global Aggregate)",
        category="total",
        color="#10b981",
        secondary_color="#059669",
        values=total_tps_values,
        raw_counts=total_req_counts,
        total_count=sum(total_req_counts),
        peak_tps=max(total_tps_values) if total_tps_values else 0.0,
        avg_tps=round(sum(total_tps_values) / max(1, len(total_tps_values)), 3),
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

        # 개별 호출 틱 계산 (최근 15건의 호출 간격 및 순간 TPS)
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
            total_count=source_totals[s.id],
            peak_tps=peak,
            avg_tps=avg,
            max_tps_limit=1.0,
            recent_calls=call_ticks
        ))

    # Lane N+1: LLM AI 정제
    llm_tps_list = [round(c / bucket_sec, 3) for c in llm_counts]
    lanes.append(LaneSeries(
        id="llm",
        name=f"{len(sources)+1}. LLM AI 정제 및 요약 파형",
        category="type",
        color="#06b6d4",
        secondary_color="#0891b2",
        values=llm_tps_list,
        raw_counts=llm_counts,
        total_count=total_llm,
        peak_tps=max(llm_tps_list) if llm_tps_list else 0.0,
        avg_tps=round(sum(llm_tps_list) / max(1, len(llm_tps_list)), 3),
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





