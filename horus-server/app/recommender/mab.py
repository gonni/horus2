import math
import numpy as np
from typing import List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.feedback import RecoFeedback
from app.models.article import Article

class MABRecommender:
    """
    Multi-Armed Bandit (MAB) Recommendation Engine
    - Thompson Sampling (Beta Distribution)
    - UCB1 (Upper Confidence Bound)
    """
    
    @staticmethod
    def thompson_sampling(successes: int, failures: int) -> float:
        # Beta(alpha, beta) -> alpha = successes + 1, beta = failures + 1
        return np.random.beta(successes + 1, failures + 1)

    @staticmethod
    def ucb1(successes: int, total_trials: int, total_all_trials: int, c: float = 1.414) -> float:
        if total_trials == 0:
            return float("inf")
        exploitation = successes / total_trials
        exploration = c * math.sqrt(math.log(max(total_all_trials, 1)) / total_trials)
        return exploitation + exploration

    @classmethod
    async def get_recommended_articles(
        cls, db: AsyncSession, limit: int = 5, explore_ratio: float = 0.2
    ) -> List[Tuple[Article, float]]:
        # 1. 최근 48시간 기사 후보군 가져오기
        stmt = select(Article).order_by(Article.published_at.desc()).limit(50)
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        if not candidates:
            return []

        article_ids = [a.id for a in candidates]

        # 2. 각 기사의 피드백 통계 집계 (클릭수, 노출수)
        stats_stmt = (
            select(
                RecoFeedback.article_id,
                func.count(RecoFeedback.id).filter(RecoFeedback.event_type == "click").label("clicks"),
                func.count(RecoFeedback.id).filter(RecoFeedback.event_type == "impression").label("impressions")
            )
            .where(RecoFeedback.article_id.in_(article_ids))
            .group_by(RecoFeedback.article_id)
        )
        stats_res = await db.execute(stats_stmt)
        feedback_map = {row.article_id: (row.clicks or 0, row.impressions or 0) for row in stats_res.all()}

        # 3. Thompson Sampling 스코어 계산
        scored_candidates = []
        for art in candidates:
            clicks, impressions = feedback_map.get(art.id, (0, 0))
            non_clicks = max(impressions - clicks, 0)
            
            # Thompson Sampling score
            sample_score = cls.thompson_sampling(clicks, non_clicks)
            
            # 최신성(Recency) 부스팅 결합
            scored_candidates.append((art, float(sample_score)))

        # 4. 상위 Top N 추천
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:limit]

mab_engine = MABRecommender()
