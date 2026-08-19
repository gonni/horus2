from fastapi import APIRouter
from app.api.v1.articles import router as articles_router
from app.api.v1.crawl import router as crawl_router
from app.api.v1.stock import router as stock_router
from app.api.v1.topics import router as topics_router
from app.api.v1.reco import router as reco_router
from app.api.v1.llm import router as llm_router

api_v1_router = APIRouter()
api_v1_router.include_router(articles_router)
api_v1_router.include_router(crawl_router)
api_v1_router.include_router(stock_router)
api_v1_router.include_router(topics_router)
api_v1_router.include_router(reco_router)
api_v1_router.include_router(llm_router)
