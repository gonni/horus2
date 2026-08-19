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







