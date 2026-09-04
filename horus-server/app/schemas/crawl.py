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
    articles_24h: int = 0
    peak_tps_24h: float = 0.0
    success_rate_24h: float = 99.4
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

# 🧠 GPU2 Dual 5070 Ti 8-Way 병렬 큐 & 텍스트/비전 듀얼 워커 스키마
class TextWorkerControlRequest(BaseModel):
    model_name: Optional[str] = Field(default="gpu2:qwen3.8:27b", description="LLM 텍스트 모델명 (GPU2 또는 Ollama)")
    concurrency: Optional[int] = Field(default=8, ge=1, le=32, description="텍스트 NLP 동시 처리 슬롯 수")

class VisionWorkerControlRequest(BaseModel):
    model_name: Optional[str] = Field(default="gpu2:qwen3.8:27b", description="LLM 비전 모델명")
    concurrency: Optional[int] = Field(default=4, ge=1, le=32, description="비전 이미지 동시 처리 슬롯 수")

class GPUConcurrencyRequest(BaseModel):
    concurrency: int = Field(default=8, ge=1, le=32, description="변경할 동시 처리 슬롯 수 (1~32)")
    subsystem: Optional[str] = Field(default="all", description="적용 대상 서브시스템: all, text, vision")

class GPUUnifiedStatusResponse(BaseModel):
    # 병렬 동시성 파라미터
    concurrency: int = Field(default=8, description="전체 동시 처리 슬롯 수")
    text_concurrency: int = Field(default=8, description="텍스트 NLP 동시 처리 슬롯 수")
    vision_concurrency: int = Field(default=4, description="비전 Image-to-Text 동시 처리 슬롯 수")
    gpu_device: str = Field(default="Dual RTX 5070 Ti (8-Way 병렬 가속)", description="가속 디바이스 정보")
    provider: str = Field(default="gpu2", description="현재 사용 중인 AI 공급자 (gpu2, ollama, hybrid)")
    active_slots: List[Dict[str, Any]] = Field(default_factory=list, description="현재 가동 중인 병렬 슬롯별 상태 목록")

    text_state: str = Field(default="IDLE", description="IDLE, RUNNING, PAUSED, STOPPED")
    text_model_name: str = "gpu2:qwen3.8:27b"
    text_pending_count: int = 0
    text_processed_count: int = 0
    text_failed_count: int = 0

    vision_state: str = Field(default="IDLE", description="IDLE, RUNNING, PAUSED, STOPPED")
    vision_model_name: str = "gpu2:qwen3.8:27b"
    vision_pending_count: int = 0
    vision_processed_count: int = 0
    vision_failed_count: int = 0

    total_articles: int = 0
    current_task: Optional[Dict[str, Any]] = None
    last_processed_at: Optional[str] = None
    last_error_message: Optional[str] = None

class LLMWorkerControlRequest(BaseModel):
    model_name: Optional[str] = Field(default="gpu2:qwen3.8:27b", description="LLM 모델명")
    batch_size: Optional[int] = Field(default=8, ge=1, le=32)
    interval_seconds: Optional[float] = Field(default=0.5, ge=0.1, le=60.0)

class LLMWorkerStatusResponse(BaseModel):
    state: str = Field(description="IDLE, RUNNING, PAUSED, STOPPED")
    model_name: str = "gpu2:qwen3.8:27b"
    batch_size: int = 8
    interval_seconds: float = 0.5
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

# 🌊 다중 레인 Horizon 실시간 스트림 스키마 (초단위 호출 틱 & 이벤트 타입별 정밀 타임라인)
class BucketEventBreakdown(BaseModel):
    seed_scan: int = 0
    article_ingest: int = 0
    image_ingest: int = 0
    llm_enrich: int = 0
    error: int = 0
    total: int = 0

class CallTick(BaseModel):
    id: int
    event_type: str  # 'seed_scan', 'article_ingest', 'image_ingest', 'llm_enrich', 'error'
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
    type_breakdown: List[BucketEventBreakdown] = Field(default_factory=list) # 각 시점별 호출 종류 세분화
    total_count: int = 0
    peak_tps: float = 0.0
    avg_tps: float = 0.0
    current_instant_count: int = 0 # 가장 최근 시점 호출 수
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

# 🚀 지능형 신규 4대 수집기 스키마 (US Market, Community Spike, Smart Auto Seed, Topic Graph)
class SmartCollectorCreate(BaseModel):
    name: str = Field(description="수집기 이름")
    collector_type: str = Field(description="수집 유형: us_market_signal, community_spike, smart_auto_seed, topic_graph")
    target_url_or_query: str = Field(description="대상 URL 또는 검색어/서브레딧")
    category: str = Field(default="news", description="카테고리: news, community, stock")
    crawl_interval_minutes: int = Field(default=15, description="수집 주기(분)")
    is_active: bool = Field(default=True, description="활성화 여부")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="유형별 추가 파라미터")

class SmartCollectorUpdate(BaseModel):
    name: Optional[str] = None
    target_url_or_query: Optional[str] = None
    category: Optional[str] = None
    crawl_interval_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

class SmartCollectorTestRequest(BaseModel):
    collector_type: str = Field(description="수집 유형: us_market_signal, community_spike, smart_auto_seed, topic_graph")
    target: str = Field(description="대상 검색어 / Subreddit / Seed URL / Topic")
    language: Optional[str] = Field(default="en", description="언어 코드 (en, ko)")
    max_results: Optional[int] = Field(default=10, description="최대 결과 수")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 옵션 (mode, min_score 등)")

class SmartCollectorTestResponse(BaseModel):
    status: str
    collector_type: str
    target: str
    total_count: int
    results: List[Dict[str, Any]] = Field(default_factory=list)
    extra_meta: Optional[Dict[str, Any]] = None
    message: str

class TopicGraphExpandRequest(BaseModel):
    topic: str = Field(description="확장할 중심 주제어")
    depth: Optional[int] = Field(default=1, description="그래프 탐색 깊이")
    limit_terms: Optional[int] = Field(default=8, description="연관어 최대 개수")

class TopicGraphExpandResponse(BaseModel):
    center_topic: str
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    expanded_keywords: List[str] = Field(default_factory=list)
    suggested_query: str

# 🌐 수집 대상 사이트/피드 (Target Sites & Financial Feeds) 관리 스키마
class TargetSiteCreate(BaseModel):
    name: str = Field(description="사이트 또는 매체 이름 (예: CNBC 마켓 속보, Yahoo Finance NVDA)")
    url: str = Field(description="대상 웹사이트 URL 또는 RSS/Feed 엔드포인트")
    category: str = Field(default="us_market", description="카테고리: us_market, macro, tech_ai, earnings, crypto, sec_edgar, domestic_news")
    is_active: bool = Field(default=True, description="활성화 여부")
    description: Optional[str] = Field(default="", description="설명 또는 메모")

class TargetSiteRead(BaseModel):
    id: int
    name: str
    url: str
    category: str
    is_active: bool
    is_builtin: bool = False
    description: Optional[str] = ""
    created_at: Optional[str] = None

class TargetSiteTestRequest(BaseModel):
    url: str = Field(description="테스트 대상 사이트 또는 RSS 피드 URL")
    publisher_name: Optional[str] = Field(default="", description="언론사/매체명")
    max_results: Optional[int] = Field(default=10, description="최대 결과 수")

# 🛸 Subreddit 카탈로그 관리 스키마
class SubredditCreate(BaseModel):
    name: str = Field(description="Subreddit 식별자 (예: UFOs, cars, wallstreetbets)")
    label: Optional[str] = Field(default="", description="표시 레이블 (예: UFO / 외계 미스터리)")
    category: str = Field(default="custom", description="카테고리: ufo_mystery, cars_ev, finance, tech_ai, world_news, gaming, custom")
    description: Optional[str] = Field(default="", description="Subreddit 설명")
    icon: Optional[str] = Field(default="📌", description="대표 이모지/아이콘")

class SubredditRead(BaseModel):
    id: int
    name: str
    display_name: str
    label: str
    category: str
    category_label: str
    description: str
    icon: str
    is_builtin: bool = False
    created_at: Optional[str] = None

# 💬 Reddit/Article 댓글 관리 스키마
class ArticleCommentRead(BaseModel):
    id: Optional[int] = None
    article_id: Optional[int] = None
    comment_ext_id: str
    author: Optional[str] = "익명"
    content: str
    score: int = 0
    depth: int = 0
    published_at: Optional[str] = None
    sentiment_score: Optional[float] = 0.0
    tickers: Optional[List[str]] = Field(default_factory=list)

class ArticleCommentSyncResponse(BaseModel):
    status: str
    article_id: int
    article_title: str
    total_synced_comments: int
    comments: List[ArticleCommentRead] = Field(default_factory=list)
    message: str = ""

class CollectorActionRequest(BaseModel):
    action: str = Field(description="제어 액션: start, pause, stop, run_once")



