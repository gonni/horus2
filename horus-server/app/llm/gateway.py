import logging
from typing import Optional, Dict, Any
from app.llm.ollama_client import OllamaClient
from app.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class HybridLLMGateway:
    def __init__(self):
        self.ollama = OllamaClient()
        self.gemini = GeminiClient()

    async def generate(
        self,
        prompt: str,
        task_type: str = "general", # realtime_api, stock_analysis, site_discovery, batch_extraction, tagging, summary
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        force_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Hybrid Routing Policy:
        - force_provider 설정 시 해당 공급자 우선 시도
        - 실시간성/고난도 분석 (realtime_api, stock_analysis, site_discovery): Gemini -> Ollama Fallback
        - 대량 처리/비용절감 (batch_extraction, tagging, summary): Ollama -> Gemini Fallback
        """
        # 1. Force Provider
        if force_provider == "gemini":
            return await self._call_gemini_with_fallback(prompt, system_instruction, temperature, fallback_to_ollama=False)
        elif force_provider == "ollama":
            return await self._call_ollama_with_fallback(prompt, system_instruction, temperature, fallback_to_gemini=False)

        # 2. Dynamic Routing (Default: Ollama gemma4:e4b first)
        return await self._call_ollama_with_fallback(prompt, system_instruction, temperature, fallback_to_gemini=True)

    async def _call_gemini_with_fallback(
        self, prompt: str, system_instruction: Optional[str], temperature: float, fallback_to_ollama: bool
    ) -> Dict[str, Any]:
        if self.gemini.is_configured():
            try:
                logger.info("Routing request to Gemini...")
                return await self.gemini.generate(prompt, system_instruction=system_instruction, temperature=temperature)
            except Exception as e:
                logger.warning(f"Gemini call failed ({e}), checking fallback...")
                if not fallback_to_ollama:
                    raise

        if fallback_to_ollama:
            logger.info("Falling back to local Ollama...")
            return await self.ollama.generate(prompt, system_instruction=system_instruction, temperature=temperature)
        raise RuntimeError("No LLM provider available.")

    async def _call_ollama_with_fallback(
        self, prompt: str, system_instruction: Optional[str], temperature: float, fallback_to_gemini: bool
    ) -> Dict[str, Any]:
        ollama_available = await self.ollama.is_available()
        if ollama_available:
            try:
                logger.info("Routing request to Local Ollama...")
                return await self.ollama.generate(prompt, system_instruction=system_instruction, temperature=temperature)
            except Exception as e:
                logger.warning(f"Ollama call failed ({e}), checking fallback...")
                if not fallback_to_gemini:
                    raise

        if fallback_to_gemini and self.gemini.is_configured():
            logger.info("Falling back to Gemini...")
            return await self.gemini.generate(prompt, system_instruction=system_instruction, temperature=temperature)
        
        # 마지막 시도
        return await self.ollama.generate(prompt, system_instruction=system_instruction, temperature=temperature)

llm_gateway = HybridLLMGateway()
