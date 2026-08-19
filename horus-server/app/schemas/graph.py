from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class GraphNode(BaseModel):
    id: str
    name: str
    group: int = 1
    val: float = 10.0 # 크기/가중치
    category: Optional[str] = "keyword" # keyword, stock, topic, article

class GraphLink(BaseModel):
    source: str
    target: str
    value: float = 1.0 # 엣지 가중치 / 동시출현 빈도
    label: Optional[str] = "CO_OCCURS_WITH"

class GraphDataResponse(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]
