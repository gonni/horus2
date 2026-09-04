import asyncio
import logging
import json
import re
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from crawler.config import config
from crawler.vision_transcriber import VisionTranscriber

logger = logging.getLogger(__name__)

class ConcurrentGPUWorker:
    """
    🚀 GPU2 Dual RTX 5070 Ti 기반 고성능 8-Way 병렬 작업 큐 워커
    - GPU2 (vLLM OpenAI 호환 엔드포인트)를 기본 AI 공급자로 사용 (실패 시 로컬 Ollama 폴백)
    - 5070 Ti Dual GPU 사양에 최적화된 동시 처리 슬롯(기본 concurrency=8) 지원
    - 실시간 동시성 조절(set_concurrency) 및 슬롯별 상태 추적(active_slots) 제공
    - 2개의 독립 서브시스템 지원:
        1) 📝 텍스트 NLP 정제 (요약, 감성 분석, 엔티티 추출, 종목 매핑)
        2) 🖼️ 비전 Image-to-Text (이미지 텍스트 변환, 본문 주입, 원본 URL 보존)
    """
    def __init__(self):
        self.engine = create_async_engine(config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True, pool_size=20, max_overflow=20)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        
        # LLM 공급자 엔드포인트 설정
        self.default_provider: str = getattr(config, "DEFAULT_LLM_PROVIDER", "gpu2")
        self.enable_ollama_fallback: bool = getattr(config, "ENABLE_OLLAMA_FALLBACK", False)
        self.gpu2_base_url: str = getattr(config, "GPU2_BASE_URL", "http://gpu2:8000/v1")
        self.gpu2_default_model: str = getattr(config, "GPU2_MODEL", "qwen3.8:27b")
        self.ollama_url: str = config.OLLAMA_BASE_URL or "http://localhost:11434"
        self.transcriber = VisionTranscriber()

        # 병렬 동시 처리 파라미터 (안전 상한 적용: 텍스트 기본 8, 비전 기본 4)
        self.max_vision_concurrency: int = getattr(config, "MAX_VISION_CONCURRENCY", 4)
        self.max_text_concurrency: int = getattr(config, "MAX_TEXT_CONCURRENCY", 8)
        self.concurrency: int = getattr(config, "DEFAULT_CONCURRENCY", 8)
        self.text_concurrency: int = min(self.concurrency, self.max_text_concurrency)
        self.vision_concurrency: int = min(max(2, self.concurrency // 2), self.max_vision_concurrency)
        self.consecutive_gpu2_errors: int = 0

        # 서브시스템 1: 텍스트 NLP 상태
        self.text_state: str = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.text_model_name: str = f"gpu2:{self.gpu2_default_model}"
        self.text_processed_count: int = 0
        self.text_failed_count: int = 0

        # 서브시스템 2: 비전 Image-to-Text 상태
        self.vision_state: str = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.vision_model_name: str = f"gpu2:{self.gpu2_default_model}"
        self.vision_processed_count: int = 0
        self.vision_failed_count: int = 0

        # 공통 워커 파라미터
        self.interval_seconds: float = 0.5
        self._worker_task: Optional[asyncio.Task] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        # 실시간 슬롯 및 작업 모니터링 (1..N 슬롯)
        self.active_slots: Dict[int, Dict[str, Any]] = {}
        self._in_flight_urls: set = set()
        self._in_flight_titles: set = set()
        self.last_processed_at: Optional[datetime] = None
        self.last_error_message: Optional[str] = None
        self.provider_used: str = "gpu2"

    # =========================================================================
    # ⚙️ 0. 동시 처리수(Concurrency) 실시간 동적 조절 (안전 가드레일 적용)
    # =========================================================================
    def set_concurrency(self, new_concurrency: int, subsystem: str = "all") -> int:
        clamped = max(1, min(32, int(new_concurrency)))
        if subsystem in ["all", "text"]:
            self.text_concurrency = min(clamped, self.max_text_concurrency * 2)
            self.concurrency = self.text_concurrency
        if subsystem in ["all", "vision"]:
            self.vision_concurrency = min(clamped, self.max_vision_concurrency * 2)
            if subsystem == "vision":
                self.concurrency = max(self.text_concurrency, self.vision_concurrency)

        logger.info(f"GPU Worker Concurrency dynamically updated: text={self.text_concurrency}, vision={self.vision_concurrency}, total={self.concurrency}")
        return self.concurrency

    # =========================================================================
    # 📝 1. 텍스트 NLP 서브시스템 제어
    # =========================================================================
    async def start_text(self, model_name: Optional[str] = None, concurrency: Optional[int] = None):
        if model_name:
            self.text_model_name = model_name
        if concurrency:
            self.set_concurrency(concurrency, subsystem="text")
        self.text_state = "RUNNING"
        self._pause_event.set()
        self._ensure_worker_running()
        logger.info(f"Text NLP Subsystem STARTED with model '{self.text_model_name}' (Concurrency={self.text_concurrency})")

    def pause_text(self):
        if self.text_state == "RUNNING":
            self.text_state = "PAUSED"
            logger.info("Text NLP Subsystem PAUSED.")

    def resume_text(self):
        if self.text_state == "PAUSED":
            self.text_state = "RUNNING"
            self._pause_event.set()
            self._ensure_worker_running()
            logger.info("Text NLP Subsystem RESUMED.")

    def stop_text(self):
        self.text_state = "STOPPED"
        logger.info("Text NLP Subsystem STOPPED.")

    # =========================================================================
    # 🖼️ 2. 비전 Image-to-Text 서브시스템 제어
    # =========================================================================
    async def start_vision(self, model_name: Optional[str] = None, concurrency: Optional[int] = None):
        if model_name:
            self.vision_model_name = model_name
        if concurrency:
            self.set_concurrency(concurrency, subsystem="vision")
        self.vision_state = "RUNNING"
        self._pause_event.set()
        self._ensure_worker_running()
        logger.info(f"Vision Image-to-Text Subsystem STARTED with model '{self.vision_model_name}' (Concurrency={self.vision_concurrency})")

    def pause_vision(self):
        if self.vision_state == "RUNNING":
            self.vision_state = "PAUSED"
            logger.info("Vision Image-to-Text Subsystem PAUSED.")

    def resume_vision(self):
        if self.vision_state == "PAUSED":
            self.vision_state = "RUNNING"
            self._pause_event.set()
            self._ensure_worker_running()
            logger.info("Vision Image-to-Text Subsystem RESUMED.")

    def stop_vision(self):
        self.vision_state = "STOPPED"
        logger.info("Vision Image-to-Text Subsystem STOPPED.")

    # 하위 호환성 별칭 메서드
    async def start(self, model_name: Optional[str] = None, batch_size: int = 8, interval_seconds: float = 0.5):
        await self.start_text(model_name=model_name, concurrency=batch_size)

    def pause(self):
        self.pause_text()

    def resume(self):
        self.resume_text()

    async def stop(self):
        self.stop_text()
        self.stop_vision()

    def _ensure_worker_running(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._concurrent_processing_loop())

    # =========================================================================
    # ⚡ 3. 5070 Ti Dual 8-Way 병렬 큐 실행 루프
    # =========================================================================
    async def _concurrent_processing_loop(self):
        logger.info(f"Concurrent GPU Worker loop started. (Text Concurrency: {self.text_concurrency}, Vision Concurrency: {self.vision_concurrency})")
        
        while self.text_state in ["RUNNING", "PAUSED"] or self.vision_state in ["RUNNING", "PAUSED"]:
            if self.text_state != "RUNNING" and self.vision_state != "RUNNING":
                await asyncio.sleep(1.0)
                continue

            # 선제적 유량 제어 (Adaptive Backpressure): GPU2 연속 에러 또는 과부하 감지 시 쿨다운
            if self.consecutive_gpu2_errors > 0:
                cooldown = min(10.0, 1.5 * self.consecutive_gpu2_errors)
                logger.info(f"[FlowControl] GPU2 backpressure active (errors={self.consecutive_gpu2_errors}). Cooldown for {cooldown:.1f}s...")
                await asyncio.sleep(cooldown)

            did_work = False

            # --- 작업 A: 비전 Image-to-Text 병렬 처리 (안전 상한 슬롯 제어) ---
            if self.vision_state == "RUNNING":
                try:
                    active_vision_slots = sum(1 for s in self.active_slots.values() if s.get("type") == "vision")
                    available_slots = max(0, self.vision_concurrency - active_vision_slots)
                    
                    if available_slots > 0:
                        vision_arts = await self._fetch_unprocessed_vision_articles(available_slots)
                        if vision_arts:
                            did_work = True
                            for art in vision_arts:
                                slot_id = self._acquire_slot("vision")
                                asyncio.create_task(self._run_vision_task_with_slot(slot_id, art))
                except Exception as e:
                    logger.error(f"Error scheduling Vision tasks: {e}")
                    self.last_error_message = str(e)

            # --- 작업 B: 텍스트 NLP 병렬 처리 (안전 상한 슬롯 제어) ---
            if self.text_state == "RUNNING":
                try:
                    active_text_slots = sum(1 for s in self.active_slots.values() if s.get("type") == "text")
                    available_slots = max(0, self.text_concurrency - active_text_slots)
                    
                    if available_slots > 0:
                        text_arts = await self._fetch_unprocessed_text_articles(available_slots)
                        if text_arts:
                            did_work = True
                            for art in text_arts:
                                slot_id = self._acquire_slot("text")
                                asyncio.create_task(self._run_text_task_with_slot(slot_id, art))
                except Exception as e:
                    logger.error(f"Error scheduling Text NLP tasks: {e}")
                    self.last_error_message = str(e)

            if not did_work:
                await asyncio.sleep(1.5)
            else:
                await asyncio.sleep(self.interval_seconds)

        self.active_slots.clear()
        self._in_flight_urls.clear()
        logger.info("Concurrent GPU Worker loop finished.")

    def _acquire_slot(self, task_type: str) -> int:
        for slot_num in range(1, 33):
            if slot_num not in self.active_slots:
                self.active_slots[slot_num] = {
                    "slot_id": slot_num,
                    "type": task_type,
                    "title": "작업 할당 중...",
                    "url": "",
                    "started_at": datetime.now().isoformat(),
                    "status": "RUNNING"
                }
                return slot_num
        new_id = len(self.active_slots) + 1
        self.active_slots[new_id] = {
            "slot_id": new_id,
            "type": task_type,
            "title": "작업 할당 중...",
            "url": "",
            "started_at": datetime.now().isoformat(),
            "status": "RUNNING"
        }
        return new_id

    def _release_slot(self, slot_id: int):
        self.active_slots.pop(slot_id, None)

    async def _run_text_task_with_slot(self, slot_id: int, art: tuple):
        art_id, source_id, url, title, content, published_at = art
        if slot_id in self.active_slots:
            self.active_slots[slot_id].update({
                "title": title[:50],
                "url": url,
                "started_at": datetime.now().isoformat(),
                "status": "PROCESSING"
            })
        try:
            enriched = await self._enrich_article(title, content, url)
            if enriched:
                await self._save_enriched_data(art_id, source_id, published_at, url, title, enriched)
                self.text_processed_count += 1
                self.last_processed_at = datetime.now()
            else:
                self.text_failed_count += 1
                await self._mark_article_failed(url, published_at, "LLM enrichment returned None")
        except Exception as e:
            logger.error(f"Text NLP Slot #{slot_id} error for '{title[:30]}': {e}")
            self.text_failed_count += 1
            self.last_error_message = str(e)
            await self._mark_article_failed(url, published_at, str(e))
        finally:
            self._in_flight_urls.discard(url)
            self._in_flight_titles.discard(title)
            self._release_slot(slot_id)

    async def _run_vision_task_with_slot(self, slot_id: int, art: tuple):
        art_id, source_id, url, title, content, published_at, raw_metadata = art
        if slot_id in self.active_slots:
            self.active_slots[slot_id].update({
                "title": title[:45],
                "url": url,
                "started_at": datetime.now().isoformat(),
                "status": "PROCESSING"
            })
        try:
            images_meta = (raw_metadata or {}).get("images", [])
            if images_meta:
                success = await self._process_vision_article(
                    art_id, source_id, url, title, content, published_at, raw_metadata, images_meta
                )
                if success:
                    self.vision_processed_count += 1
                    self.last_processed_at = datetime.now()
                else:
                    self.vision_failed_count += 1
            else:
                self.vision_processed_count += 1
        except Exception as e:
            logger.error(f"Vision Slot #{slot_id} error: {e}")
            self.vision_failed_count += 1
            self.last_error_message = str(e)
        finally:
            self._in_flight_urls.discard(url)
            self._release_slot(slot_id)

    # =========================================================================
    # 🖼️ 4. 비전 Image-to-Text 처리 및 본문 주입
    # =========================================================================
    async def _fetch_unprocessed_vision_articles(self, limit: int = 4) -> List[tuple]:
        fetch_size = limit + len(self._in_flight_urls) + 16
        async with self.session_factory() as session:
            stmt = text("""
                SELECT id, source_id, url, title, content, published_at, metadata
                FROM articles
                WHERE (metadata->>'images') IS NOT NULL
                  AND jsonb_array_length(metadata->'images') > 0
                  AND ((metadata->>'vision_processed') IS NULL OR (metadata->>'vision_processed')::boolean = false)
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            res = await session.execute(stmt, {"limit": fetch_size})
            rows = res.fetchall()

            selected = []
            for row in rows:
                url = row[2]
                if url not in self._in_flight_urls:
                    self._in_flight_urls.add(url)
                    selected.append(row)
                    if len(selected) >= limit:
                        break
            return selected

    async def _process_vision_article(
        self,
        art_id: int,
        source_id: Optional[int],
        url: str,
        title: str,
        content: str,
        published_at: datetime,
        raw_metadata: dict,
        images: List[Any]
    ) -> bool:
        updated_images = []
        injected_descriptions = []

        for idx, img_item in enumerate(images[:3]):  # 기사당 최대 3장
            img_url = img_item if isinstance(img_item, str) else img_item.get("url")
            if not img_url:
                continue

            desc_res = await self.transcriber.describe_image(
                image_url=img_url,
                model_name=self.vision_model_name,
                referer=url
            )
            desc_text = desc_res.get("description", "")
            is_success = desc_res.get("status") == "success"

            if is_success and desc_text and not desc_text.startswith("이미지 다운로드 실패"):
                injected_descriptions.append(f"[이미지 {idx+1} 설명: {desc_text}]")
                updated_images.append({
                    "url": img_url,
                    "caption": desc_text,
                    "injected_at": datetime.now().isoformat(),
                    "model_used": self.vision_model_name
                })
            else:
                updated_images.append({
                    "url": img_url,
                    "caption": None,
                    "error": desc_res.get("error")
                })

        new_content = content
        if injected_descriptions:
            injected_block = "\n\n" + "\n".join(injected_descriptions)
            if injected_block not in new_content:
                new_content += injected_block

        meta_update = dict(raw_metadata or {})
        meta_update["vision_processed"] = True
        meta_update["vision_model"] = self.vision_model_name
        meta_update["vision_processed_at"] = datetime.now().isoformat()
        meta_update["images"] = updated_images

        async with self.session_factory() as session:
            update_stmt = text("""
                UPDATE articles
                SET content = :content,
                    metadata = CAST(:meta AS jsonb)
                WHERE url = :url AND published_at = :published_at
            """)
            await session.execute(update_stmt, {
                "content": new_content,
                "meta": json.dumps(meta_update, ensure_ascii=False),
                "url": url,
                "published_at": published_at
            })

            if injected_descriptions:
                event_stmt = text("""
                    INSERT INTO crawl_events (source_id, event_type, title, url, details)
                    VALUES (:source_id, 'llm_enrich', :title, :url, CAST(:details AS jsonb))
                """)
                await session.execute(event_stmt, {
                    "source_id": source_id,
                    "title": f"비전 캡셔닝: {title[:40]}",
                    "url": url,
                    "details": json.dumps({
                        "type": "vision_image_to_text",
                        "image_count": len(updated_images),
                        "descriptions": injected_descriptions[:2],
                        "model": self.vision_model_name
                    }, ensure_ascii=False)
                })

            await session.commit()
        return True

    # =========================================================================
    # 📝 5. 텍스트 NLP 처리 (GPU2 vLLM 고속 호출 + Ollama Fallback)
    # =========================================================================
    async def _fetch_unprocessed_text_articles(self, limit: int = 8) -> List[tuple]:
        fetch_size = limit + len(self._in_flight_urls) + 16
        async with self.session_factory() as session:
            stmt = text("""
                SELECT id, source_id, url, title, content, published_at
                FROM articles
                WHERE summary IS NULL OR summary = '' OR (metadata->>'nlp_processed') IS NULL OR (metadata->>'nlp_processed')::boolean = false
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            res = await session.execute(stmt, {"limit": fetch_size})
            rows = res.fetchall()

            selected = []
            for row in rows:
                url = row[2]
                title = row[3] or ""
                if url not in self._in_flight_urls and title not in self._in_flight_titles:
                    self._in_flight_urls.add(url)
                    self._in_flight_titles.add(title)
                    selected.append(row)
                    if len(selected) >= limit:
                        break
            return selected

    async def _enrich_article(self, title: str, content: str, url: str) -> Optional[Dict[str, Any]]:
        system_instruction = "당신은 금융/뉴스 전문 분석 AI입니다. 주어진 기사를 분석하여 반드시 유효한 JSON 형식으로만 응답하세요."
        prompt = f"""다음 기사 본문을 분석하여 핵심 요약, 감성 분석 점수(-1.0 ~ 1.0), 주요 엔티티 및 관련 주식/코인 종목을 도출하세요.

제목: {title}
URL: {url}
본문:
{content[:3000]}

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "summary": "1~2문장으로 압축한 핵심 요약",
  "sentiment_score": 0.25,
  "key_entities": ["엔티티1", "엔티티2"],
  "related_stocks": ["관련종목명 또는 코인명"]
}}
"""
        target_model = self.text_model_name
        clean_model = target_model.replace("gpu2:", "").replace("ollama:", "")
        is_explicit_ollama = target_model.startswith("ollama:") or self.default_provider == "ollama"

        # 1차: GPU2 vLLM 호출 시도 (최대 3회 지수 백오프 재시도)
        if not is_explicit_ollama:
            gpu2_model = clean_model if clean_model not in ["auto", "default"] else self.gpu2_default_model
            payload = {
                "model": gpu2_model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1024
            }
            max_retries = getattr(config, "GPU2_MAX_RETRIES", 3)
            backoff = getattr(config, "GPU2_RETRY_BACKOFF", 1.5)
            last_err = None

            for attempt in range(1, max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        resp = await client.post(f"{self.gpu2_base_url}/chat/completions", json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            cleaned = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
                            json_match = re.search(r"\{[\s\S]*\}", cleaned)
                            if json_match:
                                self.provider_used = "gpu2"
                                self.consecutive_gpu2_errors = 0
                                return json.loads(json_match.group(0))
                        else:
                            last_err = f"HTTP {resp.status_code}: {resp.text[:100]}"
                except Exception as e:
                    last_err = str(e)

                if attempt < max_retries:
                    wait_time = backoff * (2 ** (attempt - 1))
                    logger.info(f"GPU2 text NLP attempt {attempt}/{max_retries} failed ({last_err}). Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)

            self.consecutive_gpu2_errors += 1
            logger.warning(f"GPU2 LLM enrichment completely failed after {max_retries} attempts: {last_err}")

        # 2차: Local Ollama (명시적 요청이거나 ENABLE_OLLAMA_FALLBACK=True 일 때만)
        if is_explicit_ollama or self.enable_ollama_fallback:
            try:
                logger.info("Calling Local Ollama for text NLP enrichment...")
                ollama_m = clean_model if clean_model not in ["auto", "default"] else config.OLLAMA_MODEL
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": ollama_m,
                            "prompt": prompt,
                            "format": "json",
                            "stream": False
                        }
                    )
                    if resp.status_code == 200:
                        raw = resp.json().get("response", "")
                        cleaned = raw.strip("` \n").replace("json\n", "")
                        self.provider_used = "ollama"
                        return json.loads(cleaned)
            except Exception as e:
                logger.warning(f"Ollama generate failed ({clean_model}): {e}")

        return None

    async def _save_enriched_data(self, art_id: int, source_id: Optional[int], published_at: datetime, url: str, title: str, enriched: Dict[str, Any]):
        summary = enriched.get("summary") or ""
        sentiment_score = float(enriched.get("sentiment_score") or 0.0)
        key_entities = enriched.get("key_entities") or []
        related_stocks = enriched.get("related_stocks") or []

        meta_update = {
            "nlp_processed": True,
            "nlp_model": self.text_model_name,
            "provider": self.provider_used,
            "processed_at": datetime.now().isoformat(),
            "key_entities": key_entities,
            "related_stocks": related_stocks
        }

        async with self.session_factory() as session:
            update_stmt = text("""
                UPDATE articles
                SET summary = :summary,
                    sentiment_score = :sentiment,
                    metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:meta AS jsonb)
                WHERE url = :url AND published_at = :published_at
            """)
            await session.execute(update_stmt, {
                "summary": summary,
                "sentiment": sentiment_score,
                "meta": json.dumps(meta_update, ensure_ascii=False),
                "url": url,
                "published_at": published_at
            })

            if title:
                dup_stmt = text("""
                    UPDATE articles
                    SET summary = :summary,
                        sentiment_score = :sentiment,
                        metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:meta AS jsonb)
                    WHERE title = :title AND (summary IS NULL OR summary = '')
                """)
                await session.execute(dup_stmt, {
                    "summary": summary,
                    "sentiment": sentiment_score,
                    "meta": json.dumps(meta_update, ensure_ascii=False),
                    "title": title
                })

            event_stmt = text("""
                INSERT INTO crawl_events (source_id, event_type, title, url, details)
                VALUES (:source_id, 'llm_enrich', :title, :url, CAST(:details AS jsonb))
            """)
            await session.execute(event_stmt, {
                "source_id": source_id,
                "title": title[:500],
                "url": url,
                "details": json.dumps({
                    "summary_preview": summary[:120],
                    "sentiment_score": sentiment_score,
                    "model": self.text_model_name,
                    "provider": self.provider_used
                }, ensure_ascii=False)
            })
            await session.commit()

    async def _mark_article_failed(self, url: str, published_at: datetime, reason: str):
        try:
            async with self.session_factory() as session:
                stmt = text("""
                    UPDATE articles
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('nlp_processed', true, 'nlp_error', :reason, 'nlp_failed_at', :now)
                    WHERE url = :url AND published_at = :published_at
                """)
                await session.execute(stmt, {
                    "reason": reason[:200],
                    "now": datetime.now().isoformat(),
                    "url": url,
                    "published_at": published_at
                })
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to mark article error state: {e}")

    # =========================================================================
    # 📊 6. 통합 상태 조회 (동시성 파라미터 및 실시간 슬롯 매트릭스 포함)
    # =========================================================================
    async def get_unified_status(self) -> Dict[str, Any]:
        text_pending = 0
        vision_pending = 0
        total_articles = 0

        try:
            async with self.session_factory() as session:
                cnt_stmt = text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN summary IS NULL OR summary = '' OR (metadata->>'nlp_processed') IS NULL OR (metadata->>'nlp_processed')::boolean = false THEN 1 END) as text_pending,
                        COUNT(CASE WHEN (metadata->>'images') IS NOT NULL AND jsonb_array_length(metadata->'images') > 0 AND ((metadata->>'vision_processed') IS NULL OR (metadata->>'vision_processed')::boolean = false) THEN 1 END) as vision_pending
                    FROM articles
                """)
                res = await session.execute(cnt_stmt)
                row = res.fetchone()
                if row:
                    total_articles = row[0]
                    text_pending = row[1]
                    vision_pending = row[2]
        except Exception as e:
            logger.error(f"Error querying pending counts: {e}")

        active_slots_list = list(self.active_slots.values())
        current_primary_task = active_slots_list[0] if active_slots_list else None

        return {
            # 병렬 동시성 설정
            "concurrency": self.concurrency,
            "text_concurrency": self.text_concurrency,
            "vision_concurrency": self.vision_concurrency,
            "gpu_device": "Dual RTX 5070 Ti (8-Way 병렬 가속)",
            "provider": self.provider_used,
            "active_slots": active_slots_list,

            # 텍스트 서브시스템 상태
            "text_state": self.text_state,
            "text_model_name": self.text_model_name,
            "text_pending_count": text_pending,
            "text_processed_count": self.text_processed_count,
            "text_failed_count": self.text_failed_count,

            # 비전 서브시스템 상태
            "vision_state": self.vision_state,
            "vision_model_name": self.vision_model_name,
            "vision_pending_count": vision_pending,
            "vision_processed_count": self.vision_processed_count,
            "vision_failed_count": self.vision_failed_count,

            # 공통 상태
            "total_articles": total_articles,
            "current_task": current_primary_task,
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
            "last_error_message": self.last_error_message
        }

    # 하위 호환성 get_status()
    async def get_status(self) -> Dict[str, Any]:
        unified = await self.get_unified_status()
        return {
            "state": self.text_state,
            "model_name": self.text_model_name,
            "batch_size": self.concurrency,
            "interval_seconds": self.interval_seconds,
            "processed_count": self.text_processed_count,
            "failed_count": self.text_failed_count,
            "pending_count": unified["text_pending_count"],
            "total_articles": unified["total_articles"],
            "current_item_title": self.active_slots.get(1, {}).get("title") if self.active_slots else None,
            "last_processed_at": unified["last_processed_at"],
            "last_error_message": unified["last_error_message"],
            "unified": unified
        }

concurrent_gpu_worker = ConcurrentGPUWorker()
unified_gpu_worker = concurrent_gpu_worker
llm_worker = concurrent_gpu_worker  # 하위 호환성 유지

