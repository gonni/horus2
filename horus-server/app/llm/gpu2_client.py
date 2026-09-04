import asyncio
import httpx
import json
import re
import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings

logger = logging.getLogger(__name__)

class GPU2Client:
    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = base_url or settings.GPU2_BASE_URL
        self.default_model = default_model or settings.GPU2_MODEL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=45.0)

    async def is_available(self) -> bool:
        try:
            timeout = getattr(settings, "GPU2_HEALTHCHECK_TIMEOUT", 5.0)
            res = await self.client.get("/models", timeout=timeout)
            return res.status_code == 200
        except Exception:
            return False

    async def get_installed_models(self) -> List[str]:
        try:
            timeout = getattr(settings, "GPU2_HEALTHCHECK_TIMEOUT", 5.0)
            res = await self.client.get("/models", timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                return models
        except Exception as e:
            logger.debug(f"Failed to fetch GPU2 models: {e}")
        return []

    async def resolve_model(self, requested_model: Optional[str] = None) -> str:
        target = requested_model or self.default_model
        # Strip provider prefix if present (e.g. "gpu2:qwen3.8:27b")
        if target.startswith("gpu2:"):
            target = target[5:]

        installed = await self.get_installed_models()
        if not installed:
            return target

        if target in installed:
            return target

        for m in installed:
            if target.lower() in m.lower():
                return m

        return installed[0]

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        target_model = await self.resolve_model(model)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        max_retries = getattr(settings, "GPU2_MAX_RETRIES", 3)
        backoff = getattr(settings, "GPU2_RETRY_BACKOFF", 1.5)
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.post("/chat/completions", json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                
                # If thinking model puts content in reasoning or if content has <think>
                if not content and message.get("reasoning"):
                    content = message.get("reasoning", "")

                # Strip <think>...</think> if present
                cleaned_content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                if not cleaned_content and content:
                    cleaned_content = content.strip()

                return {
                    "provider": "gpu2",
                    "model": target_model,
                    "response_text": cleaned_content,
                    "usage_metadata": data.get("usage")
                }
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"GPU2 generation attempt {attempt}/{max_retries} failed for model '{target_model}': {e}"
                )
                if attempt < max_retries:
                    wait_time = backoff * (2 ** (attempt - 1))
                    logger.info(f"Retrying GPU2 call in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)

        logger.error(f"GPU2 generation completely failed after {max_retries} attempts: {last_exception}")
        raise last_exception

    async def close(self):
        await self.client.aclose()
