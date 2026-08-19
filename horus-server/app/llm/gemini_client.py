import logging
from typing import Optional, Dict, Any
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.default_model = default_model or settings.GEMINI_MODEL
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("GEMINI_API_KEY is not configured.")

        target_model_name = model or self.default_model
        try:
            model_instance = genai.GenerativeModel(
                model_name=target_model_name,
                system_instruction=system_instruction,
                generation_config={"temperature": temperature}
            )
            
            # 비동기 호출 지원
            response = await model_instance.generate_content_async(prompt)
            return {
                "provider": "gemini",
                "model": target_model_name,
                "response_text": response.text,
                "usage_metadata": {
                    "prompt_token_count": getattr(response.usage_metadata, "prompt_token_count", None),
                    "candidates_token_count": getattr(response.usage_metadata, "candidates_token_count", None)
                } if hasattr(response, "usage_metadata") else None
            }
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise

gemini_client = GeminiClient()

