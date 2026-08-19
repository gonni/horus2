"use client";

import { useEffect, useRef, useState } from "react";
import { api, GraphData } from "@/lib/api";
import { Share2, RefreshCw, ZoomIn, Info } from "lucide-react";

export default function Graph3DPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchGraph = async (centerKeyword?: string) => {
    setLoading(true);
    try {
      const url = centerKeyword
        ? `/topics/graph-3d?center_keyword=${encodeURIComponent(centerKeyword)}&limit=40`
        : `/topics/graph-3d?limit=40`;
      const res = await api.get(url);
      setGraphData(res.data);
    } catch (e) {
      console.error("Failed to load 3D graph:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, []);

  useEffect(() => {
    if (!graphData || !containerRef.current) return;

    let ForceGraph3D: any;
    let graphInstance: any;

    import("3d-force-graph").then((module) => {
      ForceGraph3D = module.default;
      containerRef.current!.innerHTML = "";

      graphInstance = ForceGraph3D()(containerRef.current!)
        .graphData(graphData)
        .nodeLabel((node: any) => `${node.name} (가중치: ${node.val})`)
        .nodeAutoColorBy("group")
        .nodeRelSize(5)
        .linkWidth((link: any) => Math.min(link.value * 0.8, 4))
        .linkOpacity(0.5)
        .linkColor(() => "#6366f1")
        .backgroundColor("#090d16")
        .onNodeClick((node: any) => {
          setSelectedNode(node.name);
          fetchGraph(node.name);
        });

      graphInstance.cameraPosition({ z: 250 });
    });

    return () => {
      if (graphInstance && containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [graphData]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Share2 className="w-6 h-6 text-indigo-400" />
            3D 단어 동시출현 지식 그래프 (Neo4j)
          </h1>
          <p className="text-sm text-slate-400">
            기사에서 실시간 추출된 핵심 키워드 간의 연관 관계망 시각화 (노드 클릭 시 중심 탐색)
          </p>
        </div>

        <div className="flex items-center gap-2">
          {selectedNode && (
            <span className="text-xs bg-indigo-500/20 text-indigo-400 px-3 py-1.5 rounded-lg border border-indigo-500/30">
              중심 단어: <strong>{selectedNode}</strong>
            </span>
          )}
          <button
            onClick={() => {
              setSelectedNode(null);
              fetchGraph();
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            전체 뷰 리셋
          </button>
        </div>
      </div>

      {/* 3D 캔버스 영역 */}
      <div className="relative w-full h-[650px] bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm text-slate-400 text-sm">
            Neo4j 그래프 관계망을 로딩 중입니다...
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />

        {/* 안내 뱃지 */}
        <div className="absolute bottom-4 left-4 bg-slate-900/80 backdrop-blur border border-slate-800 px-3 py-2 rounded-lg text-xs text-slate-400 flex items-center gap-2">
          <Info className="w-4 h-4 text-indigo-400" />
          <span>마우스 드래그로 360° 회전, 휠로 줌인/줌아웃 가능합니다.</span>
        </div>
      </div>
    </div>
  );
}
