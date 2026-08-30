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
    본문에 포함된 이미지를 Vision LLM(GPU2 Dual RTX 5070 Ti vLLM 멀티모달 모델 또는 Local Ollama 또는 Gemini Vision)을 통해
    한국어 텍스트 설명 및 OCR로 변환하고 본문 텍스트 내에 주입합니다.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.gpu2_base_url = getattr(config, "GPU2_BASE_URL", "http://gpu2:8000/v1")
        self.gpu2_default_model = getattr(config, "GPU2_MODEL", "cyankiwi/Qwen3.8-27B-AWQ-INT4")
        self.ollama_url = getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = model_name or f"gpu2:{self.gpu2_default_model}"
        self.gemini_key = getattr(config, "GEMINI_API_KEY", None)

    def _get_image_headers(self, image_url: str, referer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    async def fetch_image_base64(self, image_url: str, referer: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        이미지 URL에서 바이너리를 가져와 Base64 문자열로 인코딩합니다.
        핫링크 방지(Hotlink 403)를 우회하기 위해 다중 Referer 시도를 수행합니다.
        반환: (base64_str, error_message)
        """
        if not image_url:
            return None, "Empty image URL"

        if image_url.startswith("data:image/") and ";base64," in image_url:
            return image_url.split(";base64,")[1], None

        parsed = urlparse(image_url)
        domain = parsed.netloc

        candidate_referers = [
            referer,
            f"https://{domain}/" if domain else None,
            "https://m.clien.net/",
            None
        ]

        last_error = None
        for ref in candidate_referers:
            headers = self._get_image_headers(image_url, referer=ref)
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True, verify=False) as client:
                    res = await client.get(image_url)
                    if res.status_code == 200 and len(res.content) > 50:
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

    async def _call_gpu2_vision(
        self,
        b64_image: str,
        prompt: str,
        model_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        GPU2 (vLLM / OpenAI 호환 멀티모달 엔드포인트) 호출
        Qwen3.8-27B-AWQ-INT4 등 Vision 지원 모델에 Base64 이미지를 전달하여 고속 OCR/캡셔닝을 수행합니다.
        (최대 3회 지수 백오프 재시도 포함)
        """
        clean_model = model_name.replace("gpu2:", "").strip() if model_name.startswith("gpu2:") else model_name
        if not clean_model or clean_model == "default":
            clean_model = self.gpu2_default_model

        payload = {
            "model": clean_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.2
        }

        max_retries = getattr(config, "GPU2_MAX_RETRIES", 3)
        backoff = getattr(config, "GPU2_RETRY_BACKOFF", 1.5)
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                url = f"{self.gpu2_base_url.rstrip('/')}/chat/completions"
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            content = msg.get("content") or ""
                            reasoning = msg.get("reasoning") or ""

                            import re
                            cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                            final_text = cleaned or content.strip()
                            if not final_text and reasoning:
                                final_text = reasoning.strip()
                            if final_text:
                                return final_text, None
                        last_error = "GPU2 응답 choices 비어있음"
                    else:
                        last_error = f"GPU2 HTTP {res.status_code}: {res.text[:120]}"
            except Exception as e:
                last_error = f"GPU2 연결 실패: {str(e)}"

            if attempt < max_retries:
                wait_time = backoff * (2 ** (attempt - 1))
                logger.info(f"GPU2 Vision attempt {attempt}/{max_retries} failed ({last_error}). Retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

        return None, last_error

    async def _call_ollama_vision(
        self,
        b64_image: str,
        prompt: str,
        model_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        로컬 Ollama Vision API (/api/generate) 호출
        """
        clean_model = model_name.replace("ollama:", "").strip() if model_name.startswith("ollama:") else model_name
        payload = {
            "model": clean_model,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{self.ollama_url}/api/generate", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    resp_text = data.get("response", "").strip()
                    if resp_text and len(resp_text) > 3:
                        return resp_text, None
                    return None, "Ollama 응답이 비어있습니다."
                elif res.status_code == 404:
                    return None, f"Ollama 모델 '{clean_model}' 미설치"
                else:
                    return None, f"Ollama HTTP {res.status_code}: {res.text[:100]}"
        except Exception as e:
            return None, f"Ollama 호출 실패: {str(e)}"

    async def describe_image(
        self,
        image_url: str,
        custom_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        referer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        단일 이미지에 대해 Vision LLM을 실행하여 한글 텍스트 설명(캡션/OCR/도표 해석)을 반환합니다.
        GPU2 vLLM(Qwen3.8-27B-AWQ-INT4)을 기본으로 사용하며, Ollama 폴백은 설정에 의해 제어됩니다.
        """
        if not image_url:
            return {"description": "", "status": "error", "error": "이미지 URL이 없습니다."}

        # 1. 캐시 확인
        cache_key = hashlib.md5(image_url.encode("utf-8")).hexdigest()
        if cache_key in VISION_CACHE:
            return {
                "description": VISION_CACHE[cache_key],
                "status": "success",
                "cached": True,
                "provider": "cache"
            }

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

        target_model = model_name or self.model_name
        description = ""
        used_model = ""
        used_provider = ""
        last_error = None

        # 3. 모델 라우팅 (GPU2 vs Local Ollama)
        is_explicit_ollama = target_model.startswith("ollama:") or getattr(config, "DEFAULT_LLM_PROVIDER", "gpu2") == "ollama"
        enable_fallback = getattr(config, "ENABLE_OLLAMA_FALLBACK", False)

        if not is_explicit_ollama:
            # 🚀 [1순위] GPU2 Dual RTX 5070 Ti vLLM (Qwen3.8-27B-AWQ-INT4 Vision) 호출
            gpu2_model = target_model if target_model.startswith("gpu2:") else f"gpu2:{self.gpu2_default_model}"
            logger.info(f"Invoking GPU2 Vision for image ({image_url[:50]}...) using model {gpu2_model}")
            res_text, gpu2_err = await self._call_gpu2_vision(b64_image, prompt, gpu2_model)
            if res_text:
                description = res_text
                used_model = gpu2_model
                used_provider = "gpu2"
            else:
                last_error = gpu2_err
                logger.warning(f"GPU2 Vision failed after retries: {gpu2_err}")

        # 4. Local Ollama Vision 시도 (명시적 요청이거나 ENABLE_OLLAMA_FALLBACK=True 일 때만)
        if not description and (is_explicit_ollama or enable_fallback):
            logger.info("Calling Local Ollama Vision...")
            installed = await self.get_installed_ollama_models()
            candidate_models = []
            if is_explicit_ollama:
                candidate_models.append(target_model.replace("ollama:", ""))
            for m in installed:
                if any(k in m.lower() for k in ["vision", "llava", "minicpm", "vl", "bakllava", "qwen"]) and m not in candidate_models:
                    candidate_models.append(m)
            for m in installed:
                if m not in candidate_models:
                    candidate_models.append(m)

            for target_m in candidate_models:
                res_text, o_err = await self._call_ollama_vision(b64_image, prompt, target_m)
                if res_text:
                    description = res_text
                    used_model = f"ollama:{target_m}"
                    used_provider = "ollama"
                    break
                else:
                    last_error = o_err

        # 5. [선택적 폴백] Gemini Vision (ENABLE_OLLAMA_FALLBACK=True 및 Gemini 키 존재 시)
        if not description and enable_fallback and self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                g_model = genai.GenerativeModel("gemini-2.0-flash")
                image_parts = [{"mime_type": "image/jpeg", "data": base64.b64decode(b64_image)}]
                res = await g_model.generate_content_async([prompt, image_parts[0]])
                if res.text:
                    description = res.text.strip()
                    used_model = "gemini-2.0-flash (Cloud)"
                    used_provider = "gemini"
            except Exception as e:
                logger.error(f"Gemini vision fallback failed: {e}")

        # 6. 결과 반환 및 캐싱
        if description:
            cleaned_desc = " ".join(description.split())
            VISION_CACHE[cache_key] = cleaned_desc
            return {
                "description": cleaned_desc,
                "status": "success",
                "model_used": used_model,
                "provider": used_provider
            }

        # 실패 시 안내
        guide_msg = "GPU2 Vision(Qwen3.8-27B-AWQ-INT4) 호출 실패."
        if last_error:
            guide_msg = f"{guide_msg} (오류 상세: {last_error})"

        return {
            "description": guide_msg,
            "status": "error",
            "error": last_error,
            "provider": "failed"
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
