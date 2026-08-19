import json
import logging
import random
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import httpx

from crawler.config import config
from crawler.fetcher import ContentFetcher
from crawler.extractor import AIExtractor

logger = logging.getLogger(__name__)

def sanitize_css_selector(sel: Optional[str]) -> str:
    """
    LLM이 생성한 CSS Selector에서 주석, 설명 문장, 백틱 등을 정제하고 순수 셀렉터만 반환합니다.
    """
    if not sel:
        return ""
    s = str(sel).strip()
    s = s.strip("`'\" \n\r\t")

    # 주석이나 에러 메시지/설명문이 들어간 경우 빈 문자열로 처리
    if (
        s.startswith("/*") or s.startswith("//") or s.startswith("# ")
        or "warning" in s.lower() or "cannot" in s.lower()
        or "not determined" in s.lower() or "not found" in s.lower()
        or "provided dom" in s.lower()
    ):
        return ""

    # 줄바꿈이 있거나 너무 긴 문장인 경우
    if "\n" in s or (len(s.split()) > 7 and any(w in s.lower() for w in ["the", "this", "selector", "contains", "element"])):
        return ""

    return s

class DOMSimplifier:
    """
    HTML 문서를 LLM이 분석하기 좋은 간결한 DOM 계층 구조 및 CSS 클래스/ID 스켈레톤으로 압축합니다.
    상단 네비게이션/헤더 등 노이즈를 적극 제거하고 실제 게시글 목록/본문 컨테이너를 포커싱합니다.
    """
    @staticmethod
    def simplify_html_for_list(html: str, max_length: int = 15000) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "svg", "path", "noscript", "iframe", "header", "footer", "nav", "aside", "form", "button"]):
            tag.decompose()

        for noise in list(soup.find_all(attrs={"class": True})):
            if getattr(noise, "attrs", None) is None or getattr(noise, "decomposed", False):
                continue
            cls_raw = noise.get("class", [])
            cls_str = " ".join(cls_raw if isinstance(cls_raw, list) else [str(cls_raw)]).lower()
            if any(k in cls_str for k in ["nav", "menu", "gnb", "lnb", "header", "footer", "sidebar", "banner", "ad_", "advertisement", "modal", "dropdown", "popup"]):
                if not any(k in cls_str for k in ["list", "board", "post", "article", "table", "item", "content", "subject", "title"]):
                    noise.decompose()

        for noise in list(soup.find_all(attrs={"id": True})):
            if getattr(noise, "attrs", None) is None or getattr(noise, "decomposed", False):
                continue
            id_str = str(noise.get("id", "")).lower()
            if any(k in id_str for k in ["nav", "menu", "gnb", "lnb", "header", "footer", "sidebar", "banner", "ad_", "advertisement", "modal", "dropdown", "popup"]):
                if not any(k in id_str for k in ["list", "board", "post", "article", "table", "item", "content", "subject", "title"]):
                    noise.decompose()

        body = soup.body or soup
        lines = []

        def traverse(elem, depth=0):
            if depth > 8 or len("".join(lines)) > max_length:
                return
            for child in elem.children:
                if child.name:
                    tag_name = child.name
                    cls = ".".join(child.get("class", [])) if child.get("class") else ""
                    id_attr = f"#{child.get('id')}" if child.get("id") else ""
                    href = f" href='{child.get('href')[:40]}...'" if child.name == "a" and child.get("href") else ""

                    text_snippet = child.get_text(separator=" ", strip=True)[:40]
                    text_str = f" \"{text_snippet}\"" if text_snippet and len(child.find_all()) == 0 else ""

                    indent = "  " * depth
                    line = f"{indent}<{tag_name}{id_attr}{('.' + cls) if cls else ''}{href}>{text_str}"
                    lines.append(line)

                    traverse(child, depth + 1)

        traverse(body, 0)
        result = "\n".join(lines)
        return result[:max_length]

    @staticmethod
    def simplify_html_for_article(html: str, max_length: int = 12000) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "svg", "path", "noscript", "iframe", "header", "footer", "nav", "aside"]):
            tag.decompose()

        for noise in list(soup.find_all(attrs={"class": True})):
            if getattr(noise, "attrs", None) is None or getattr(noise, "decomposed", False):
                continue
            cls_raw = noise.get("class", [])
            cls_str = " ".join(cls_raw if isinstance(cls_raw, list) else [str(cls_raw)]).lower()
            if any(k in cls_str for k in ["comment", "reply", "sidebar", "banner", "ad_", "recommend", "footer", "header", "nav"]):
                noise.decompose()

        body = soup.body or soup
        lines = []

        def traverse(elem, depth=0):
            if depth > 8 or len("".join(lines)) > max_length:
                return
            for child in elem.children:
                if child.name:
                    tag_name = child.name
                    cls = ".".join(child.get("class", [])) if child.get("class") else ""
                    id_attr = f"#{child.get('id')}" if child.get("id") else ""

                    text_snippet = child.get_text(separator=" ", strip=True)[:60]
                    text_str = f" \"{text_snippet}\"" if text_snippet and len(child.find_all()) == 0 else ""

                    indent = "  " * depth
                    line = f"{indent}<{tag_name}{id_attr}{('.' + cls) if cls else ''}>{text_str}"
                    lines.append(line)

                    traverse(child, depth + 1)

        traverse(body, 0)
        return "\n".join(lines)[:max_length]

class AIWrapperSynthesizer:
    """
    LLM과 텍스트 밀도 알고리즘을 활용하여 웹사이트의 기사 목록 및 상세 본문/메타데이터를
    정밀하게 추출할 수 있는 최적 CSS Selector 래퍼(Wrapper)를 스스로 합성합니다.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or getattr(config, "OLLAMA_MODEL", "gemma4:12b-mlx")
        self.ollama_url = getattr(config, "OLLAMA_BASE_URL", getattr(config, "OLLAMA_URL", "http://localhost:11434")) or "http://localhost:11434"

    async def _call_llm(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Local Ollama LLM 호출 (GPU 연산 수행)"""
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 1024,
                        }
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("response", "").strip()
        except Exception as e:
            logger.error(f"Local Ollama call failed: {e}")

        # Gemini Cloud Fallback
        try:
            from app.llm.gemini_client import gemini_client
            if gemini_client and gemini_client.is_configured():
                full_prompt = f"{system_prompt}\n\n{prompt}"
                gemini_res = await gemini_client.generate(full_prompt)
                return gemini_res.get("response_text", "") if isinstance(gemini_res, dict) else str(gemini_res)
        except Exception as ge:
            logger.debug(f"Gemini fallback skipped/failed: {ge}")

        return None

    @staticmethod
    def extract_header_metadata(soup: BeautifulSoup, base_url: str = "") -> Dict[str, Any]:
        """
        HTML 문서의 <head> 및 메타태그에서 OpenGraph, Twitter Cards, Canonical, Meta Description 등
        문서 고유의 정밀 메타데이터를 100% 수집합니다.
        """
        meta_data: Dict[str, Any] = {}

        for tag in soup.find_all("meta"):
            prop = tag.get("property") or tag.get("name") or tag.get("http-equiv")
            content = tag.get("content")
            if prop and content:
                meta_data[prop.strip()] = content.strip()

        og_site_name = meta_data.get("og:site_name") or meta_data.get("twitter:site") or ""
        og_title = meta_data.get("og:title") or meta_data.get("twitter:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
        og_desc = meta_data.get("og:description") or meta_data.get("description") or meta_data.get("twitter:description") or ""
        og_image = meta_data.get("og:image") or meta_data.get("twitter:image") or ""
        if og_image and base_url:
            og_image = urljoin(base_url, og_image)

        og_url = meta_data.get("og:url") or meta_data.get("twitter:url") or base_url

        canonical_tag = soup.find("link", rel="canonical")
        canonical_url = urljoin(base_url, canonical_tag.get("href").strip()) if canonical_tag and canonical_tag.get("href") else og_url

        title_tag = soup.title.string.strip() if soup.title and soup.title.string else og_title

        return {
            "og_site_name": og_site_name,
            "og_type": meta_data.get("og:type", "article"),
            "og_title": og_title,
            "title": title_tag,
            "og_description": og_desc,
            "description": meta_desc if (meta_desc := meta_data.get("description")) else og_desc,
            "og_image": og_image,
            "og_url": og_url,
            "canonical_url": canonical_url,
            "raw_meta_tags": meta_data,
        }

    @staticmethod
    def find_best_content_candidates(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        메뉴/네비게이션/광고/댓글을 배제하고, 순수 본문 텍스트 밀도가 가장 높은 컨테이너 후보 top 5를 스코어링합니다.
        (뽐뿌의 td.han, td.board-contents, .pic_bg, 클리앙의 .post_article, 일반 언론사의 #dic_area 등 자동 특정)
        """
        import copy
        clean_soup = copy.copy(soup)
        for tag in clean_soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            tag.decompose()

        # 댓글 및 메모 작성/드래그앤드롭 영역 전수 제거 (노이즈 원천 차단)
        for noise in list(clean_soup.find_all(id=lambda i: i and any(k in str(i).lower() for k in ["comment", "reply", "memo_", "cmt_"]))):
            noise.decompose()
        for noise in list(clean_soup.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["comment", "reply", "memo_", "cmt_", "reply_area", "d_drag", "photo_drag", "sidebar", "banner", "menu", "nav", "footer", "ad_"]))):
            noise.decompose()

        candidates = []
        for tag in clean_soup.find_all(["td", "article", "section", "div", "p"]):
            # 전체 화면 레이아웃/래퍼 컨테이너는 본문 후보에서 배제
            cls_list = tag.get("class", [])
            cls_str = " ".join(cls_list if isinstance(cls_list, list) else [str(cls_list)]).lower()
            tag_id = str(tag.get("id", "")).lower()

            if any(cls_str == w or cls_str.startswith(w + " ") for w in ["wrapper", "contents", "container", "wrap", "main", "body", "layout", "toptitle"]):
                continue
            if tag_id in ["wrapper", "contents", "container", "wrap", "main", "body", "layout", "toptitle", "header"]:
                continue

            text = tag.get_text(separator=" ", strip=True)
            text_len = len(text)
            if text_len < 20:
                continue

            # 링크 텍스트 비율 (낮을수록 순수 본문)
            links_text_len = sum(len(a.get_text(strip=True)) for a in tag.find_all("a"))
            link_ratio = links_text_len / max(1, text_len)
            if link_ratio > 0.35:
                continue

            score = text_len * (1.0 - link_ratio)

            # 클래스/ID 기반 본문 특화 보너스 점수
            for bonus_kw in ["han", "board-contents", "pic_bg", "view_content", "post_article", "post_content", "articleBody", "article_body", "dic_area", "content", "view_body"]:
                if bonus_kw in cls_str or bonus_kw in tag_id:
                    score += 500

            # 고유 셀렉터 생성
            selector = ""
            if tag_id:
                selector = f"#{tag_id}"
            elif cls_list:
                selector = f"{tag.name}.{cls_list[0]}"
            else:
                selector = tag.name

            candidates.append({
                "selector": selector,
                "score": round(score, 1),
                "text_length": text_len,
                "preview": text[:120] + "...",
                "img_count": len(tag.find_all("img")),
            })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        unique_candidates = []
        seen = set()
        for c in candidates:
            if c["selector"] not in seen and c["selector"] not in ["body", "html", "table", "tbody", "div.wrapper", "div.contents", "div.container", "div.wrap"]:
                seen.add(c["selector"])
                unique_candidates.append(c)
            if len(unique_candidates) >= 4:
                break

        return unique_candidates

    async def synthesize_from_anchors(
        self,
        list_url: str,
        list_html: str,
        positive_anchors: List[str],
        negative_anchors: Optional[List[str]] = None,
        sample_article_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        사용자가 지정한 기사 제목(Positive Anchors)을 기반으로 기사 목록 link_selector를 도출합니다.
        """
        soup = BeautifulSoup(list_html, "html.parser")
        candidate_selectors = []

        # 1. 앵커 텍스트를 포함하는 a 태그 탐색
        matched_anchors = []
        for pos_text in positive_anchors:
            pos_clean = pos_text.strip()
            if not pos_clean:
                continue
            for a in soup.find_all("a"):
                a_text = a.get_text(separator=" ", strip=True)
                if pos_clean in a_text or a_text in pos_clean:
                    matched_anchors.append(a)

        # 2. 공통 부모 컨테이너 및 CSS Selector 추출
        best_selector = ""
        reasoning = ""

        if matched_anchors:
            # 부모 태그들의 클래스/ID 빈도 분석
            parent_classes = []
            for a in matched_anchors:
                p = a.parent
                if p:
                    cls = p.get("class", [])
                    if cls:
                        parent_classes.append(".".join(cls))
            if parent_classes:
                from collections import Counter
                most_common = Counter(parent_classes).most_common(1)[0][0]
                best_selector = f".{most_common.split()[0]} a"
                reasoning = f"선택된 앵커 텍스트들의 공통 부모 클래스(등장 빈도: {len(matched_anchors)})를 기반으로 최적화되었습니다."

        if not best_selector:
            # 일반적인 목록 컨테이너 패턴 탐색
            for sel in ["table#revolution_main_table a", ".list_wrap a", ".board_list a", ".post_list a", ".article_list a", "table.board_list a", "ul.list_news a", "div.news_list a"]:
                if len(soup.select(sel)) >= 3:
                    best_selector = sel
                    reasoning = "일반적인 커뮤니티/뉴스 목록 테이블 패턴을 감지하여 도출되었습니다."
                    break

        if not best_selector:
            best_selector = "a[href*='view'], a[href*='article'], a[href*='board']"
            reasoning = "기사 상세 뷰 URL 패턴을 기반으로 셀렉터를 구성했습니다."

        # 3. 실시간 파싱 테스트 수행
        fetcher = ContentFetcher()
        from crawler.pipeline import CrawlPipeline
        pipeline = CrawlPipeline()
        extracted_items = []
        try:
            extracted_items = pipeline.extract_links_with_meta(list_url, list_html, link_selector=best_selector or None)
            if negative_anchors and extracted_items:
                filtered = []
                for item in extracted_items:
                    t = (item.get("title") or item.get("anchor_text") or "").lower()
                    if not any(n.strip().lower() in t for n in negative_anchors if n.strip()):
                        filtered.append(item)
                if filtered:
                    extracted_items = filtered
        except Exception as e:
            logger.warning(f"Test failed for synthesized selector '{best_selector}': {e}")

        target_article_url = sample_article_url or (extracted_items[0]["url"] if extracted_items else None)
        sample_article_preview = None
        content_selector = ""
        title_selector = ""
        author_selector = ""
        date_selector = ""

        if target_article_url:
            art_html = await fetcher.fetch_html(target_article_url)
            if art_html:
                art_soup = BeautifulSoup(art_html, "html.parser")
                candidates = self.find_best_content_candidates(art_soup)
                if candidates:
                    content_selector = candidates[0]["selector"]

                extractor = AIExtractor()
                hints = {
                    "content_selector": content_selector or None,
                    "title_selector": title_selector or None,
                    "author_selector": author_selector or None,
                    "date_selector": date_selector or None
                }
                art_data = extractor.extract_comprehensive(target_article_url, art_html, hints=hints)
                sample_article_preview = art_data

        await fetcher.close()
        await pipeline.close()

        confidence = 0.95 if (len(extracted_items) >= 2 and sample_article_preview) else (0.7 if extracted_items else 0.3)

        return {
            "status": "success" if confidence >= 0.5 else "warning",
            "model_used": self.model_name,
            "rules": {
                "link_selector": best_selector,
                "content_selector": content_selector,
                "title_selector": title_selector,
                "author_selector": author_selector,
                "date_selector": date_selector,
                "llm_model": self.model_name,
            },
            "reasoning": f"[앵커 텍스트 기반 맞춤 추론]: {reasoning}",
            "extractable_fields": ["title", "link", "author", "date", "content"],
            "sample_links_count": len(extracted_items),
            "sample_links": [item["url"] for item in extracted_items],
            "sample_items": extracted_items,
            "sample_article_preview": sample_article_preview,
            "confidence_score": confidence,
            "message": f"앵커 예시({len(positive_anchors)}건) 기반 최적 셀렉터 도출 완료! ({len(extracted_items)}건 수집)"
        }

    async def synthesize_article_metadata_multi_sample(
        self,
        sample_urls: List[str],
        base_rules: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        다수(5개 무작위)의 실제 상세 페이지를 교차 분석(Template Intersection)하여
        텍스트 밀도 알고리즘 + 헤더 메타태그 + LLM 하이브리드로 최적 CSS Selector 세트를 합성합니다.
        """
        if not sample_urls:
            return {"error": "분석할 상세 페이지 URL이 없습니다."}

        # 🌟 무작위(Random) 5개 문서 샘플링으로 공통 템플릿의 대표성 극대화
        if len(sample_urls) > 5:
            target_urls = random.sample(sample_urls, 5)
        else:
            target_urls = list(sample_urls)

        fetcher = ContentFetcher()
        extractor = AIExtractor()

        fetched_pages = []
        try:
            for url in target_urls:
                html = await fetcher.fetch_html(url)
                if html and len(html) > 500:
                    fetched_pages.append({"url": url, "html": html})
        finally:
            await fetcher.close()

        sample_dom_summaries = []
        all_content_candidates = []
        all_header_meta = []
        title_candidates_counter: Dict[str, int] = {}
        author_candidates_counter: Dict[str, int] = {}
        date_candidates_counter: Dict[str, int] = {}

        for idx, page in enumerate(fetched_pages):
            soup = BeautifulSoup(page["html"], "html.parser")
            header_meta = self.extract_header_metadata(soup, base_url=page["url"])
            content_candidates = self.find_best_content_candidates(soup)
            all_content_candidates.extend(content_candidates)
            all_header_meta.append(header_meta)

            # 1. 템플릿 교차 분석: 제목 후보 탐색
            for t_tag in soup.select("h1, #topTitle h1, div#topTitle h1, .view_title, .post_title, td.view_title, .sub_title"):
                p_id = t_tag.parent.get("id") if t_tag.parent else None
                t_sel = f"#{p_id} {t_tag.name}" if p_id else (f"div#topTitle {t_tag.name}" if soup.find(id="topTitle") else t_tag.name)
                if t_tag.get_text(strip=True):
                    title_candidates_counter[t_sel] = title_candidates_counter.get(t_sel, 0) + 1

            # 2. 템플릿 교차 분석: 작성자 후보 탐색
            for a_tag in soup.select(".topTitle-name a, a.baseList-name, .topTitle-name, .post_contact .nickname, .user_name, .author, span.name, .writer"):
                cls = a_tag.get("class", [])
                a_sel = f"{a_tag.name}.{cls[0]}" if isinstance(cls, list) and cls else (f"#{a_tag.get('id')}" if a_tag.get("id") else a_tag.name)
                if a_tag.get_text(strip=True):
                    author_candidates_counter[a_sel] = author_candidates_counter.get(a_sel, 0) + 1

            # 3. 템플릿 교차 분석: 작성일시 후보 탐색
            for d_tag in soup.select("ul.topTitle-mainbox li, .post_date, time, td[class*='date'], span[class*='date']"):
                t_str = d_tag.get_text(strip=True)
                if "등록일" in t_str or re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", t_str):
                    date_candidates_counter["ul.topTitle-mainbox li"] = date_candidates_counter.get("ul.topTitle-mainbox li", 0) + 1

            head_nodes = []
            for elem in soup.select("h1, h2, #topTitle, .topTitle-name, a.baseList-name, ul.topTitle-mainbox, .post_title, .title, td.han, .han, td.board-contents, .pic_bg, .post_contact, .post_date, .post_author, .nickname, .user_name, .name, .post_article, .post_content, article")[:25]:
                cls_str = ".".join(elem.get("class", [])) if isinstance(elem.get("class"), list) else str(elem.get("class", ""))
                tag_name = elem.name
                elem_text = elem.get_text(separator=" ", strip=True)[:80]
                head_nodes.append(f"<{tag_name} class='{cls_str}'>{elem_text}</{tag_name}>")

            cand_summary = ", ".join([f"{c['selector']} (점수: {c['score']}, 글자수: {c['text_length']})" for c in content_candidates[:3]])
            sample_dom_summaries.append(
                f"[문서 #{idx + 1}: {page['url']}]\n"
                f"- OpenGraph 제목: {header_meta.get('og_title')}\n"
                f"- OpenGraph 설명: {header_meta.get('og_description')[:80]}...\n"
                f"- 알고리즘 추천 순수 본문 컨테이너: {cand_summary}\n"
                f"- 주요 DOM 태그:\n" + "\n".join(head_nodes[:12])
            )

        joined_samples_text = "\n\n".join(sample_dom_summaries)

        prompt = f"""
당신은 웹 크롤러 정밀 파서 및 래퍼(Wrapper) 합성 전문 최고급 AI입니다.
다음은 동일한 웹사이트의 무작위 5개 실제 상세 페이지에서 추출한 [OpenGraph 헤더 메타], [알고리즘 추천 순수 본문 후보], [DOM 스켈레톤]입니다:

{joined_samples_text}

[🚨 중요 지침 - 절대 위반 금지]:
1. content_selector(본문 컨테이너):
   - 상단 네비게이션, 게시판 카테고리/목록, 사이드바, 광고를 절대 포함하지 마세요.
   - 🚨 특히 문서 하단의 댓글 영역(#comment_wrapper, #comment_list, .comment_box 등)은 문서마다 개수가 다르고 변동되는 영역이므로 절대 본문으로 잡지 마세요!
   - 글쓴이가 작성한 순수 본문 영역(예: 뽐뿌의 'td.han' 또는 'td.board-contents', 클리앙의 '.post_article', 언론사의 '#dic_area')만을 정확히 단독 지정하세요.
2. title_selector(제목): 글 제목 태그 (예: '#topTitle h1', '.post_title', 'h1', 'td.view_title')
3. author_selector(작성자): 글쓴이 닉네임 태그 (예: 'a.baseList-name', '.topTitle-name a', '.post_contact .nickname', 'span.name')
4. date_selector(작성일시): 작성일자 태그 (예: 'ul.topTitle-mainbox li', '.post_date', 'time')
5. views_selector(조회수): 조회수 태그 (예: 'ul.topTitle-mainbox li', '.view_count')

출력 형식 (반드시 유효한 JSON만 단독 출력):
```json
{{
  "title_selector": "순수 제목 CSS Selector",
  "author_selector": "작성자 CSS Selector",
  "date_selector": "작성일시 CSS Selector",
  "content_selector": "순수 본문 컨테이너 CSS Selector (댓글/메뉴 원천 배제)",
  "views_selector": "조회수 CSS Selector",
  "category_selector": "카테고리명 CSS Selector",
  "image_selector": "본문 이미지 CSS Selector",
  "reasoning": "댓글 및 메뉴가 배제된 순수 본문 및 메타 셀렉터 선정 근거"
}}
```
"""

        rules_dict = {
            "title_selector": "",
            "author_selector": "",
            "date_selector": "",
            "content_selector": "",
            "views_selector": "",
            "category_selector": "",
            "image_selector": "",
        }
        reasoning_text = ""

        # 템플릿 차분 분석 기본값 자동 지정
        if all_content_candidates:
            rules_dict["content_selector"] = all_content_candidates[0]["selector"]
        if title_candidates_counter:
            rules_dict["title_selector"] = max(title_candidates_counter, key=title_candidates_counter.get)
        if author_candidates_counter:
            rules_dict["author_selector"] = max(author_candidates_counter, key=author_candidates_counter.get)
        if date_candidates_counter:
            rules_dict["date_selector"] = max(date_candidates_counter, key=date_candidates_counter.get)

        try:
            llm_response = await self._call_llm(prompt, system_prompt="Output valid JSON only with pure CSS selector strings.")
            if llm_response:
                json_match = re.search(r"\{[\s\S]*\}", llm_response)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    for k in rules_dict.keys():
                        if parsed.get(k):
                            clean_sel = sanitize_css_selector(parsed[k])
                            if k == "content_selector" and (clean_sel in ["table", "body", "html", ".wrap", "#wrap", "div.contents", "div.wrapper", "div.container"] or clean_sel.endswith(" p")):
                                if all_content_candidates:
                                    clean_sel = all_content_candidates[0]["selector"]
                            if clean_sel:
                                rules_dict[k] = clean_sel
                    reasoning_text = parsed.get("reasoning", "")
        except Exception as e:
            logger.warning(f"Multi-sample synthesis LLM failed: {e}")

        # 도출된 규칙으로 5개 무작위 샘플 페이지를 즉시 정밀 파싱하여 검증 리스트 생성
        sample_previews = []
        for idx, page in enumerate(fetched_pages):
            parsed_data = extractor.extract_comprehensive(
                url=page["url"],
                raw_html=page["html"],
                hints=rules_dict
            )
            if idx < len(all_header_meta):
                parsed_data["header_meta"] = all_header_meta[idx]
            sample_previews.append(parsed_data)

        return {
            "rules": rules_dict,
            "reasoning": reasoning_text or f"무작위 {len(fetched_pages)}개 상세 페이지의 텍스트 밀도와 공통 DOM 구조를 분석하여 순수 본문 및 메타 규칙을 도출했습니다.",
            "analyzed_urls_count": len(fetched_pages),
            "sample_previews": sample_previews,
            "message": f"무작위 {len(fetched_pages)}개 상세 페이지 교차 분석 완료"
        }

    @staticmethod
    def reverse_find_css_selector(html: str, target_snippet: str, base_url: str = "", target_field: Optional[str] = "content_selector") -> Dict[str, Any]:
        """
        사용자가 웹페이지에서 복사하여 붙여넣은 텍스트 조각(target_snippet)을 HTML DOM에서 역추적하여
        가장 정확하고 고유한 CSS Selector와 부모 컨테이너를 찾아냅니다.
        """
        snippet = target_snippet.strip()
        if not snippet:
            return {"error": "역추적할 텍스트 문자열이 비어있습니다."}

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # 댓글 및 메모 작성/드래그앤드롭 영역 사전 배제
        for noise in list(soup.find_all(id=lambda i: i and any(k in str(i).lower() for k in ["comment", "reply", "memo_", "cmt_"]))):
            noise.decompose()
        for noise in list(soup.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["comment", "reply", "memo_", "cmt_", "reply_area", "d_drag", "photo_drag"]))):
            noise.decompose()

        best_match = None
        min_len_diff = float("inf")

        for elem in soup.find_all(True):
            elem_text = elem.get_text(separator=" ", strip=True)
            if snippet in elem_text:
                len_diff = len(elem_text) - len(snippet)
                if len_diff < min_len_diff and elem.name not in ["html", "body"]:
                    min_len_diff = len_diff
                    best_match = elem

        if not best_match:
            words = [w for w in snippet.split() if len(w) > 2][:4]
            if words:
                for elem in soup.find_all(True):
                    elem_text = elem.get_text(separator=" ", strip=True)
                    if all(w in elem_text for w in words):
                        len_diff = len(elem_text) - len(snippet)
                        if len_diff < min_len_diff and elem.name not in ["html", "body"]:
                            min_len_diff = len_diff
                            best_match = elem

        if not best_match:
            return {"error": "페이지 HTML 내에서 해당 텍스트를 찾지 못했습니다. 복사한 문자열을 다시 확인해주세요."}

        elem = best_match

        # 1. 본문 컨테이너(content_selector)인 경우: <p> 문단이나 span이 아닌 상위 본문 컨테이너(td.han, td.board-contents, .post_article)로 승격
        if target_field in ["content", "content_selector"]:
            curr = best_match
            while curr and curr.name not in ["html", "body", "table", "tbody"]:
                c_cls = " ".join(curr.get("class", [])) if isinstance(curr.get("class"), list) else str(curr.get("class", ""))
                c_id = str(curr.get("id", ""))
                if any(k in c_cls.lower() or k in c_id.lower() for k in ["han", "board-contents", "pic_bg", "post_article", "post_content", "view_content", "article_body", "article"]):
                    elem = curr
                    break
                curr = curr.parent

        # 2. 작성자(author_selector)인 경우: 가장 구체적인 닉네임 앵커/span 태그로 좁힘
        elif target_field in ["author", "author_selector"]:
            for child in best_match.find_all(["a", "span", "strong", "li"]):
                c_cls = " ".join(child.get("class", [])) if isinstance(child.get("class"), list) else str(child.get("class", ""))
                if any(k in c_cls.lower() for k in ["name", "nickname", "author", "user", "member", "writer"]):
                    elem = child
                    break

        cls_list = elem.get("class", [])
        cls_str = ".".join(cls_list) if isinstance(cls_list, list) and cls_list else ""
        tag_id = elem.get("id", "")

        suggested_selector = ""
        if tag_id:
            suggested_selector = f"#{tag_id}"
        elif cls_str:
            suggested_selector = f"{elem.name}.{cls_str.split()[0]}"
        else:
            parent = elem.parent
            if parent and parent.get("id"):
                suggested_selector = f"#{parent.get('id')} {elem.name}"
            elif parent and parent.get("class"):
                p_cls = parent.get("class")[0] if isinstance(parent.get("class"), list) else str(parent.get("class")).split()[0]
                suggested_selector = f"{parent.name}.{p_cls} {elem.name}"
            else:
                suggested_selector = elem.name

        return {
            "status": "success",
            "suggested_selector": suggested_selector,
            "tag_name": elem.name,
            "element_text_preview": elem.get_text(separator=" ", strip=True)[:150],
            "matched_snippet": snippet[:100],
            "message": f"CSS Selector 도출 성공: {suggested_selector}"
        }

class DOMElementInspector:
    """
    페이지 내 모든 앵커 텍스트/링크를 탐색하고,
    유사한 컨테이너(ul, table, div 등)별로 그룹핑하여 시각화 데이터를 생성합니다.
    """
    @staticmethod
    def inspect_page_links(html: str, base_url: str = "") -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        all_items = []
        for a in soup.find_all("a"):
            text = a.get_text(separator=" ", strip=True)
            href = a.get("href", "")
            if text and len(text) > 1 and not href.startswith("#") and not href.startswith("javascript"):
                all_items.append({
                    "anchor_text": text[:80],
                    "url": urljoin(base_url, href) if base_url else href,
                    "tag_name": "a"
                })

        groups = []
        group_id_counter = 1

        # 1. <table> 요소 그룹핑 (전형적인 게시판)
        for table in soup.find_all("table"):
            anchors = table.find_all("a")
            if len(anchors) >= 3:
                sample_anchors = []
                items = []
                for a in anchors[:20]:
                    text = a.get_text(separator=" ", strip=True)
                    href = a.get("href", "")
                    if text and len(text) > 1 and not href.startswith("#") and not href.startswith("javascript"):
                        full_url = urljoin(base_url, href) if base_url else href
                        items.append({"anchor_text": text[:80], "url": full_url, "tag_name": "a"})
                        if len(sample_anchors) < 5:
                            sample_anchors.append(text[:40])

                if len(items) >= 2:
                    table_id = table.get("id")
                    table_cls = ".".join(table.get("class", [])) if table.get("class") else ""
                    selector = f"#{table_id} a" if table_id else (f"table.{table_cls.split()[0]} a" if table_cls else "table a")

                    groups.append({
                        "group_id": f"grp_{group_id_counter}",
                        "selector": selector,
                        "container_tag": "table",
                        "container_class": table_cls,
                        "display_name": f"[게시글 목록 영역] table{f'#{table_id}' if table_id else ('.' + table_cls.split()[0] if table_cls else '')}",
                        "link_count": len(anchors),
                        "is_probable_article_list": True,
                        "sample_anchors": sample_anchors,
                        "items": items
                    })
                    group_id_counter += 1

        # 2. <ul> / <ol> 목록 컨테이너
        for ul in soup.find_all(["ul", "ol"]):
            anchors = ul.find_all("a")
            if 3 <= len(anchors) <= 100:
                sample_anchors = []
                items = []
                for a in anchors[:20]:
                    text = a.get_text(separator=" ", strip=True)
                    href = a.get("href", "")
                    if text and len(text) > 1 and not href.startswith("#") and not href.startswith("javascript"):
                        full_url = urljoin(base_url, href) if base_url else href
                        items.append({"anchor_text": text[:80], "url": full_url, "tag_name": "a"})
                        if len(sample_anchors) < 5:
                            sample_anchors.append(text[:40])

                if len(items) >= 2:
                    ul_id = ul.get("id")
                    ul_cls = ".".join(ul.get("class", [])) if ul.get("class") else ""
                    selector = f"#{ul_id} a" if ul_id else (f"{ul.name}.{ul_cls.split()[0]} a" if ul_cls else f"{ul.name} a")

                    is_menu = any(k in selector.lower() for k in ["menu", "nav", "gnb", "lnb", "footer", "header", "tab"])
                    groups.append({
                        "group_id": f"grp_{group_id_counter}",
                        "selector": selector,
                        "container_tag": ul.name,
                        "container_class": ul_cls,
                        "display_name": f"{'[메뉴/기타 영역]' if is_menu else '[목록 영역]'} {ul.name}{f'#{ul_id}' if ul_id else ('.' + ul_cls.split()[0] if ul_cls else '')}",
                        "link_count": len(anchors),
                        "is_probable_article_list": not is_menu,
                        "sample_anchors": sample_anchors,
                        "items": items
                    })
                    group_id_counter += 1

        # 3. <div> 반복 카드/목록 컨테이너
        for div in soup.find_all("div"):
            div_cls = ".".join(div.get("class", [])) if div.get("class") else ""
            if any(k in div_cls.lower() for k in ["list", "board", "post", "news", "feed", "card", "article"]):
                anchors = div.find_all("a")
                if len(anchors) >= 3:
                    sample_anchors = []
                    items = []
                    for a in anchors[:20]:
                        text = a.get_text(separator=" ", strip=True)
                        href = a.get("href", "")
                        if text and len(text) > 1 and not href.startswith("#") and not href.startswith("javascript"):
                            full_url = urljoin(base_url, href) if base_url else href
                            items.append({"anchor_text": text[:80], "url": full_url, "tag_name": "a"})
                            if len(sample_anchors) < 5:
                                sample_anchors.append(text[:40])

                    if len(items) >= 2:
                        selector = f"div.{div_cls.split()[0]} a"
                        if not any(g["selector"] == selector for g in groups):
                            groups.append({
                                "group_id": f"grp_{group_id_counter}",
                                "selector": selector,
                                "container_tag": "div",
                                "container_class": div_cls,
                                "display_name": f"[게시글 영역] div.{div_cls.split()[0]}",
                                "link_count": len(anchors),
                                "is_probable_article_list": True,
                                "sample_anchors": sample_anchors,
                                "items": items
                            })
                            group_id_counter += 1

        groups.sort(key=lambda x: (x["is_probable_article_list"], x["link_count"]), reverse=True)
        return {
            "groups": groups,
            "all_items": all_items,
            "total_links": len(all_items)
        }

class SmartAnchorPatternExtractor:
    """
    사용자가 선택/검색한 특정 타겟 앵커(예: '질문안받습니다')의 DOM 구조적 계층과 패턴을 분석하여,
    공지사항(Notice), 광고(AD), 사이드바/위젯을 자동으로 걸러내고
    순수 일반 게시글 본문 링크들만 완벽하게 묶어내는 고정밀 셀렉터 및 링크 그룹 추출기
    """
    @staticmethod
    def extract_same_group_by_anchor(html: str, target_snippet: str, base_url: str = "") -> Dict[str, Any]:
        snippet = target_snippet.strip()
        if not snippet:
            return {"error": "검색할 타겟 앵커 텍스트를 입력해주세요."}

        soup = BeautifulSoup(html, "html.parser")
        for tag in list(soup(["script", "style", "noscript", "iframe"])):
            tag.decompose()

        # 1. 타겟 앵커 찾기 (정확 매칭 -> 대소문자 무시 -> 서브스트링 매칭)
        target_a = None
        for a in soup.find_all("a"):
            a_text = a.get_text(separator=" ", strip=True)
            if snippet == a_text or (len(snippet) >= 2 and snippet.lower() in a_text.lower()):
                target_a = a
                break

        if not target_a:
            words = [w for w in snippet.split() if len(w) >= 2]
            for a in soup.find_all("a"):
                a_text = a.get_text(separator=" ", strip=True)
                if words and any(w in a_text for w in words):
                    target_a = a
                    break

        if not target_a:
            return {"error": f"페이지 내에서 '{snippet}' 앵커를 찾지 못했습니다. 목록에 존재하는 정확한 제목을 입력해주세요."}

        target_text = target_a.get_text(separator=" ", strip=True)
        target_href = target_a.get("href", "")

        candidates = []

        # 2. 계층 구조 분석 (Table, UL/OL, Div Card)
        parent_tr = target_a.find_parent("tr")
        parent_tbl = target_a.find_parent("table")
        parent_td = target_a.find_parent("td")

        # Case 1: 테이블(Table) 기반 게시판 구조 (코인판, 뽐뿌, 디시인사이드, 루리웹 등)
        if parent_tr and parent_tbl:
            td_cls_list = parent_td.get("class", []) if parent_td else []
            td_cls_str = f".{td_cls_list[0]}" if td_cls_list else ""

            # 번호(no, num) 열이 존재하는지 확인
            has_no_col = bool(parent_tbl.select("td.no, td.num, th.no, th.num, td[class*='no']"))
            # 공지사항(notice) 행이 존재하는지 확인
            has_notice = bool(parent_tbl.select("tr.notice, tr[class*='notice'], td.notice, td[class*='notice'], tr.head"))

            tr_prefix = "tr:not(.notice):not([class*='notice'])" if has_notice else "tr"

            if has_no_col and td_cls_str:
                candidates.append(f"td.no ~ td{td_cls_str} a:not([href*='#'])")
                candidates.append(f"tr:has(td.no) td{td_cls_str} a:not([href*='#'])")
                candidates.append(f"{tr_prefix} td.no ~ td{td_cls_str} a:not([href*='#'])")
                candidates.append(f"td.no ~ td{td_cls_str} > a:first-child")

            if td_cls_str:
                candidates.append(f"{tr_prefix} td{td_cls_str} a:not([href*='#'])")
                candidates.append(f"{tr_prefix} td{td_cls_str} > a:first-child")
                candidates.append(f"tbody {tr_prefix} td{td_cls_str} a")

            candidates.append(f"{tr_prefix} td.title a:not([href*='#'])")
            candidates.append(f"{tr_prefix} td.subject a:not([href*='#'])")

        # Case 2: 리스트(UL / OL) 기반 게시판 (클리앙, 에펨코리아, 네이버 카페 등)
        elif target_a.find_parent(["ul", "ol"]):
            ul = target_a.find_parent(["ul", "ol"])
            li = target_a.find_parent("li")
            a_cls_list = target_a.get("class", [])
            a_cls_str = f".{a_cls_list[0]}" if a_cls_list else ""
            ul_cls = ul.get("class", [])
            ul_prefix = f"{ul.name}.{ul_cls[0]} " if ul_cls else ""

            has_notice = bool(ul.select("li.notice, li[class*='notice'], li.ad"))
            li_prefix = "li:not(.notice)" if has_notice else "li"

            candidates.append(f"{ul_prefix}{li_prefix} a{a_cls_str}:not([href*='#'])")
            candidates.append(f"{ul_prefix}{li_prefix} a:not([href*='#'])")
            candidates.append(f"{li_prefix} a{a_cls_str}:not([href*='#'])")

        # Case 3: 일반 Div/Card 기반
        else:
            p_div = target_a.find_parent("div")
            div_cls = p_div.get("class", []) if p_div else []
            if div_cls:
                candidates.append(f"div.{div_cls[0]} a:not([href*='#'])")
                candidates.append(f"div.{div_cls[0]} a")

        # 3. 각 후보 셀렉터 정밀 시뮬레이션 및 점수화
        best_selector = None
        best_items = []
        best_score = -1
        excluded_notices = []

        for sel in candidates:
            try:
                matched_nodes = soup.select(sel)
                valid_items = []
                unique_hrefs = set()
                notices_found = []

                for node in matched_nodes:
                    text = node.get_text(separator=" ", strip=True)
                    href = node.get("href", "")
                    if not text or not href or href.startswith("javascript") or href.startswith("#"):
                        continue

                    # 공지사항/광고 키워드 배제
                    if any(bad in text for bad in ["공지", "[공지]", "이용규칙", "전체공지", "AD", "[AD]", "필독"]):
                        notices_found.append(text[:60])
                        continue

                    full_url = urljoin(base_url, href) if base_url else href
                    if full_url not in unique_hrefs:
                        unique_hrefs.add(full_url)
                        valid_items.append({
                            "anchor_text": text[:100],
                            "url": full_url,
                            "tag_name": "a"
                        })

                # 타겟 앵커가 포함되어 있는지 필수 검증
                contains_target = any(snippet in item["anchor_text"] for item in valid_items)
                if not contains_target:
                    continue

                item_count = len(valid_items)
                if item_count < 2:
                    continue

                score = item_count
                # 이상적인 게시판 1페이지 글 수 (10~40개)
                if 10 <= item_count <= 40:
                    score += 60
                elif 5 <= item_count <= 50:
                    score += 30

                if "td.no" in sel:
                    score += 40
                if ":not(.notice)" in sel:
                    score += 30
                if ":not([href*='#'])" in sel:
                    score += 20
                if "> a:first-child" in sel:
                    score += 15

                if score > best_score:
                    best_score = score
                    best_selector = sel
                    best_items = valid_items
                    excluded_notices = notices_found
            except Exception:
                continue

        if not best_selector:
            best_selector = candidates[0] if candidates else "table tbody tr td.title a"

        return {
            "status": "success",
            "suggested_link_selector": best_selector,
            "target_anchor": target_text,
            "target_url": urljoin(base_url, target_href) if base_url else target_href,
            "matched_count": len(best_items),
            "matched_items": best_items,
            "sample_links": [it["url"] for it in best_items[:5]],
            "excluded_notices_count": len(excluded_notices),
            "excluded_sample_notices": excluded_notices[:3],
            "message": f"타겟 앵커 '{snippet}'와 동일 패턴의 본문 기사 {len(best_items)}건을 성공적으로 묶었습니다."
        }
