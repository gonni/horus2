import asyncio
import logging
import os
import sys
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, text
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# horus-eyes 모듈 경로를 sys.path에 동적으로 등록
HORUS_EYES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../horus-eyes"))
if HORUS_EYES_DIR not in sys.path:
    sys.path.append(HORUS_EYES_DIR)

from app.core.database import get_db
from app.models.crawl_source import CrawlSource
from app.models.article import Article
from app.schemas.crawl import (
    CrawlSourceRead, CrawlSourceCreate, CrawlSourceUpdate, CrawlJobRequest, CrawlJobStatus,
    BackfillRequest, BackfillStatus, CrawlDashboardStats, CrawlTestRequest, CrawlTestResponse,
    ExtractedLinkItem, DetailedArticlePreview, ArticlePreviewRequest,
    WrapperRules, WrapperSynthesisRequest, WrapperSynthesisResponse, WrapperRuleSaveRequest, WrapperRuleTestRequest,
    DOMInspectItem, DOMInspectRequest, DOMInspectResponse, DOMContainerGroup, AnchorGuidedSynthesisRequest,
    ArticleMetaSynthesizeRequest, ArticleMetaSynthesizeResponse,
    VisionDescribeRequest, VisionDescribeResponse,
    ReverseSelectorRequest, ReverseSelectorResponse,
    AnchorGroupMatchRequest, AnchorGroupMatchResponse
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





