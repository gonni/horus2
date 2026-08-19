-- PostgreSQL 확장 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- 1. 크롤링 소스 관리 테이블 (crawl_sources)
CREATE TABLE IF NOT EXISTS crawl_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    category VARCHAR(50) DEFAULT 'news',       -- news, community, stock
    crawl_interval_minutes INT DEFAULT 15,
    is_active BOOLEAN DEFAULT TRUE,
    ai_parsing_hints JSONB DEFAULT '{}'::jsonb, -- LLM 추출 가이드라인 및 샘플 스키마
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 기사 원천 데이터 (articles) - 날짜별 파티셔닝
CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL,
    source_id INT REFERENCES crawl_sources(id) ON DELETE SET NULL,
    url VARCHAR(1000) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    author VARCHAR(100),
    published_at TIMESTAMPTZ NOT NULL,
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    category VARCHAR(50),
    sentiment_score FLOAT,                     -- -1.0 ~ 1.0 (LLM 감성 분석)
    embedding vector(768),                     -- pgvector 기사 시맨틱 임베딩 (768 dim)
    metadata JSONB DEFAULT '{}'::jsonb,        -- 태그, 추출된 엔티티, 원본 메타 등
    PRIMARY KEY (id, published_at),
    CONSTRAINT uk_articles_url_pub UNIQUE (url, published_at)
) PARTITION BY RANGE (published_at);

-- 기본/초기 파티션 테이블 생성 (과거 및 미래 파티션 예시)
CREATE TABLE IF NOT EXISTS articles_default PARTITION OF articles DEFAULT;
CREATE TABLE IF NOT EXISTS articles_2025 PARTITION OF articles
    FOR VALUES FROM ('2025-01-01 00:00:00+09') TO ('2026-01-01 00:00:00+09');
CREATE TABLE IF NOT EXISTS articles_2026 PARTITION OF articles
    FOR VALUES FROM ('2026-01-01 00:00:00+09') TO ('2027-01-01 00:00:00+09');
CREATE TABLE IF NOT EXISTS articles_2027 PARTITION OF articles
    FOR VALUES FROM ('2027-01-01 00:00:00+09') TO ('2028-01-01 00:00:00+09');

-- 전문검색 Trigram 인덱스 및 벡터 인덱스
CREATE INDEX IF NOT EXISTS idx_articles_title_trgm ON articles USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_content_trgm ON articles USING gin (content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_pub_at ON articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles (source_id);

-- 3. 실시간 단어 빈도 시계열 (term_frequencies) - TimescaleDB Hypertable
CREATE TABLE IF NOT EXISTS term_frequencies (
    time TIMESTAMPTZ NOT NULL,
    source_id INT,
    term VARCHAR(100) NOT NULL,
    frequency INT NOT NULL,
    doc_count INT DEFAULT 1
);
SELECT create_hypertable('term_frequencies', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_term_freq_term_time ON term_frequencies (term, time DESC);

-- 4. KOSPI 주가 및 종가매매 퀀트 (stock_daily, stock_closing_targets)
CREATE TABLE IF NOT EXISTS stock_daily (
    target_dt DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    open_price INT, 
    high_price INT, 
    low_price INT, 
    close_price INT,
    volume BIGINT,
    individual BIGINT, 
    foreigner BIGINT, 
    institution BIGINT, 
    pension BIGINT,
    PRIMARY KEY (target_dt, code)
);
CREATE INDEX IF NOT EXISTS idx_stock_daily_dt ON stock_daily (target_dt DESC);

CREATE TABLE IF NOT EXISTS stock_closing_targets (
    id SERIAL PRIMARY KEY,
    target_dt DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    target_score FLOAT,
    closing_price INT NOT NULL,
    next_day_open INT, 
    next_day_10m_high INT, 
    next_day_close INT,
    return_rate_open FLOAT, 
    return_rate_high FLOAT,
    is_success BOOLEAN,
    analysis_report TEXT,                      -- LLM 종목 분석 리포트
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stock_closing_dt ON stock_closing_targets (target_dt DESC);

-- 5. MAB 추천 피드백 (reco_feedbacks)
CREATE TABLE IF NOT EXISTS reco_feedbacks (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    article_id BIGINT,
    event_type VARCHAR(20) NOT NULL,            -- impression, click
    score FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reco_feedbacks_art ON reco_feedbacks (article_id, event_type);

-- 6. 기사 이미지 멀티모달 처리 큐 (article_images)
CREATE TABLE IF NOT EXISTS article_images (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT,
    article_url VARCHAR(1000),
    image_url VARCHAR(1000) NOT NULL,
    order_index INT DEFAULT 1,
    placeholder_token VARCHAR(500) NOT NULL,
    local_path VARCHAR(500),
    status VARCHAR(20) DEFAULT 'PENDING',       -- PENDING, PROCESSING, COMPLETED, FAILED
    description TEXT,
    model_used VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_article_images_article_id ON article_images (article_id);
CREATE INDEX IF NOT EXISTS idx_article_images_status ON article_images (status);
CREATE INDEX IF NOT EXISTS idx_article_images_status_article ON article_images (status, article_id);

-- 레거시 MySQL crawl_seeds 마이그레이션 시드 데이터
INSERT INTO crawl_sources (id, name, base_url, category, crawl_interval_minutes, is_active, ai_parsing_hints)
VALUES 
(21, '네이버뉴>속보>전체', 'https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=title', 'news', 10, true, '{"legacy_seed_no": 21, "language": "ko", "link_selector": "ul.type02 li a, ul.type06_headline li a, .list_body a", "content_selector": "#dic_area, #articeBody"}'::jsonb),
(22, '뽐뿌>자유게시판', 'https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard', 'community', 15, true, '{"legacy_seed_no": 22, "language": "ko", "link_selector": "tr.list0 td a, tr.list1 td a, a.list_subject", "content_selector": ".board-contents, td.board-contents"}'::jsonb),
(23, '좌리앙', 'https://m.clien.net/service/board/park', 'community', 15, true, '{"legacy_seed_no": 23, "language": "ko", "link_selector": ".list_item a.list_subject, span.subject_fixed, a.list_subject", "content_selector": ".post_article, .post_content"}'::jsonb),
(24, '코인판>자유게시판', 'https://coinpan.com/free', 'community', 15, true, '{"legacy_seed_no": 24, "language": "ko", "link_selector": "tbody tr td.title a, a.hx, tr.list td.title a", "content_selector": ".read_body, .xe_content"}'::jsonb)
ON CONFLICT (id) DO UPDATE 
SET name = EXCLUDED.name, base_url = EXCLUDED.base_url, category = EXCLUDED.category, ai_parsing_hints = EXCLUDED.ai_parsing_hints;
