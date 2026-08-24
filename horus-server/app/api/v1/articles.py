from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleRead, ArticleSearchResult

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.get("", response_model=ArticleSearchResult)
async def list_articles(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_id: Optional[int] = None,
    category: Optional[str] = None
):
    offset = (page - 1) * page_size
    query = select(Article)
    count_query = select(func.count(Article.id))

    if source_id:
        query = query.where(Article.source_id == source_id)
        count_query = count_query.where(Article.source_id == source_id)
    if category:
        query = query.where(Article.category == category)
        count_query = count_query.where(Article.category == category)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    query = query.order_by(desc(Article.id)).offset(offset).limit(page_size)
    result = await db.execute(query)
    articles = result.scalars().all()

    return ArticleSearchResult(total=total, items=articles)

@router.get("/search", response_model=ArticleSearchResult)
async def search_articles(
    keyword: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    PostgreSQL GIN Trigram 인덱스를 활용한 23.8M건 초고속 전문검색
    """
    offset = (page - 1) * page_size
    
    # ILIKE 검색 (GIN Trigram 인덱스 적용)
    filter_cond = or_(
        Article.title.ilike(f"%{keyword}%"),
        Article.content.ilike(f"%{keyword}%")
    )
    
    count_query = select(func.count(Article.id)).where(filter_cond)
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    query = (
        select(Article)
        .where(filter_cond)
        .order_by(desc(Article.id))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    articles = result.scalars().all()

    return ArticleSearchResult(total=total, items=articles)

@router.get("/{article_id}", response_model=ArticleRead)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db)
):
    query = select(Article).where(Article.id == article_id).limit(1)
    result = await db.execute(query)
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
