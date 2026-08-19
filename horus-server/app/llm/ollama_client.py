import httpx
import json
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.default_model = default_model or settings.OLLAMA_MODEL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def is_available(self) -> bool:
        try:
            res = await self.client.get("/api/tags")
            return res.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        format_json: bool = False
    ) -> Dict[str, Any]:
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system_instruction:
            payload["system"] = system_instruction
        if format_json:
            payload["format"] = "json"

        try:
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "provider": "ollama",
                "model": target_model,
                "response_text": data.get("response", ""),
                "usage_metadata": {
                    "total_duration": data.get("total_duration"),
                    "eval_count": data.get("eval_count")
                }
            }
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def close(self):
        await self.client.aclose()
