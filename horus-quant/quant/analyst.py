import httpx
import logging

logger = logging.getLogger(__name__)

class LLMStockAnalyst:
    def __init__(self, api_base_url: str = "http://localhost:8000/api/v1"):
        self.api_base_url = api_base_url

    async def generate_stock_report(self, code: str, name: str, closing_price: int, change_rate: float) -> str:
        prompt = f"""
종가매매 추천 종목 분석 리포트를 작성해주세요.

- 종목명: {name} ({code})
- 종가: {closing_price:,}원
- 당일 등락률: {change_rate:+.2f}%

[작성 가이드]:
1. 최근 테마/모멘텀 요약 (1~2줄)
2. 기술적 수급 포인트 (1~2줄)
3. 익일 시초가 대응 전략 및 목표 수익률 (1줄)
"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.api_base_url}/llm/generate",
                    json={"prompt": prompt, "task_type": "stock_analysis"}
                )
                if res.status_code == 200:
                    return res.json().get("response_text", "")
        except Exception as e:
            logger.error(f"LLM Stock Analyst call failed: {e}")
        return "자동 분석 리포트 생성 대기 중입니다."
