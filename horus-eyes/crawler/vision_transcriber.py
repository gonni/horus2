import asyncio
import base64
import hashlib
import logging
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse, urljoin
import httpx
from crawler.config import config

logger = logging.getLogger(__name__)

# 전역 이미지 Vision 분석 결과 캐시 (동일 이미지 재호출 시 초고속 반환)
VISION_CACHE: Dict[str, str] = {}

class VisionTranscriber:
    """
    본문에 포함된 이미지를 Vision LLM(Local Ollama 멀티모달 모델 또는 Gemini Vision)을 통해
    한국어 텍스트 설명 및 OCR로 변환하고 본문 텍스트 내에 주입합니다.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.ollama_url = config.OLLAMA_BASE_URL
        self.model_name = model_name or "llama3.2-vision"
        self.gemini_key = config.GEMINI_API_KEY

    def _get_image_headers(self, image_url: str, referer: Optional[str] = None) -> Dict[str, str]:
        parsed = urlparse(image_url)
        domain = parsed.netloc or "m.clien.net"
        ref = referer or f"https://{domain}/"
        if "clien.net" in domain:
            ref = "https://m.clien.net/"

        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": ref,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
        }

    async def fetch_image_base64(self, image_url: str, referer: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        이미지 URL에서 바이너리를 가져와 Base64 문자열로 인코딩합니다.
        핫링크 방지(Hotlink 403)를 우회하기 위해 다중 Referer 시도를 수행합니다.
        반환: (base64_str, error_message)
        """
        parsed = urlparse(image_url)
        domain = parsed.netloc

        candidate_referers = [
            referer or f"https://{domain}/",
            "https://m.clien.net/",
            "https://www.clien.net/",
            "https://www.google.com/",
            None
        ]

        last_error = None
        for ref in candidate_referers:
            headers = self._get_image_headers(image_url, referer=ref)
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True, verify=False) as client:
                    res = await client.get(image_url)
                    if res.status_code == 200 and len(res.content) > 100:
                        return base64.b64encode(res.content).decode("utf-8"), None
                    last_error = f"HTTP {res.status_code}"
            except Exception as e:
                last_error = str(e)

        logger.warning(f"Failed to fetch image binary for {image_url}: {last_error}")
        return None, last_error

    async def get_installed_ollama_models(self) -> List[str]:
        """로컬 Ollama에 설치된 전체 모델 목록 조회"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.ollama_url}/api/tags")
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    return [m.get("name") for m in models if m.get("name")]
        except Exception:
            pass
        return []

    async def describe_image(
        self,
        image_url: str,
        custom_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        referer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        단일 이미지에 대해 Vision LLM을 실행하여 한글 텍스트 설명(캡션/OCR/도표 해석)을 반환합니다.
        """
        if not image_url:
            return {"description": "", "status": "error", "error": "이미지 URL이 없습니다."}

        # 1. 캐시 확인
        cache_key = hashlib.md5(image_url.encode("utf-8")).hexdigest()
        if cache_key in VISION_CACHE:
            return {"description": VISION_CACHE[cache_key], "status": "success", "cached": True}

        # 2. 이미지 바이너리 다운로드
        b64_image, fetch_err = await self.fetch_image_base64(image_url, referer=referer)
        if not b64_image:
            return {
                "description": "이미지 다운로드 실패 (외부 링크 접근 차단 또는 이미지 경로 오류)",
                "status": "error",
                "error": f"Image fetch failed: {fetch_err}"
            }

        prompt = custom_prompt or (
            "당신은 이미지 분석 및 OCR 전문 AI입니다. "
            "제공된 이미지에 포함된 모든 글자(텍스트/OCR), 그래프/도표의 수치, 주요 인물이나 사물의 시각적 핵심 내용을 "
            "한국어로 정확하고 읽기 쉽게 1~3문장 내외로 요약 설명해주세요. 불필요한 서론은 생략하고 내용만 답변하세요."
        )

        # 3. 모델 후보군 선정 (지정 모델 -> 설치된 비전 모델 -> Gemini Fallback)
        installed = await self.get_installed_ollama_models()
        candidate_models = []
        if model_name: candidate_models.append(model_name)
        if self.model_name and self.model_name not in candidate_models: candidate_models.append(self.model_name)
        
        # 설치된 모델 중 vision 키워드가 있는 모델 자동 탐색
        for m in installed:
            if any(k in m.lower() for k in ["vision", "llava", "minicpm", "vl", "bakllava"]) and m not in candidate_models:
                candidate_models.append(m)
        
        # 설치된 모델의 첫 번째 모델
        for m in installed:
            if m not in candidate_models:
                candidate_models.append(m)

        description = ""
        used_model = ""
        last_ollama_err = None

        # 4. Local Ollama 호출
        for target_m in candidate_models:
            try:
                payload = {
                    "model": target_m,
                    "prompt": prompt,
                    "images": [b64_image],
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                    }
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(f"{self.ollama_url}/api/generate", json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        resp_text = data.get("response", "").strip()
                        if resp_text and len(resp_text) > 3:
                            description = resp_text
                            used_model = target_m
                            break
                    elif res.status_code == 404:
                        last_ollama_err = f"모델 '{target_m}' 미설치"
                    else:
                        last_ollama_err = f"HTTP {res.status_code}: {res.text[:100]}"
            except Exception as e:
                last_ollama_err = str(e)

        # 5. Gemini Vision Fallback
        if not description and self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                g_model = genai.GenerativeModel("gemini-2.0-flash")
                image_parts = [{"mime_type": "image/jpeg", "data": base64.b64decode(b64_image)}]
                res = await g_model.generate_content_async([prompt, image_parts[0]])
                if res.text:
                    description = res.text.strip()
                    used_model = "gemini-2.0-flash (Cloud)"
            except Exception as e:
                logger.error(f"Gemini vision fallback failed: {e}")

        # 6. 결과 반환 및 캐싱
        if description:
            cleaned_desc = " ".join(description.split())
            VISION_CACHE[cache_key] = cleaned_desc
            return {
                "description": cleaned_desc,
                "status": "success",
                "model_used": used_model
            }

        # 실패 시 명확한 가이드 제공
        guide_msg = "로컬 Ollama에 Vision 지원 모델(예: ollama pull llama3.2-vision 또는 ollama pull llava)을 설치하거나 상단에서 설치된 모델을 선택해주세요."
        if last_ollama_err:
            guide_msg = f"{guide_msg} (오류 상세: {last_ollama_err})"

        return {
            "description": guide_msg,
            "status": "warning",
            "error": last_ollama_err
        }

    async def describe_images_batch(
        self,
        image_urls: List[str],
        model_name: Optional[str] = None,
        referer: Optional[str] = None
    ) -> Dict[str, str]:
        """
        복수 이미지 목록을 비동기 병렬로 처리하여 URL -> 설명 맵을 생성합니다. (최대 5개 동시)
        """
        if not image_urls:
            return {}

        results: Dict[str, str] = {}
        targets = image_urls[:5]

        tasks = [self.describe_image(url, model_name=model_name, referer=referer) for url in targets]
        res_list = await asyncio.gather(*tasks, return_exceptions=True)

        for url, res_obj in zip(targets, res_list):
            if isinstance(res_obj, dict) and res_obj.get("description"):
                results[url] = res_obj["description"]

        return results

    def inject_descriptions_into_content(
        self,
        content_text: str,
        image_descriptions: Dict[str, str]
    ) -> str:
        """
        본문 텍스트 내에 Vision으로 추출된 이미지 설명을 자연스럽게 주입합니다.
        """
        if not content_text or not image_descriptions:
            return content_text

        injected_blocks = []
        for idx, (img_url, desc) in enumerate(image_descriptions.items()):
            # 경고/오류 메시지가 아닌 실제 설명인 경우에만 주입
            if desc and not desc.startswith("이미지 다운로드 실패") and not desc.startswith("로컬 Ollama에 Vision"):
                injected_blocks.append(f"[🖼️ 첨부 이미지 #{idx + 1} 내용: {desc}]")

        if injected_blocks:
            separator = "\n\n" + "\n\n".join(injected_blocks) + "\n\n"
            return content_text + separator

        return content_text
