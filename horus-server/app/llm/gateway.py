import logging
import asyncio
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.llm.gpu2_client import GPU2Client
from app.llm.ollama_client import OllamaClient
from app.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class HybridLLMGateway:
    def __init__(self):
        self.gpu2 = GPU2Client()
        self.ollama = OllamaClient()
        self.gemini = GeminiClient()

    async def get_available_models(self) -> Dict[str, Any]:
        """
        GPU2 vLLM 및 Local Ollama의 가용 모델 및 상태를 집계하여 반환합니다.
        """
        gpu2_task = asyncio.create_task(self.gpu2.is_available())
        ollama_task = asyncio.create_task(self.ollama.is_available())
        gpu2_avail, ollama_avail = await asyncio.gather(gpu2_task, ollama_task)

        gpu2_models = []
        if gpu2_avail:
            gpu2_models = await self.gpu2.get_installed_models()

        ollama_models = []
        if ollama_avail:
            ollama_models = await self.ollama.get_installed_models()

        default_provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "gpu2")
        is_gpu2_default = default_provider == "gpu2"

        options = [
            {
                "id": "auto",
                "name": f"Auto ({'GPU2 전용' if not getattr(settings, 'ENABLE_OLLAMA_FALLBACK', False) else 'GPU2 우선 → Ollama 자동 폴백'})",
                "provider": "auto",
                "model": "auto",
                "is_default": is_gpu2_default,
                "online": bool(gpu2_avail or (ollama_avail and getattr(settings, "ENABLE_OLLAMA_FALLBACK", False))),
                "description": "GPU2 전용 가속 및 안정적 재처리 보장" if not getattr(settings, "ENABLE_OLLAMA_FALLBACK", False) else "GPU2 활성 시 우선 처리, 미응답 시 Ollama 전환"
            }
        ]

        for m in gpu2_models:
            options.append({
                "id": f"gpu2:{m}",
                "name": f"{m} (GPU2 vLLM)",
                "provider": "gpu2",
                "model": m,
                "online": True,
                "description": "GPU2 Dual RTX 5070 Ti 전용 가속"
            })

        for m in ollama_models:
            options.append({
                "id": f"ollama:{m}",
                "name": f"{m} (Local Ollama)",
                "provider": "ollama",
                "model": m,
                "online": True,
                "description": "Local Ollama 머신 가속"
            })

        return {
            "default_model": "auto" if is_gpu2_default else f"ollama:{settings.OLLAMA_MODEL}",
            "gpu2_available": gpu2_avail,
            "ollama_available": ollama_avail,
            "gemini_available": self.gemini.is_configured(),
            "options": options
        }

    async def generate(
        self,
        prompt: str,
        task_type: str = "general",
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        model: Optional[str] = None,
        force_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Configurable Routing Policy:
        - force_provider == 'gemini' or req_model starts with 'gemini': Gemini 호출
        - force_provider == 'ollama' or req_model starts with 'ollama': Ollama 호출
        - force_provider == 'gpu2' or req_model starts with 'gpu2': GPU2 호출 (재시도 및 실패 처리)
        - model이 'auto' 또는 None인 경우: DEFAULT_LLM_PROVIDER(기본 gpu2)에 따른 라우팅
        """
        req_model = (model or "").strip()
        default_provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "gpu2")

        # 1. Force Gemini
        if force_provider == "gemini" or req_model.startswith("gemini"):
            return await self._call_gemini_with_fallback(prompt, system_instruction, temperature, fallback_to_ollama=False)

        # 2. Explicit Ollama
        if force_provider == "ollama" or req_model.startswith("ollama:"):
            target_m = req_model.replace("ollama:", "") if req_model.startswith("ollama:") else req_model
            return await self._call_ollama_direct(prompt, system_instruction, target_m, temperature)

        # 3. Explicit GPU2
        if force_provider == "gpu2" or req_model.startswith("gpu2:"):
            target_m = req_model.replace("gpu2:", "") if req_model.startswith("gpu2:") else req_model
            return await self._call_gpu2_direct(prompt, system_instruction, target_m, temperature, max_tokens)

        # 4. Default Provider Routing (Default: GPU2)
        if default_provider == "ollama":
            target_m = req_model if req_model and req_model != "auto" else getattr(settings, "OLLAMA_MODEL", "qwen3.5:35b-mlx")
            return await self._call_ollama_direct(prompt, system_instruction, target_m, temperature)

        return await self._call_auto_routing(prompt, system_instruction, temperature, max_tokens)

    async def _call_auto_routing(
        self, prompt: str, system_instruction: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        enable_fallback = getattr(settings, "ENABLE_OLLAMA_FALLBACK", False)

        # 1차: GPU2 확인 및 시도 (내부적으로 최대 3회 지수 백오프 재시도 포함)
        try:
            gpu2_available = await self.gpu2.is_available()
            if gpu2_available:
                logger.info("Routing: GPU2 is online. Calling GPU2 vLLM...")
                res = await self.gpu2.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                res["fallback_used"] = False
                return res
            else:
                logger.warning("Routing: GPU2 health check failed or timeout.")
        except Exception as e:
            logger.error(f"Routing: GPU2 call failed after retries: {e}")
            if not enable_fallback:
                raise RuntimeError(f"GPU2 LLM 생성 실패 (재시도 초과): {e}")

        # 2차: Local Ollama Fallback (ENABLE_OLLAMA_FALLBACK == True 일 때만 활성화)
        if enable_fallback:
            try:
                ollama_available = await self.ollama.is_available()
                if ollama_available:
                    logger.info("Fallback Enabled: Falling back to Local Ollama...")
                    res = await self.ollama.generate(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        temperature=temperature
                    )
                    res["fallback_used"] = True
                    return res
            except Exception as e:
                logger.warning(f"Fallback: Local Ollama call failed ({e}). Checking Gemini fallback...")

            # 3차: Gemini Fallback
            if self.gemini.is_configured():
                try:
                    logger.info("Fallback Enabled: Falling back to Gemini...")
                    res = await self.gemini.generate(prompt, system_instruction=system_instruction, temperature=temperature)
                    res["fallback_used"] = True
                    return res
                except Exception as e:
                    logger.error(f"Fallback: Gemini fallback failed ({e})")

        raise RuntimeError("GPU2 LLM 서비스에 연결할 수 없습니다. (Ollama 자동 폴백 비활성화됨)")

    async def _call_gpu2_direct(
        self, prompt: str, system_instruction: Optional[str], model: str, temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        enable_fallback = getattr(settings, "ENABLE_OLLAMA_FALLBACK", False)
        try:
            return await self.gpu2.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            logger.error(f"GPU2 direct call failed after retries: {e}")
            if enable_fallback and await self.ollama.is_available():
                logger.info("Fallback Enabled: Attempting Ollama fallback for GPU2 direct call...")
                res = await self.ollama.generate(prompt, system_instruction=system_instruction, temperature=temperature)
                res["fallback_used"] = True
                return res
            raise

    async def _call_ollama_direct(
        self, prompt: str, system_instruction: Optional[str], model: str, temperature: float
    ) -> Dict[str, Any]:
        return await self.ollama.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            model=model,
            temperature=temperature
        )

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

        if fallback_to_ollama and getattr(settings, "ENABLE_OLLAMA_FALLBACK", False):
            logger.info("Falling back to local Ollama...")
            return await self.ollama.generate(prompt, system_instruction=system_instruction, temperature=temperature)
        raise RuntimeError("No LLM provider available.")

llm_gateway = HybridLLMGateway()
