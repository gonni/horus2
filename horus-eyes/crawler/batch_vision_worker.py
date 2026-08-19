import asyncio
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from crawler.vision_transcriber import VisionTranscriber

logger = logging.getLogger(__name__)

# 로컬 이미지 다운로드 및 보관 디렉토리
DEFAULT_IMAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images"))
IMAGE_STORE_DIR = os.getenv("HORUS_IMAGE_STORE_DIR", DEFAULT_IMAGE_DIR)
os.makedirs(IMAGE_STORE_DIR, exist_ok=True)

class BatchVisionWorker:
    """
    본문에 이미지 위치 표식({{HORUS_IMG:...}})이 삽입된 상태로 크롤링된 문서들의 이미지를
    비동기 백그라운드 배치(Image-to-Text)로 처리하여 본문 텍스트 내에 설명을 주입하고 치환합니다.
    """
    def __init__(self, vision_model: Optional[str] = None):
        self.transcriber = VisionTranscriber(model_name=vision_model)

    async def save_image_to_local_store(self, image_url: str, article_id: Optional[int], order_index: int, referer: Optional[str] = None) -> Optional[str]:
        """
        이미지를 로컬 스토리지에 다운로드하여 보관하고 로컬 파일 경로를 반환합니다.
        """
        try:
            filename = f"art_{article_id or 'temp'}_img_{order_index}_{int(datetime.now().timestamp())}.png"
            local_path = os.path.join(IMAGE_STORE_DIR, filename)

            headers = self.transcriber._get_image_headers(image_url, referer=referer)
            async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True, verify=False) as client:
                res = await client.get(image_url)
                if res.status_code == 200 and len(res.content) > 100:
                    with open(local_path, "wb") as f:
                        f.write(res.content)
                    return local_path
        except Exception as e:
            logger.warning(f"Failed to save local image for {image_url}: {e}")
        return None

    async def process_single_image(
        self,
        db: AsyncSession,
        image_record: Any,
        vision_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        단일 ArticleImage 레코드에 대해 Vision 설명문 도출 및 본문 치환을 수행합니다.
        """
        # 순환 참조 방지용 동적 import
        from app.models.article import Article
        from app.models.article_image import ArticleImage

        image_record.status = "PROCESSING"
        await db.commit()

        # 1. 로컬 이미지 다운로드 및 보관
        local_path = await self.save_image_to_local_store(
            image_url=image_record.image_url,
            article_id=image_record.article_id,
            order_index=image_record.order_index,
            referer=image_record.article_url
        )
        if local_path:
            image_record.local_path = local_path

        # 2. Vision LLM 설명 생성
        desc_res = await self.transcriber.describe_image(
            image_url=image_record.image_url,
            model_name=vision_model,
            referer=image_record.article_url
        )
        description = desc_res.get("description", "")
        status = desc_res.get("status", "error")

        if status == "success" and description:
            image_record.description = description
            image_record.model_used = desc_res.get("model_used", vision_model or self.transcriber.model_name)
            image_record.status = "COMPLETED"
            image_record.processed_at = datetime.now()

            # 3. 🌟 연결된 Article 본문(content) 내의 표식 토큰({{HORUS_IMG:...}})을 완성된 텍스트 설명으로 치환!
            if image_record.article_id:
                stmt = select(Article).where(Article.id == image_record.article_id)
                res = await db.execute(stmt)
                article = res.scalars().first()
                if article and article.content:
                    replacement = f"\n\n[🖼️ 첨부 이미지 #{image_record.order_index} 내용: {description}]\n\n"
                    # 정확한 토큰 치환
                    if image_record.placeholder_token in article.content:
                        article.content = article.content.replace(image_record.placeholder_token, replacement)
                    else:
                        article.content = article.content + replacement

            await db.commit()
            return {"id": image_record.id, "status": "COMPLETED", "description": description}

        else:
            image_record.status = "FAILED"
            image_record.error_message = desc_res.get("error") or description
            await db.commit()
            return {"id": image_record.id, "status": "FAILED", "error": image_record.error_message}

    async def process_batch(
        self,
        db: AsyncSession,
        batch_size: int = 10,
        vision_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        PENDING 상태의 이미지들을 배치로 로드하여 Vision 변환 및 본문 주입을 일괄 수행합니다.
        """
        from app.models.article_image import ArticleImage

        stmt = select(ArticleImage).where(ArticleImage.status == "PENDING").order_index_by(ArticleImage.id).limit(batch_size) if hasattr(select(ArticleImage).where(ArticleImage.status == "PENDING"), 'order_index_by') else select(ArticleImage).where(ArticleImage.status == "PENDING").order_by(ArticleImage.id).limit(batch_size)
        res = await db.execute(stmt)
        pending_records = res.scalars().all()

        if not pending_records:
            return {
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "message": "처리 대기 중인 이미지가 없습니다."
            }

        results = []
        success_count = 0
        failed_count = 0

        for rec in pending_records:
            result = await self.process_single_image(db, rec, vision_model=vision_model)
            results.append(result)
            if result["status"] == "COMPLETED":
                success_count += 1
            else:
                failed_count += 1

        return {
            "processed_count": len(pending_records),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
            "message": f"{len(pending_records)}개 이미지 배치 처리 완료 (성공: {success_count}, 실패: {failed_count})"
        }

    @staticmethod
    async def get_queue_stats(db: AsyncSession) -> Dict[str, int]:
        """
        현재 이미지 큐의 상태별 개수 통계를 반환합니다.
        """
        from app.models.article_image import ArticleImage

        stmt = select(ArticleImage.status, func.count(ArticleImage.id)).group_by(ArticleImage.status)
        res = await db.execute(stmt)
        counts = dict(res.all())

        return {
            "pending": counts.get("PENDING", 0),
            "processing": counts.get("PROCESSING", 0),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
            "total": sum(counts.values())
        }
