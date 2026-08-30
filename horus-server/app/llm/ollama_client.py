import httpx
import json
import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.default_model = default_model or settings.OLLAMA_MODEL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def is_available(self) -> bool:
        try:
            res = await self.client.get("/api/tags", timeout=2.0)
            return res.status_code == 200
        except Exception:
            return False

    async def get_installed_models(self) -> List[str]:
        try:
            res = await self.client.get("/api/tags", timeout=2.5)
            if res.status_code == 200:
                data = res.json()
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.debug(f"Failed to fetch Ollama tags: {e}")
        return []

    async def resolve_model(self, requested_model: Optional[str] = None) -> str:
        target = requested_model or self.default_model
        if target.startswith("ollama:"):
            target = target[7:]

        installed = await self.get_installed_models()
        if not installed:
            return target

        # 1. Exact match
        if target in installed:
            return target

        # 2. Match base name (e.g. gemma4:e4b vs gemma4:e4b-mlx or gemma4)
        base_name = target.split(":")[0]
        for m in installed:
            if m.startswith(target) or m.startswith(base_name):
                logger.info(f"Resolved Ollama model '{target}' -> '{m}'")
                return m

        # 3. Match any partial
        for m in installed:
            if "gemma" in m or "qwen" in m:
                logger.info(f"Fell back to installed Ollama model '{m}' for requested '{target}'")
                return m

        # 4. First available
        logger.info(f"Using first installed model '{installed[0]}' for requested '{target}'")
        return installed[0]

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        format_json: bool = False
    ) -> Dict[str, Any]:
        target_model = await self.resolve_model(model)
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
            logger.error(f"Ollama generation failed with model '{target_model}': {e}")
            raise

    async def close(self):
        await self.client.aclose()
