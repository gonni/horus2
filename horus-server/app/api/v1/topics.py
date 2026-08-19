from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.neo4j_client import get_neo4j_driver
from app.models.article import TermFrequency
from app.schemas.graph import GraphDataResponse, GraphNode, GraphLink
from app.schemas.article import TermFrequencyRead

router = APIRouter(prefix="/topics", tags=["Topics & Knowledge Graph"])

@router.get("/graph-3d", response_model=GraphDataResponse)
async def get_graph_3d(
    center_keyword: Optional[str] = None,
    limit: int = Query(30, ge=5, le=100)
):
    """
    Neo4j에서 3D 단어망 시각화용 노드/링크 데이터 고속 추출
    """
    driver = get_neo4j_driver()
    nodes_dict = {}
    links_list = []

    async with driver.session() as session:
        if center_keyword:
            cypher = """
            MATCH (k:Keyword {name: $keyword})-[r:CO_OCCURS_WITH]-(neighbor:Keyword)
            RETURN k.name AS source, neighbor.name AS target, r.weight AS weight
            ORDER BY r.weight DESC LIMIT $limit
            """
            result = await session.run(cypher, keyword=center_keyword, limit=limit)
        else:
            cypher = """
            MATCH (k1:Keyword)-[r:CO_OCCURS_WITH]->(k2:Keyword)
            RETURN k1.name AS source, k2.name AS target, r.weight AS weight
            ORDER BY r.weight DESC LIMIT $limit
            """
            result = await session.run(cypher, limit=limit)

        records = await result.data()
        for idx, row in enumerate(records):
            s = row["source"]
            t = row["target"]
            w = float(row["weight"])

            if s not in nodes_dict:
                nodes_dict[s] = GraphNode(id=s, name=s, group=1, val=15.0, category="keyword")
            if t not in nodes_dict:
                nodes_dict[t] = GraphNode(id=t, name=t, group=2, val=10.0, category="keyword")

            links_list.append(GraphLink(source=s, target=t, value=w))

    # 기본 데모 데이터 폴백 (Neo4j에 데이터가 아직 적재되지 않았을 때)
    if not nodes_dict:
        demo_keywords = ["삼성전자", "반도체", "인공지능", "금리", "코스피", "HBM", "엔비디아", "물가", "환율", "수출"]
        for i, k in enumerate(demo_keywords):
            nodes_dict[k] = GraphNode(id=k, name=k, group=(i % 3) + 1, val=12.0)
        links_list = [
            GraphLink(source="삼성전자", target="반도체", value=5.0),
            GraphLink(source="반도체", target="HBM", value=4.5),
            GraphLink(source="HBM", target="엔비디아", value=4.0),
            GraphLink(source="반도체", target="인공지능", value=3.8),
            GraphLink(source="코스피", target="삼성전자", value=3.5),
            GraphLink(source="금리", target="물가", value=4.2),
            GraphLink(source="금리", target="환율", value=3.9),
            GraphLink(source="환율", target="수출", value=3.0)
        ]

    return GraphDataResponse(
        nodes=list(nodes_dict.values()),
        links=links_list
    )

@router.get("/term-timeseries", response_model=List[TermFrequencyRead])
async def get_term_timeseries(
    term: str = Query(..., description="조회할 단어"),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    start_time = datetime.now() - timedelta(hours=hours)
    query = (
        select(TermFrequency)
        .where(TermFrequency.term == term, TermFrequency.time >= start_time)
        .order_by(TermFrequency.time.asc())
    )
    result = await db.execute(query)
    return result.scalars().all()
