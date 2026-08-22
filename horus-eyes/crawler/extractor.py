import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
import trafilatura
import httpx
from crawler.config import config

logger = logging.getLogger(__name__)

class ExtractedArticle(BaseModel):
    title: str = Field(description="기사 제목")
    content: str = Field(description="기사 본문 내용")
    summary: Optional[str] = Field(default=None, description="기사 요약")
    author: Optional[str] = Field(default=None, description="작성자 또는 언론사")
    published_at: datetime = Field(default_factory=datetime.now, description="기사 발행 일시")
    category: Optional[str] = Field(default="general", description="카테고리")
    sentiment_score: Optional[float] = Field(default=0.0, description="감성 점수 (-1.0 ~ 1.0)")
    key_entities: List[str] = Field(default_factory=list, description="주요 언급 인물/기업/기관")
    related_stocks: List[str] = Field(default_factory=list, description="관련 주식 종목명")

import copy
import re
import hashlib
from urllib.parse import urljoin

# 닉네임 이미지 URL -> 고유 식별 텍스트 캐시 (동일 이미지에 대해 동일 텍스트 닉네임 100% 보장)
AUTHOR_IMAGE_CACHE: Dict[str, str] = {}

class AIExtractor:
    def __init__(self):
        self.ollama_url = config.OLLAMA_BASE_URL
        self.gemini_key = config.GEMINI_API_KEY

    def clean_text_duplicates(self, text: str) -> str:
        """
        1. '메모12345입력', '님', '작성자 :' 등 불필요한 UI 잡음 제거
        2. '천안중년천안중년' -> '천안중년', 'bambooshootsbambooshoots' -> 'bambooshoots' 등 동일 텍스트 반복 제거
        """
        if not text:
            return ""
        # UI 노이즈 텍스트 제거
        text = re.sub(r"(메모\s*\d*\s*입력.*|메모하기.*|\d+입력.*|작성자\s*메모.*)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(\s*님$|^작성자\s*[:：]\s*|^글쓴이\s*[:：]\s*)", "", text).strip()

        # 완전 2회 반복 패턴 제거 (문자열 길이가 짝수이고 앞뒤 절반이 동일한 경우)
        length = len(text)
        if length >= 2 and length % 2 == 0:
            half = length // 2
            if text[:half] == text[half:]:
                text = text[:half]

        # 정규표현식 기반 반복 서브스트링 de-duplication (예: abcabc -> abc)
        match = re.match(r"^(.{2,})\1$", text)
        if match:
            text = match.group(1)

        return text.strip()

    @staticmethod
    def parse_flexible_date(date_str: Any) -> Optional[datetime]:
        """
        다양한 한국 웹사이트 및 커뮤니티의 작성일자 형식을 유연하고 견고하게 파싱합니다:
        - 2026.08.18 / 22:46, 2026-08-18 22:46:00, 2026/08/18 22:46
        - 2026년 08월 18일 22시 46분, 2026.08.18
        - 등록일 2026-08-17 20:21
        """
        if not date_str or not isinstance(date_str, str):
            return None
        date_str = date_str.strip()

        # 1. YYYY-MM-DD (HH:MM:SS) 정규표현식 매칭 (' / ', ' | ', 'T', ' ' 구분자 완벽 지원)
        m = re.search(r"(\d{4})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})일?(?:[^\d\n]*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?", date_str)
        if m:
            year = m.group(1)
            month = m.group(2).zfill(2)
            day = m.group(3).zfill(2)
            hour = m.group(4).zfill(2) if m.group(4) else "00"
            minute = m.group(5).zfill(2) if m.group(5) else "00"
            second = m.group(6).zfill(2) if m.group(6) else "00"
            dt_str = f"{year}-{month}-{day} {hour}:{minute}:{second}"
            try:
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        # 2. ISO 8601 포맷
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")[:19])
        except Exception:
            pass

        return None

    def clean_extracted_author(self, target_elem: Any, raw_fallback: str = "", base_url: str = "") -> str:
        """
        작성자 엘리먼트에서 닉네임을 정밀 추출합니다:
        1. 내부 팝업/메모 UI 태그 제거
        2. 이미지 닉네임(img[alt], img[title]) 우선 파싱
        3. 이미지만 있는 경우 고유 식별 닉네임(@파일명 또는 @img_hash) 부여 및 캐싱
        4. 중복 텍스트(예: 천안중년천안중년) 완벽 정제
        """
        if target_elem is None:
            return self.clean_text_duplicates(raw_fallback)

        elem = copy.copy(target_elem)

        # 1. UI 노이즈 태그 및 레벨/등급 아이콘 제거
        for noise in list(elem.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["memo", "popup", "layer", "btn", "dropdown", "menu", "badge", "point_level", "level_icon"]))):
            noise.decompose()
        for tag in list(elem(["script", "style", "button"])):
            tag.decompose()

        # 레벨/계급/포인트 아이콘 이미지 제거
        for img in list(elem.find_all("img")):
            img_alt = (img.get("alt") or img.get("title") or "").lower()
            img_cls = str(img.get("class", "")).lower()
            img_src = str(img.get("src", "")).lower()
            if any(k in img_alt or k in img_cls or k in img_src for k in ["레벨", "level", "rank", "grade", "point", "icon", "badge", "계급", "등급", "lv"]):
                img.decompose()

        # 2. 텍스트 추출 (중첩 span.nickname, a.baseList-name 등이 있으면 우선 1개만)
        sub_nick = elem.select_one(".nickname, .user_name, .author, span.name, a.baseList-name, .topTitle-name a")
        if sub_nick:
            text = sub_nick.get_text(strip=True)
        else:
            text = elem.get_text(separator=" ", strip=True)

        if text and len(text.strip()) > 0:
            return self.clean_text_duplicates(text)

        # 3. 텍스트가 없고 순수 이미지 닉네임인 경우 처리
        img = elem.find("img")
        if img:
            img_alt = img.get("alt") or img.get("title")
            if img_alt and len(img_alt.strip()) > 0 and not any(k in img_alt.lower() for k in ["icon", "btn", "level", "grade", "emoticon", "레벨"]):
                return self.clean_text_duplicates(img_alt.strip())

            src = img.get("src") or img.get("data-src") or ""
            if src:
                full_src = urljoin(base_url, src)
                if full_src in AUTHOR_IMAGE_CACHE:
                    return AUTHOR_IMAGE_CACHE[full_src]

                filename = full_src.split("/")[-1].split("?")[0].split(".")[0]
                if filename and len(filename) >= 3 and not any(k in filename.lower() for k in ["blank", "default", "icon", "anonymous"]):
                    nick = f"@{filename}"
                else:
                    h = hashlib.md5(full_src.encode("utf-8")).hexdigest()[:6]
                    nick = f"@user_{h}"
                AUTHOR_IMAGE_CACHE[full_src] = nick
                return nick

        return self.clean_text_duplicates(raw_fallback)

    def extract_content_with_placeholders(
        self,
        html: str,
        base_url: str = "",
        content_selector: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        본문 텍스트를 추출할 때, 본문에 포함된 <img> 태그 위치에
        향후 비동기 Vision LLM 배치 처리 시 치환할 고유 이미지 표식({{HORUS_IMG:1:https://...}})을 박아둡니다.
        반환값: (표식이 박힌 본문 텍스트, 추출된 이미지 메타데이터 목록)
        """
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            import copy
            soup = BeautifulSoup(html, "html.parser")

            # 1. 스크립트, 스타일, 네비게이션, 푸터, 댓글 영역 전수 제거 (노이즈 원천 차단)
            for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
                tag.decompose()

            # 댓글 컨테이너 및 메모 작성창/드래그앤드롭 업로더 폼 전수 제거
            for noise in list(soup.find_all(id=lambda i: i and any(k in str(i).lower() for k in ["comment", "reply", "memo_", "cmt_"]))):
                noise.decompose()
            for noise in list(soup.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["comment", "reply", "memo_", "cmt_", "reply_area", "d_drag", "photo_drag"]))):
                noise.decompose()

            target = None
            if content_selector:
                target = soup.select_one(content_selector)
            if not target:
                for selector in ["td.han", ".han", "td.board-contents", ".pic_bg", "#dic_area", "#articeBody", "#newsEndContents", ".article_body", ".article-body", "#article-view", ".post_article", ".post_content", "article"]:
                    target = soup.select_one(selector)
                    if target:
                        break

            if not target:
                target = soup

            # 본문 내 <img> 및 <a data-org-src> 태그 탐색 및 고유 표식 토큰 삽입 (원본 GIF/고화질 이미지 완벽 복원)
            extracted_images = []
            img_idx = 1
            processed_nodes = set()

            # 1. 원본 보기 앵커/컨테이너(a[data-org-src], a.btn_show_org 등) 우선 처리
            for org_node in list(target.find_all(lambda t: t.name in ["a", "div", "figure"] and (t.get("data-org-src") or t.get("data-original") or t.get("data-gif") or "btn_show_org" in str(t.get("class", "")) or "gif" in str(t.get("onclick", "")).lower()))):
                raw_src = org_node.get("data-org-src") or org_node.get("data-original") or org_node.get("data-gif") or org_node.get("data-src")
                if not raw_src and org_node.name == "a" and org_node.get("href"):
                    href = str(org_node["href"]).strip()
                    if any(href.lower().endswith(ext) for ext in [".gif", ".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
                        raw_src = href

                if raw_src and not any(k in raw_src.lower() for k in ["icon", "btn", "logo", "banner", "gif_load", "loading", "blank.gif", "dot.gif"]):
                    full_img_url = urljoin(base_url, raw_src)
                    token = f"{{{{HORUS_IMG:{img_idx}:{full_img_url}}}}}"
                    extracted_images.append({
                        "order_index": img_idx,
                        "placeholder_token": token,
                        "placeholder_key": f"HORUS_IMG_{img_idx}",
                        "image_url": full_img_url,
                        "status": "PENDING"
                    })
                    org_node.replace_with(soup.new_string(f"\n\n{token}\n\n"))
                    processed_nodes.add(org_node)
                    img_idx += 1

            # 2. 일반 <img> 태그 처리 (Lazy Loading 및 부모 링크 속성 교차 확인)
            for img in list(target.find_all("img")):
                # 상위 앵커에서 이미 처리된 경우 스킵
                if img in processed_nodes or (img.parent and img.parent in processed_nodes):
                    continue

                parent_a = img.find_parent("a") or img.parent
                raw_src = None

                # 부모 앵커의 원본 속성 확인
                if parent_a and parent_a.name == "a":
                    for attr in ["data-org-src", "data-original", "data-src", "data-url", "data-gif", "data-href", "data-full-src"]:
                        val = parent_a.get(attr)
                        if val and not val.startswith("data:image"):
                            raw_src = str(val).strip()
                            break
                    if not raw_src and parent_a.get("href"):
                        href = str(parent_a["href"]).strip()
                        if any(href.lower().endswith(ext) for ext in [".gif", ".jpg", ".jpeg", ".png", ".webp", ".bmp"]):
                            raw_src = href

                # img 태그 자체의 속성 탐색
                if not raw_src:
                    for attr in ["data-org-src", "data-src", "data-original", "data-lazy-src", "data-url", "data-echo", "data-fallback-src", "src"]:
                        val = img.get(attr)
                        if val and not val.startswith("data:image"):
                            raw_src = str(val).strip()
                            break

                if not raw_src:
                    srcset = img.get("srcset") or img.get("data-srcset")
                    if srcset:
                        raw_src = str(srcset).split(",")[0].strip().split(" ")[0]

                # UI 플레이스홀더(gif_load.png 등), 버튼, 아이콘 등 비본문 템플릿 이미지 필터링
                if raw_src and not any(k in raw_src.lower() for k in ["gif_load", "loading", "icon", "btn", "logo", "banner", "ad.", "emoji", "emoticon", "drag", "photo_drag", "blank.gif", "dot.gif", "transparent.gif", "clear.gif"]):
                    full_img_url = urljoin(base_url, raw_src)
                    token = f"{{{{HORUS_IMG:{img_idx}:{full_img_url}}}}}"
                    extracted_images.append({
                        "order_index": img_idx,
                        "placeholder_token": token,
                        "placeholder_key": f"HORUS_IMG_{img_idx}",
                        "image_url": full_img_url,
                        "status": "PENDING"
                    })
                    # <img> 태그 또는 부모 <a> 태그를 표식 문자열로 교체
                    replace_target = parent_a if (parent_a and parent_a.name == "a" and len(parent_a.find_all(True)) <= 1) else img
                    replace_target.replace_with(soup.new_string(f"\n\n{token}\n\n"))
                    img_idx += 1
                else:
                    img.decompose()

            content_text = target.get_text(separator="\n", strip=True)
            content_text = re.sub(r"\n{3,}", "\n\n", content_text)
            return content_text, extracted_images

        except Exception as e:
            logger.error(f"Failed to extract content with placeholders: {e}")
            return "", []

    def fast_clean_text(self, html: str, content_selector: Optional[str] = None, base_url: str = "") -> Optional[str]:
        """
        1. 지정된 CSS Selector 우선 추출 (이미지 표식 보존 지원)
        2. 네이버 뉴스 등 대표 한국 언론사 본문 셀렉터 지원
        3. Trafilatura 폴백
        """
        content_with_flags, _ = self.extract_content_with_placeholders(html, base_url=base_url, content_selector=content_selector)
        if content_with_flags and len(content_with_flags) > 20:
            return content_with_flags

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "aside"]):
                tag.decompose()

            if content_selector:
                target = soup.select_one(content_selector)
                if target:
                    return target.get_text(separator="\n", strip=True)

            for selector in ["#dic_area", "#articeBody", "#newsEndContents", ".article_body", ".article-body", "#article-view"]:
                target = soup.select_one(selector)
                if target:
                    return target.get_text(separator="\n", strip=True)

            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_recall=True
            )
            return extracted if extracted else soup.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return None

    def extract_native_metadata(self, html: str, url: str, hints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        HTML 메타태그 및 힌트(title_selector, author_selector, date_selector, views_selector, category_selector, image_selector)를
        우선 적용하여 제목/작성일자/작성자/조회수/카테고리/이미지 고속 파싱
        """
        import re
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        hints = hints or {}
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. 제목 추출 (힌트 우선 -> OpenGraph -> H1)
        title = ""
        if hints.get("title_selector"):
            target = soup.select_one(hints["title_selector"])
            if target:
                t_copy = copy.copy(target)
                for noise in t_copy.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["comment", "cnt", "reply", "badge", "count"])):
                    noise.decompose()
                title = t_copy.get_text(separator=" ", strip=True)
                title = re.sub(r"\s*\[?\d+\]?\s*$", "", title).strip()
                title = re.sub(r"\s+", " ", title).strip()
        if not title:
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif soup.find("h1"):
                title = soup.find("h1").get_text(strip=True)
            elif soup.title:
                title = soup.title.get_text(strip=True)

        # 2. 카테고리/게시판명 추출
        category_name = hints.get("category", "")
        if hints.get("category_selector"):
            cat_elem = soup.select_one(hints["category_selector"])
            if cat_elem:
                category_name = cat_elem.get_text(strip=True)
        if not category_name:
            cat_tag = soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["board_name", "category", "board_title", "sub_title", "channel"]))
            if cat_tag:
                category_name = cat_tag.get_text(strip=True)[:30]

        # 3. 작성자 / 닉네임 추출 (힌트 우선 -> 커뮤니티 특화 태그 -> 메타태그)
        author = ""
        if hints.get("author_selector"):
            target = soup.select_one(hints["author_selector"])
            if target:
                author = self.clean_extracted_author(target, base_url=url)

        if not author:
            # 커뮤니티 특화 셀렉터 우선 검색 (내부 UI 노이즈 및 이미지 닉네임 대응)
            comm_author = soup.select_one(".topTitle-name a, a.baseList-name, .topTitle-name, .post_contact, .nickname, .user_name, .author, span.member, .writer_info, .writer, .post_author, .view_info, .info_author, .user_id, span[class*='nick'], span[class*='author'], div[class*='author']")
            if comm_author:
                author = self.clean_extracted_author(comm_author, base_url=url)

        if not author:
            og_author = soup.find("meta", property="og:article:author") or soup.find("meta", attrs={"name": "author"})
            if og_author and og_author.get("content"):
                author = self.clean_text_duplicates(og_author["content"].strip())

        og_site = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "publisher"})
        publisher = og_site["content"].strip() if og_site and og_site.get("content") else ""
        if not author and publisher:
            author = publisher

        # 4. 작성일자 & 수정일자 추출 (힌트 우선 -> 정규표현식 -> 메타태그)
        pub_date = None
        mod_date = None
        if hints.get("date_selector"):
            for target in soup.select(hints["date_selector"]):
                date_str = target.get("data-date-time") or target.get("datetime") or target.get_text(separator=" ", strip=True)
                pub_date = self.parse_flexible_date(date_str)
                if pub_date:
                    break

        if not pub_date:
            # 커뮤니티 특화 등록일/작성일 태그 검색 (ul.topTitle-mainbox li, .wt_box li, span.number, .post_date, time 등)
            for cand_elem in soup.select("ul.topTitle-mainbox li, .wt_box li, span.number, .post_date, .datestamp, .date, time, td[class*='date'], span[class*='date'], div[class*='date'], li.right"):
                text_c = cand_elem.get_text(separator=" ", strip=True)
                pub_date = self.parse_flexible_date(text_c)
                if pub_date:
                    break

        if not pub_date:
            meta_pub = (
                soup.find("meta", property="article:published_time")
                or soup.find("meta", attrs={"name": "pubdate"})
                or soup.find("meta", attrs={"name": "article:published"})
            )
            if meta_pub and meta_pub.get("content"):
                pub_date = self.parse_flexible_date(meta_pub["content"])

        # 5. 조회수(views) 추출
        views = ""
        if hints.get("views_selector"):
            for view_elem in soup.select(hints["views_selector"]):
                views_raw = view_elem.get_text(separator=" ", strip=True)
                v_match = re.search(r"(?:조회\s*수?|views?|hit)?\s*[:：]?\s*([\d,]+)", views_raw, re.IGNORECASE)
                if v_match and v_match.group(1):
                    # 날짜나 연도(2026 등)가 아닌 순수 조회수 숫자 추출
                    views = v_match.group(1)
                    if "조회" in views_raw or len(views) <= 7:
                        break
        if not views:
            # 커뮤니티 공통 조회수 패턴 탐색 (예: "조회 수 79", "조회 180", "180")
            for view_tag in soup.select("li.right, .view_count, .hit, .views, .read_count, .wt_box li"):
                text_v = view_tag.get_text(separator=" ", strip=True)
                if "조회" in text_v:
                    v_match = re.search(r"([\d,]+)", text_v)
                    if v_match:
                        views = v_match.group(1)
                        break

        # 6. 대표 이미지 (og:image)
        og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        image_url = None
        if og_image and og_image.get("content"):
            image_url = urljoin(url, og_image["content"].strip())

        # 7. 본문 내 모든 첨부 이미지 목록 (image_selector 또는 자동 탐색)
        images = []
        img_selector = hints.get("image_selector") or "article img, #dic_area img, #articeBody img, .article_body img, #article-view img, .post_content img, .post_article img, td.han img, div[itemprop='articleBody'] img"
        try:
            # 1. data-org-src 속성을 가진 고화질/원본 앵커 탐색
            for org_node in soup.select("a[data-org-src], a.btn_show_org, *[data-org-src]"):
                raw_src = org_node.get("data-org-src") or org_node.get("data-original") or org_node.get("data-gif")
                if raw_src and not any(k in raw_src.lower() for k in ["icon", "btn", "logo", "banner", "gif_load", "loading", "blank.gif", "dot.gif"]):
                    full_img = urljoin(url, raw_src)
                    if full_img not in images:
                        images.append(full_img)

            # 2. 일반 <img> 태그 탐색
            for img in soup.select(img_selector):
                parent_a = img.find_parent("a")
                raw_src = None
                if parent_a and parent_a.get("data-org-src"):
                    raw_src = parent_a["data-org-src"]
                elif parent_a and parent_a.get("href") and any(str(parent_a["href"]).lower().endswith(ext) for ext in [".gif", ".jpg", ".jpeg", ".png", ".webp"]):
                    raw_src = parent_a["href"]

                if not raw_src:
                    for attr in ["data-org-src", "data-src", "data-original", "data-lazy-src", "data-url", "data-echo", "src"]:
                        val = img.get(attr)
                        if val and not val.startswith("data:image"):
                            raw_src = val.strip()
                            break
                if not raw_src:
                    srcset = img.get("srcset") or img.get("data-srcset")
                    if srcset:
                        raw_src = str(srcset).split(",")[0].strip().split(" ")[0]

                if raw_src and not any(k in raw_src.lower() for k in ["icon", "btn", "logo", "banner", "ad.", "emoji", "emoticon", "gif_load", "loading", "drag", "photo_drag", "blank.gif", "dot.gif"]):
                    full_img = urljoin(url, raw_src)
                    if full_img not in images:
                        images.append(full_img)
        except Exception:
            pass

        # 대표 이미지가 없고 본문 이미지가 있으면 첫 번째 이미지를 대표 이미지로 사용
        if not image_url and images:
            image_url = images[0]

        # 8. 메타 설명문 (og:description)
        og_desc = ""
        meta_desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if meta_desc_tag and meta_desc_tag.get("content"):
            og_desc = str(meta_desc_tag["content"]).strip()

        # 9. 표준 URL (canonical)
        canonical_url = url
        link_canonical = soup.find("link", rel="canonical") or soup.find("meta", property="og:url")
        if link_canonical and link_canonical.get("href"):
            canonical_url = urljoin(url, str(link_canonical["href"]).strip())
        elif link_canonical and link_canonical.get("content"):
            canonical_url = urljoin(url, str(link_canonical["content"]).strip())

        # 10. 문서 고유의 전체 헤더 메타태그 수집 (모든 값은 순수 문자열로 변환)
        raw_meta_tags = {}
        for tag in soup.find_all("meta"):
            prop = tag.get("property") or tag.get("name") or tag.get("http-equiv")
            content = tag.get("content")
            if prop and content:
                raw_meta_tags[str(prop).strip()] = str(content).strip()

        header_meta = {
            "og_site_name": str(publisher or raw_meta_tags.get("og:site_name", "")),
            "og_type": str(raw_meta_tags.get("og:type", "article")),
            "og_title": str(raw_meta_tags.get("og:title", title)),
            "title": str(soup.title.string.strip() if soup.title and soup.title.string else title),
            "og_description": str(og_desc or raw_meta_tags.get("og:description", "")),
            "description": str(raw_meta_tags.get("description") or og_desc or ""),
            "og_image": str(image_url or raw_meta_tags.get("og:image", "")),
            "og_url": str(raw_meta_tags.get("og:url", url)),
            "canonical_url": str(canonical_url),
            "raw_meta_tags": raw_meta_tags
        }

        return {
            "title": title,
            "author": author or "미지정",
            "publisher": publisher,
            "published_at": pub_date,
            "modified_at": mod_date,
            "views": views,
            "category_name": category_name,
            "image_url": image_url,
            "images": images,
            "og_description": og_desc,
            "og_site_name": publisher,
            "canonical_url": canonical_url,
            "header_meta": header_meta
        }

    def extract_comprehensive(self, url: str, raw_html: str, hints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        기사 본문 및 전체 확장 메타데이터를 정밀 추출합니다. (Dry-run 및 상세 검사 뷰어용)
        """
        hints = hints or {}
        content_sel = hints.get("content_selector")
        cleaned_text, extracted_images = self.extract_content_with_placeholders(raw_html, base_url=url, content_selector=content_sel)
        if not cleaned_text:
            cleaned_text = self.fast_clean_text(raw_html, content_selector=content_sel, base_url=url) or ""

        native_meta = self.extract_native_metadata(raw_html, url, hints=hints)

        # 글자 수 및 읽기 시간 계산
        char_count = len(cleaned_text)
        reading_time = max(1, round(char_count / 500))  # 한글 기준 분당 ~500자

        # 원본 HTML 크기 (KB)
        html_size_kb = round(len(raw_html.encode("utf-8")) / 1024, 1)

        # 간단한 요약문 추출
        preview_text = cleaned_text[:300] + ("..." if len(cleaned_text) > 300 else "")
        summary = native_meta.get("og_description") or preview_text

        # 추출된 이미지 URL 리스트
        all_images = native_meta.get("images", [])
        for item in extracted_images:
            if item["image_url"] not in all_images:
                all_images.append(item["image_url"])

        return {
            "url": url,
            "title": native_meta.get("title") or "제목 없음",
            "content": cleaned_text,
            "content_preview": preview_text,
            "summary": summary,
            "author": native_meta.get("author") or "미지정",
            "publisher": native_meta.get("publisher") or "미지정",
            "published_at": native_meta["published_at"].strftime("%Y-%m-%d %H:%M:%S") if native_meta.get("published_at") else None,
            "category": native_meta.get("category_name") or hints.get("category", "news"),
            "views": native_meta.get("views") or "",
            "sentiment_score": 0.0,
            "key_entities": [],
            "related_stocks": [],
            "image_url": native_meta.get("image_url") or (all_images[0] if all_images else None),
            "images": all_images,
            "extracted_images": extracted_images,
            "og_description": native_meta.get("og_description"),
            "og_site_name": native_meta.get("og_site_name"),
            "canonical_url": native_meta.get("canonical_url", url),
            "char_count": char_count,
            "reading_time_minutes": reading_time,
            "raw_html_size_kb": html_size_kb,
            "image_descriptions": {},
            "header_meta": native_meta.get("header_meta", {}),
        }

    async def extract_comprehensive_async(
        self,
        url: str,
        raw_html: str,
        hints: Optional[Dict[str, Any]] = None,
        enable_vision: bool = False,
        vision_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        비동기 기사 본문 및 메타데이터 정밀 추출 (Vision LLM 이미지 텍스트 변환 및 본문 표식 치환 지원)
        """
        base_result = self.extract_comprehensive(url, raw_html, hints=hints)
        
        if enable_vision and base_result.get("images"):
            from crawler.vision_transcriber import VisionTranscriber
            transcriber = VisionTranscriber(model_name=vision_model)
            image_descriptions = await transcriber.describe_images_batch(
                image_urls=base_result["images"],
                model_name=vision_model,
                referer=url
            )
            if image_descriptions:
                base_result["image_descriptions"] = image_descriptions
                
                # 🌟 본문 내 이미지 위치 표식({{HORUS_IMG:idx:url}})을 실시간으로 [🖼️ 첨부 이미지 #idx 내용: ...]으로 교체!
                updated_content = base_result["content"]
                for item in base_result.get("extracted_images", []):
                    token = item["placeholder_token"]
                    img_url = item["image_url"]
                    idx = item["order_index"]
                    if img_url in image_descriptions:
                        desc = image_descriptions[img_url]
                        replacement = f"\n\n[🖼️ 첨부 이미지 #{idx} 내용: {desc}]\n\n"
                        updated_content = updated_content.replace(token, replacement)

                # 만약 표식이 없었으나 이미지가 있는 경우 하단에 주입
                if not any(item["placeholder_token"] in base_result["content"] for item in base_result.get("extracted_images", [])):
                    updated_content = transcriber.inject_descriptions_into_content(
                        content_text=updated_content,
                        image_descriptions=image_descriptions
                    )

                base_result["content"] = updated_content
                base_result["char_count"] = len(updated_content)

        return base_result


    async def extract_structured(self, url: str, raw_html: str, hints: Optional[Dict[str, Any]] = None, use_llm: bool = False) -> Optional[ExtractedArticle]:
        hints = hints or {}
        content_sel = hints.get("content_selector")
        cleaned_text = self.fast_clean_text(raw_html, content_selector=content_sel)
        if not cleaned_text or len(cleaned_text) < 10:
            return None

        # 기본 메타데이터 네이티브 추출 (0% GPU 고속 CPU 파싱)
        native_meta = self.extract_native_metadata(raw_html, url, hints=hints)

        if not use_llm:
            # 🚀 크롤링 단계: 초고속 네이티브 모드 (GPU 부하 0%, LLM 가공은 분리형 백그라운드 워커로 위임)
            return ExtractedArticle(
                title=native_meta.get("title") or "제목 없음",
                content=cleaned_text,
                summary=None,
                author=native_meta.get("author"),
                published_at=native_meta.get("published_at") or datetime.now(),
                category=hints.get("category", "news"),
                sentiment_score=None,
                key_entities=[],
                related_stocks=[]
            )

        # 🌟 테스트 프리뷰 또는 명시적 LLM 추출 요청 시에만 Ollama 호출
        prompt = f"""
다음은 웹페이지에서 추출한 텍스트입니다. 기사의 핵심 메타데이터와 본문을 정제하여 JSON 형식으로 출력하세요.

URL: {url}
힌트: {json.dumps(hints or {}, ensure_ascii=False)}

[텍스트 내용]:
{cleaned_text[:4000]}

반드시 아래 JSON 스키마에 맞춰 응답하세요:
{{
  "title": "기사 제목",
  "content": "정제된 기사 본문 텍스트 (광고, 기자 이메일, 저작권 문구 제외)",
  "summary": "1~2문장 요약",
  "author": "기자 이름 또는 언론사/출처",
  "published_at": "YYYY-MM-DDTHH:MM:SS",
  "category": "economy/tech/society/general 중 택 1",
  "sentiment_score": 0.0,
  "key_entities": ["엔티티1", "엔티티2"],
  "related_stocks": ["종목명1"]
}}
"""
        # 1. Local Ollama 또는 Gemini 호출
        response_json_str = await self._call_llm(prompt)
        
        if not response_json_str:
            # LLM 미구동 시 네이티브 추출 데이터로 안전한 기본 반환 (크롤링 중단 방지)
            return ExtractedArticle(
                title=native_meta.get("title") or "제목 없음",
                content=cleaned_text,
                summary=cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text,
                author=native_meta.get("author"),
                published_at=native_meta.get("published_at") or datetime.now(),
                category=hints.get("category", "news"),
                sentiment_score=0.0,
                key_entities=[],
                related_stocks=[]
            )

        try:
            cleaned_json = response_json_str.strip("` \n").replace("json\n", "")
            data = json.loads(cleaned_json)
            
            # published_at 파싱
            pub_date = native_meta.get("published_at") or datetime.now()
            if data.get("published_at"):
                try:
                    pub_date = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
                except Exception:
                    pass

            return ExtractedArticle(
                title=data.get("title") or native_meta.get("title", "제목 없음"),
                content=data.get("content", cleaned_text),
                summary=data.get("summary"),
                author=data.get("author") or native_meta.get("author"),
                published_at=pub_date,
                category=data.get("category", "general"),
                sentiment_score=float(data.get("sentiment_score", 0.0)),
                key_entities=data.get("key_entities", []),
                related_stocks=data.get("related_stocks", [])
            )
        except Exception as e:
            logger.error(f"Failed to parse LLM structured output: {e}\nRaw output: {response_json_str}")
            return ExtractedArticle(
                title=native_meta.get("title") or "제목 없음",
                content=cleaned_text,
                summary=cleaned_text[:200],
                author=native_meta.get("author"),
                published_at=native_meta.get("published_at") or datetime.now(),
                category="news",
                sentiment_score=0.0
            )

    async def _call_llm(self, prompt: str) -> Optional[str]:
        # Local Ollama 시도
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": config.OLLAMA_MODEL, "prompt": prompt, "format": "json", "stream": False}
                )
                if res.status_code == 200:
                    return res.json().get("response")
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")

        # Gemini Fallback
        if self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                model = genai.GenerativeModel(config.GEMINI_MODEL)
                res = await model.generate_content_async(prompt)
                return res.text
            except Exception as e:
                logger.error(f"Gemini fallback failed: {e}")

        return None
