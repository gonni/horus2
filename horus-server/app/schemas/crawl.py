from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

class CrawlSourceBase(BaseModel):
    name: str
    base_url: str
    category: str = "news"
    crawl_interval_minutes: int = 15
    is_active: bool = True
    ai_parsing_hints: Optional[Dict[str, Any]] = None

class CrawlSourceCreate(CrawlSourceBase):
    pass

class CrawlSourceUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    category: Optional[str] = None
    crawl_interval_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    ai_parsing_hints: Optional[Dict[str, Any]] = None

class CrawlSourceRead(CrawlSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CrawlJobRequest(BaseModel):
    source_id: int
    max_pages: Optional[int] = 10

class CrawlJobStatus(BaseModel):
    source_id: int
    status: str
    crawled_count: int
    error_count: int
    started_at: datetime
    finished_at: Optional[datetime] = None

class BackfillRequest(BaseModel):
    start_date: str = Field(description="시작일 (YYYY-MM-DD)", example="2026-08-01")
    end_date: str = Field(description="종료일 (YYYY-MM-DD)", example="2026-08-15")
    section: str = Field(default="economy", description="네이버 섹션: economy, tech, society, politics")
    max_articles_per_day: int = Field(default=30, description="일별 최대 수집 기사 수")

class BackfillStatus(BaseModel):
    status: str
    current_date: Optional[str] = None
    total_days: int = 0
    processed_days: int = 0
    saved_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    current_tps: float = 0.0
    last_message: str = ""

class CrawlTestRequest(BaseModel):
    url: str = Field(description="테스트 대상 목록 URL")
    link_selector: Optional[str] = Field(default=None, description="기사 링크 영역 CSS Selector")
    content_selector: Optional[str] = Field(default=None, description="본문 영역 CSS Selector")
    title_selector: Optional[str] = Field(default=None, description="제목 영역 CSS Selector")
    author_selector: Optional[str] = Field(default=None, description="작성자 영역 CSS Selector")
    date_selector: Optional[str] = Field(default=None, description="작성일시 영역 CSS Selector")
    views_selector: Optional[str] = Field(default=None, description="조회수 영역 CSS Selector")
    category_selector: Optional[str] = Field(default=None, description="카테고리 영역 CSS Selector")
    image_selector: Optional[str] = Field(default=None, description="첨부이미지 영역 CSS Selector")

class ExtractedLinkItem(BaseModel):
    url: str
    title: Optional[str] = None
    anchor_text: Optional[str] = None
    snippet: Optional[str] = None
    press: Optional[str] = None
    time_text: Optional[str] = None
    thumbnail: Optional[str] = None

class DetailedArticlePreview(BaseModel):
    url: str
    title: str
    content: str
    content_preview: str
    summary: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    category: Optional[str] = "news"
    views: Optional[str] = ""
    sentiment_score: Optional[float] = 0.0
    key_entities: List[str] = Field(default_factory=list)
    related_stocks: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    og_description: Optional[str] = None
    og_site_name: Optional[str] = None
    canonical_url: Optional[str] = None
    char_count: int = 0
    reading_time_minutes: int = 1
    raw_html_size_kb: float = 0.0
    image_descriptions: Dict[str, str] = Field(default_factory=dict, description="본문 이미지별 Vision LLM 텍스트 설명")
    header_meta: Optional[Dict[str, Any]] = Field(default=None, description="HTML <head> OpenGraph 및 전체 메타태그 정보")

class ArticlePreviewRequest(BaseModel):
    url: str = Field(description="파싱 대상 기사/문서 URL")
    content_selector: Optional[str] = Field(default=None, description="본문 영역 CSS Selector")
    title_selector: Optional[str] = Field(default=None, description="제목 영역 CSS Selector")
    author_selector: Optional[str] = Field(default=None, description="작성자 영역 CSS Selector")
    date_selector: Optional[str] = Field(default=None, description="작성일시 영역 CSS Selector")
    views_selector: Optional[str] = Field(default=None, description="조회수 영역 CSS Selector")
    category_selector: Optional[str] = Field(default=None, description="카테고리 영역 CSS Selector")
    image_selector: Optional[str] = Field(default=None, description="첨부이미지 영역 CSS Selector")
    category: Optional[str] = Field(default="news", description="카테고리")
    enable_vision: Optional[bool] = Field(default=False, description="본문 이미지 Vision 텍스트 변환 및 주입 여부")
    vision_model: Optional[str] = Field(default=None, description="Vision LLM 모델명")

class CrawlTestResponse(BaseModel):
    status: str
    list_url: str
    extracted_links_count: int
    sample_links: List[str] = Field(default_factory=list)
    items: List[ExtractedLinkItem] = Field(default_factory=list)
    sample_article: Optional[DetailedArticlePreview] = None
    message: str = ""

class CrawlDashboardStats(BaseModel):
    total_articles: int
    today_articles: int
    active_sources_count: int
    current_tps: float
    rate_limit_policy: str
    recent_articles: List[Dict[str, Any]]
    sources_summary: List[Dict[str, Any]]

class WrapperRules(BaseModel):
    link_selector: Optional[str] = ""
    content_selector: Optional[str] = ""
    title_selector: Optional[str] = ""
    author_selector: Optional[str] = ""
    date_selector: Optional[str] = ""
    views_selector: Optional[str] = ""
    category_selector: Optional[str] = ""
    image_selector: Optional[str] = ""
    llm_model: Optional[str] = "gemma4:12b-mlx"
    enable_vision: Optional[bool] = False
    vision_model: Optional[str] = None

class VisionDescribeRequest(BaseModel):
    image_url: str = Field(description="분석 대상 이미지 URL")
    prompt: Optional[str] = Field(default=None, description="커스텀 프롬프트")
    model_name: Optional[str] = Field(default="llama3.2-vision", description="Vision LLM 모델명")

class VisionDescribeResponse(BaseModel):
    image_url: str
    description: str
    status: str = "success"

class ArticleMetaSynthesizeRequest(BaseModel):
    sample_urls: List[str] = Field(description="교차 분석할 상세 페이지 URL 목록 (2~4개)")
    model_name: Optional[str] = Field(default="gemma4:12b-mlx", description="Ollama LLM 모델명")
    base_rules: Optional[Union[Dict[str, Any], WrapperRules, Any]] = Field(default=None, description="기존 베이스 셀렉터")

class ArticleMetaSynthesizeResponse(BaseModel):
    rules: WrapperRules
    reasoning: str
    analyzed_urls_count: int
    sample_previews: List[DetailedArticlePreview] = Field(default_factory=list)
    message: str = ""

class WrapperSynthesisRequest(BaseModel):
    source_id: Optional[int] = None
    url: str = Field(description="분석 대상 목록 URL")
    model_name: Optional[str] = Field(default="gemma4:e4b-mlx", description="Ollama 모델명")
    sample_article_url: Optional[str] = None

class WrapperSynthesisResponse(BaseModel):
    status: str
    model_used: str
    rules: WrapperRules
    reasoning: str
    extractable_fields: List[str] = Field(default_factory=list)
    sample_links_count: int = 0
    sample_links: List[str] = Field(default_factory=list)
    sample_items: List[ExtractedLinkItem] = Field(default_factory=list)
    sample_article_preview: Optional[DetailedArticlePreview] = None
    confidence_score: float = 0.0
    message: str = ""

class WrapperRuleSaveRequest(BaseModel):
    rules: WrapperRules

class WrapperRuleTestRequest(BaseModel):
    url: str
    rules: WrapperRules
    sample_article_url: Optional[str] = None

class DOMInspectItem(BaseModel):
    anchor_text: str
    url: str
    a_class: Optional[str] = ""
    parent_tag: Optional[str] = ""
    parent_class: Optional[str] = ""
    is_notice: bool = False
    is_menu: bool = False

class DOMInspectRequest(BaseModel):
    url: str

class DOMContainerGroup(BaseModel):
    group_id: str
    selector: str
    container_tag: str
    container_class: Optional[str] = ""
    display_name: str
    link_count: int
    is_probable_article_list: bool = False
    sample_anchors: List[str] = Field(default_factory=list)
    items: List[DOMInspectItem] = Field(default_factory=list)

class DOMInspectResponse(BaseModel):
    url: str
    total_links: int
    groups_count: int = 0
    groups: List[DOMContainerGroup] = Field(default_factory=list)
    all_items: List[DOMInspectItem] = Field(default_factory=list)
    items: List[DOMInspectItem] = Field(default_factory=list)  # 하위 호환성 유지


class AnchorGuidedSynthesisRequest(BaseModel):
    source_id: Optional[int] = None
    url: str = Field(description="분석 대상 목록 URL")
    positive_anchors: List[str] = Field(description="수집하고 싶은 앵커 텍스트 예시들")
    negative_anchors: Optional[List[str]] = Field(default_factory=list, description="제외하고 싶은 텍스트 예시들")
    model_name: Optional[str] = Field(default="gemma4:12b-mlx", description="Ollama 모델명")
    sample_article_url: Optional[str] = None

class ReverseSelectorRequest(BaseModel):
    url: str = Field(description="기사/문서 상세 URL")
    snippet: str = Field(description="사용자가 복사해서 붙여넣은 텍스트 문자열")
    target_field: Optional[str] = Field(default="content", description="대상 필드: content, author, title, date")

class ReverseSelectorResponse(BaseModel):
    status: str
    suggested_selector: str
    tag_name: Optional[str] = None
    element_text_preview: Optional[str] = None
    matched_snippet: str
    message: str

class AnchorGroupMatchRequest(BaseModel):
    url: str = Field(description="게시판 목록 페이지 URL")
    target_snippet: str = Field(description="수집대상 본문 기사 앵커 텍스트 또는 키워드")

class AnchorGroupMatchResponse(BaseModel):
    status: str
    suggested_link_selector: str
    target_anchor: str
    target_url: Optional[str] = None
    matched_count: int
    matched_items: List[Dict[str, Any]] = Field(default_factory=list)
    sample_links: List[str] = Field(default_factory=list)
    excluded_notices_count: int = 0
    excluded_sample_notices: List[str] = Field(default_factory=list)
    message: str = ""

# 🔄 지속 크롤러 데몬(Daemon) 스키마
class DaemonControlRequest(BaseModel):
    interval_seconds: Optional[int] = Field(default=60, ge=10, le=3600, description="크롤링 주기 (초)")

class DaemonStatusResponse(BaseModel):
    state: str = Field(description="IDLE, RUNNING, PAUSED, STOPPED")
    interval_seconds: int = 60
    seconds_to_next_cycle: int = 0
    cycle_count: int = 0
    total_ingested_articles: int = 0
    total_scanned_seeds: int = 0
    current_running_seed_name: Optional[str] = None
    last_cycle_started_at: Optional[str] = None
    last_cycle_finished_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_error_message: Optional[str] = None

# 🧠 GPU 단일 직렬 큐 & 텍스트/비전 듀얼 워커 스키마
class TextWorkerControlRequest(BaseModel):
    model_name: Optional[str] = Field(default="gemma4:e4b-mlx", description="Ollama 텍스트 모델명")

class VisionWorkerControlRequest(BaseModel):
    model_name: Optional[str] = Field(default="qwen3.5:2b-mlx", description="Ollama 비전 모델명")

class GPUUnifiedStatusResponse(BaseModel):
    text_state: str = Field(default="IDLE", description="IDLE, RUNNING, PAUSED, STOPPED")
    text_model_name: str = "gemma4:e4b-mlx"
    text_pending_count: int = 0
    text_processed_count: int = 0
    text_failed_count: int = 0

    vision_state: str = Field(default="IDLE", description="IDLE, RUNNING, PAUSED, STOPPED")
    vision_model_name: str = "qwen3.5:2b-mlx"
    vision_pending_count: int = 0
    vision_processed_count: int = 0
    vision_failed_count: int = 0

    total_articles: int = 0
    current_task: Optional[Dict[str, Any]] = None
    last_processed_at: Optional[str] = None
    last_error_message: Optional[str] = None

class LLMWorkerControlRequest(BaseModel):
    model_name: Optional[str] = Field(default="gemma4:e4b-mlx", description="Ollama 모델명")
    batch_size: Optional[int] = Field(default=2, ge=1, le=10)
    interval_seconds: Optional[float] = Field(default=3.0, ge=0.5, le=60.0)

class LLMWorkerStatusResponse(BaseModel):
    state: str = Field(description="IDLE, RUNNING, PAUSED, STOPPED")
    model_name: str = "gemma4:e4b-mlx"
    batch_size: int = 2
    interval_seconds: float = 3.0
    processed_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    total_articles: int = 0
    current_item_title: Optional[str] = None
    last_processed_at: Optional[str] = None
    last_error_message: Optional[str] = None
    unified: Optional[Dict[str, Any]] = None


# 📊 실시간 수집 이벤트 및 시계열 스키마
class CrawlEventItem(BaseModel):
    id: int
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    event_type: str = Field(description="seed_scan, article_ingest, image_ingest, llm_enrich, duplicate_skip, error")
    title: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class TimeSeriesMetricsResponse(BaseModel):
    range: str
    source_id: Optional[str] = "all"
    timestamps: List[str] = Field(default_factory=list)
    seed_scans: List[int] = Field(default_factory=list)
    articles_ingested: List[int] = Field(default_factory=list)
    images_ingested: List[int] = Field(default_factory=list)
    llm_enriched: List[int] = Field(default_factory=list)
    total_articles: int = 0
    total_images: int = 0
    total_llm_enriched: int = 0

# 🌊 다중 레인 Horizon 실시간 스트림 스키마 (초단위 호출 틱 & TPS 정밀 모니터링)
class CallTick(BaseModel):
    id: int
    event_type: str  # 'seed_scan', 'article_ingest', 'image_ingest', 'llm_enrich'
    time_str: str
    title: Optional[str] = None
    url: Optional[str] = None
    interval_seconds: float = 0.0
    instant_tps: float = 0.0

class LaneSeries(BaseModel):
    id: str
    name: str
    category: str = "source"  # 'total', 'source', 'type'
    color: str = "#10b981"
    secondary_color: Optional[str] = None
    values: List[float] = Field(default_factory=list)  # Instantaneous TPS (0.0 ~ 1.0)
    raw_counts: List[int] = Field(default_factory=list)
    total_count: int = 0
    peak_tps: float = 0.0
    avg_tps: float = 0.0
    max_tps_limit: float = 1.0
    recent_calls: List[CallTick] = Field(default_factory=list)

class MultiLaneStreamResponse(BaseModel):
    range: str
    timestamps: List[str] = Field(default_factory=list)
    time_window_seconds: int = 600
    lanes: List[LaneSeries] = Field(default_factory=list)
    total_events: int = 0
    active_lanes_count: int = 0
    global_max_tps: float = 0.0
    is_tps_compliant: bool = True
    duplicate_count: int = 0
    latest_event_time: Optional[str] = None










