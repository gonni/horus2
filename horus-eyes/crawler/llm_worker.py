import asyncio
import logging
import json
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from crawler.config import config
from crawler.vision_transcriber import VisionTranscriber

logger = logging.getLogger(__name__)

class UnifiedGPUWorker:
    """
    단일 직렬(Serial) GPU 작업 큐 워커
    - Ollama/GPU의 단일 스레드 병목 및 VRAM 충돌을 방지하기 위해 단일 루프에서 1건씩 순차 실행 (FIFO)
    - 2개의 독립 서브시스템 지원:
        1) 📝 텍스트 NLP 정제 (요약, 감성 분석, 엔티티 추출)
        2) 🖼️ 비전 Image-to-Text (이미지 텍스트 변환, 본문 주입, 임시파일 미저장 & 원본 URL 보존)
    - 각 서브시스템별 독립 시작/일시중지/정지 제어 완비
    """
    def __init__(self):
        self.engine = create_async_engine(config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.ollama_url: str = config.OLLAMA_BASE_URL or "http://localhost:11434"
        self.transcriber = VisionTranscriber()

        # 서브시스템 1: 텍스트 NLP 상태
        self.text_state: str = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.text_model_name: str = config.OLLAMA_MODEL or "gemma4:e4b-mlx"
        self.text_processed_count: int = 0
        self.text_failed_count: int = 0

        # 서브시스템 2: 비전 Image-to-Text 상태
        self.vision_state: str = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.vision_model_name: str = config.OLLAMA_MODEL or "gemma4:e4b-mlx"
        self.vision_processed_count: int = 0
        self.vision_failed_count: int = 0

        # 공통 워커 파라미터
        self.interval_seconds: float = 2.0
        self._worker_task: Optional[asyncio.Task] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        # 실시간 상태 모니터링
        self.current_task: Optional[Dict[str, Any]] = None
        self.last_processed_at: Optional[datetime] = None
        self.last_error_message: Optional[str] = None

    # =========================================================================
    # 📝 1. 텍스트 NLP 서브시스템 제어
    # =========================================================================
    async def start_text(self, model_name: Optional[str] = None):
        if model_name:
            self.text_model_name = model_name
        self.text_state = "RUNNING"
        self._pause_event.set()
        self._ensure_worker_running()
        logger.info(f"Text NLP Subsystem STARTED with model '{self.text_model_name}'")

    def pause_text(self):
        if self.text_state == "RUNNING":
            self.text_state = "PAUSED"
            logger.info("Text NLP Subsystem PAUSED (GPU load suspended).")

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
    async def start_vision(self, model_name: Optional[str] = None):
        if model_name:
            self.vision_model_name = model_name
        self.vision_state = "RUNNING"
        self._pause_event.set()
        self._ensure_worker_running()
        logger.info(f"Vision Image-to-Text Subsystem STARTED with model '{self.vision_model_name}'")

    def pause_vision(self):
        if self.vision_state == "RUNNING":
            self.vision_state = "PAUSED"
            logger.info("Vision Image-to-Text Subsystem PAUSED (GPU load suspended).")

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
    async def start(self, model_name: Optional[str] = None, batch_size: int = 2, interval_seconds: float = 3.0):
        await self.start_text(model_name=model_name)

    def pause(self):
        self.pause_text()

    def resume(self):
        self.resume_text()

    async def stop(self):
        self.stop_text()
        self.stop_vision()

    def _ensure_worker_running(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._unified_serial_loop())

    # =========================================================================
    # ⚡ 3. 단일 직렬(Serial) GPU 큐 실행 루프
    # =========================================================================
    async def _unified_serial_loop(self):
        logger.info("Unified GPU Serial Queue Worker loop started.")
        while self.text_state in ["RUNNING", "PAUSED"] or self.vision_state in ["RUNNING", "PAUSED"]:
            # 둘 다 실행 중이 아니면 대기
            if self.text_state != "RUNNING" and self.vision_state != "RUNNING":
                self.current_task = None
                await asyncio.sleep(1.0)
                continue

            did_work = False

            # --- 작업 A: 비전 Image-to-Text 우선 순차 처리 ---
            if self.vision_state == "RUNNING":
                try:
                    vision_arts = await self._fetch_unprocessed_vision_articles(1)
                    if vision_arts:
                        art = vision_arts[0]
                        art_id, source_id, url, title, content, published_at, raw_metadata = art
                        self.current_task = {
                            "type": "vision",
                            "title": title[:50],
                            "started_at": datetime.now().isoformat()
                        }
                        
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
                            did_work = True
                except Exception as e:
                    logger.error(f"Error in Vision serial task: {e}")
                    self.vision_failed_count += 1
                    self.last_error_message = str(e)

                if did_work:
                    await asyncio.sleep(self.interval_seconds)

            # --- 작업 B: 텍스트 NLP 요약/감성분석 순차 처리 ---
            if self.text_state == "RUNNING":
                try:
                    text_arts = await self._fetch_unprocessed_text_articles(1)
                    if text_arts:
                        art = text_arts[0]
                        art_id, source_id, url, title, content, published_at = art
                        self.current_task = {
                            "type": "text",
                            "title": title[:50],
                            "started_at": datetime.now().isoformat()
                        }
                        
                        enriched = await self._enrich_article(title, content, url)
                        if enriched:
                            await self._save_enriched_data(art_id, source_id, published_at, url, title, enriched)
                            self.text_processed_count += 1
                            self.last_processed_at = datetime.now()
                        else:
                            self.text_failed_count += 1
                        did_work = True
                except Exception as e:
                    logger.error(f"Error in Text NLP serial task: {e}")
                    self.text_failed_count += 1
                    self.last_error_message = str(e)

                if did_work:
                    await asyncio.sleep(self.interval_seconds)

            # 처리할 항목이 없으면 잠시 대기
            if not did_work:
                self.current_task = None
                await asyncio.sleep(2.0)

        self.current_task = None
        logger.info("Unified GPU Serial Queue Worker loop finished.")

    # =========================================================================
    # 🖼️ 4. 비전 Image-to-Text 처리 및 본문 주입
    # =========================================================================
    async def _fetch_unprocessed_vision_articles(self, limit: int = 1) -> List[tuple]:
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
            res = await session.execute(stmt, {"limit": limit})
            return res.fetchall()

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
        """
        1) 이미지 URL에서 메모리 Base64 변환 후 VLM 실행 (디스크 파일 저장 안 함)
        2) 도출된 설명을 본문에 [이미지 설명: ...] 형태로 주입
        3) 원본 절대경로 URL은 articles.metadata['images']에 영구 보존
        """
        updated_images = []
        injected_descriptions = []

        for idx, img_item in enumerate(images[:3]):  # 1기사당 최대 3장 처리
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

        # 본문에 설명 주입
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
            # 1. 기사 업데이트
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

            # 2. crawl_events에 비전 처리 이벤트 기록
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
    # 📝 5. 텍스트 NLP 처리 (요약, 감성 분석, 엔티티)
    # =========================================================================
    async def _fetch_unprocessed_text_articles(self, limit: int = 1) -> List[tuple]:
        async with self.session_factory() as session:
            stmt = text("""
                SELECT id, source_id, url, title, content, published_at
                FROM articles
                WHERE summary IS NULL OR summary = '' OR (metadata->>'nlp_processed') IS NULL OR (metadata->>'nlp_processed')::boolean = false
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            res = await session.execute(stmt, {"limit": limit})
            return res.fetchall()

    async def _enrich_article(self, title: str, content: str, url: str) -> Optional[Dict[str, Any]]:
        prompt = f"""
다음 기사 본문을 분석하여 핵심 요약, 감성 분석 점수(-1.0 ~ 1.0), 주요 엔티티 및 관련 주식/코인 종목을 도출하세요.

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
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.text_model_name,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False
                    }
                )
                if resp.status_code == 200:
                    raw = resp.json().get("response", "")
                    cleaned = raw.strip("` \n").replace("json\n", "")
                    return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Ollama generate failed ({self.text_model_name}): {e}")
        return None

    async def _save_enriched_data(self, art_id: int, source_id: Optional[int], published_at: datetime, url: str, title: str, enriched: Dict[str, Any]):
        summary = enriched.get("summary") or ""
        sentiment_score = float(enriched.get("sentiment_score") or 0.0)
        key_entities = enriched.get("key_entities") or []
        related_stocks = enriched.get("related_stocks") or []

        meta_update = {
            "nlp_processed": True,
            "nlp_model": self.text_model_name,
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
                    "model": self.text_model_name
                }, ensure_ascii=False)
            })
            await session.commit()

    # =========================================================================
    # 📊 6. 통합 상태 조회 (텍스트 & 비전 분리 대기 큐 및 통계)
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

        return {
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

            # 공통 직렬 큐 상태
            "total_articles": total_articles,
            "current_task": self.current_task,
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
            "last_error_message": self.last_error_message
        }

    # 하위 호환성 get_status()
    async def get_status(self) -> Dict[str, Any]:
        unified = await self.get_unified_status()
        return {
            "state": self.text_state,
            "model_name": self.text_model_name,
            "batch_size": 1,
            "interval_seconds": self.interval_seconds,
            "processed_count": self.text_processed_count,
            "failed_count": self.text_failed_count,
            "pending_count": unified["text_pending_count"],
            "total_articles": unified["total_articles"],
            "current_item_title": self.current_task.get("title") if self.current_task else None,
            "last_processed_at": unified["last_processed_at"],
            "last_error_message": unified["last_error_message"],
            "unified": unified
        }

unified_gpu_worker = UnifiedGPUWorker()
llm_worker = unified_gpu_worker  # 하위 호환성 유지
