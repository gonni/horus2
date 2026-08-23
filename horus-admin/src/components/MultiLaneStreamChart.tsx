"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { MultiLaneStreamResponse, LaneSeries, CallTick, BucketEventBreakdown, api } from "@/lib/api";
import { Play, Pause, RefreshCw, ShieldCheck, Activity, Layers, Flame, Compass, Globe, Sparkles, Clock } from "lucide-react";

export type TimeRangeOption = "1m" | "10m" | "1h" | "1d" | "7d";

interface MultiLaneStreamChartProps {
  initialRange?: TimeRangeOption;
  autoRefreshInterval?: number; // ms
  onRangeChange?: (range: TimeRangeOption) => void;
}

// 🎨 호출 종류별 표준 색상 팔레트
const EVENT_COLORS = {
  seed_scan: { color: "#10b981", label: "Seed URL 스캔", bg: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" },
  article_ingest: { color: "#3b82f6", label: "신규 기사 호출", bg: "bg-blue-500/20 text-blue-300 border-blue-500/40" },
  image_ingest: { color: "#a855f7", label: "이미지/미디어 수집", bg: "bg-purple-500/20 text-purple-300 border-purple-500/40" },
  llm_enrich: { color: "#eab308", label: "LLM AI 정제", bg: "bg-amber-500/20 text-amber-300 border-amber-500/40" },
  error: { color: "#ef4444", label: "호출 오류/재시도", bg: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
};

export const MultiLaneStreamChart: React.FC<MultiLaneStreamChartProps> = ({
  initialRange = "1m",
  autoRefreshInterval = 2000,
  onRangeChange,
}) => {
  const [range, setRange] = useState<TimeRangeOption>(initialRange);
  const [streamData, setStreamData] = useState<MultiLaneStreamResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isLiveStreaming, setIsLiveStreaming] = useState(true);
  const [currentTimeStr, setCurrentTimeStr] = useState<string>("");

  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    timeIndex: number;
    timeLabel: string;
    laneBreakdown: {
      name: string;
      color: string;
      breakdown?: BucketEventBreakdown;
      totalCalls: number;
      tps: number;
    }[];
    activeLane?: {
      name: string;
      breakdown?: BucketEventBreakdown;
      totalCalls: number;
    };
  } | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sizeRef = useRef<{ width: number; height: number; dpr: number }>({ width: 800, height: 430, dpr: 1 });

  // 1. API 데이터 페치
  const fetchStreamData = useCallback(async (r: TimeRangeOption) => {
    if (document.hidden) return;
    try {
      const res = await api.get<MultiLaneStreamResponse>(`/crawl/metrics/stream?range=${r}`);
      setStreamData(res.data);
      setCurrentTimeStr(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
    } catch (e) {
      console.error("Failed to fetch stream data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRangeChange = (newRange: TimeRangeOption) => {
    setRange(newRange);
    setLoading(true);
    fetchStreamData(newRange);
    if (onRangeChange) onRangeChange(newRange);
  };

  useEffect(() => {
    if (initialRange && initialRange !== range) {
      setRange(initialRange);
      fetchStreamData(initialRange);
    }
  }, [initialRange]);

  // 2. 실시간 주기적 데이터 갱신
  useEffect(() => {
    fetchStreamData(range);
    const timer = setInterval(() => {
      if (isLiveStreaming && !document.hidden) {
        fetchStreamData(range);
      }
    }, autoRefreshInterval);

    const handleVisibility = () => {
      if (!document.hidden && isLiveStreaming) {
        fetchStreamData(range);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [range, isLiveStreaming, autoRefreshInterval, fetchStreamData]);

  // 3. 고성능 정통 Cubism.js 이벤트 스택/밀도 차트 렌더러
  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    const { width, height, dpr } = sizeRef.current;
    if (width <= 0 || height <= 0) return;

    const targetW = Math.round(width * dpr);
    const targetH = Math.round(height * dpr);
    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW;
      canvas.height = targetH;
    }

    ctx.save();
    ctx.scale(dpr, dpr);

    // 1. Cubism 정통 다크 슬레이트 배경
    ctx.fillStyle = "#070b12";
    ctx.fillRect(0, 0, width, height);

    const lanes = streamData?.lanes || [];
    const timestamps = streamData?.timestamps || [];
    const numLanes = Math.max(1, lanes.length);
    const topAxisHeight = 26;
    const leftLabelWidth = 150;
    const rightValueWidth = 70; // Cubism 우측 순간 호출값 표시 영역
    const chartWidth = Math.max(10, width - leftLabelWidth - rightValueWidth);
    const chartHeight = Math.max(10, height - topAxisHeight - 8);
    const laneHeight = chartHeight / numLanes;
    const bucketCount = Math.max(1, timestamps.length);

    // 2. 상단 시간축 룰러 (Cubism Time Ruler)
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(leftLabelWidth, 0, chartWidth, topAxisHeight);

    ctx.fillStyle = "rgba(148, 163, 184, 0.85)";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    const numTicks = Math.min(8, bucketCount);
    if (numTicks > 1) {
      for (let i = 0; i < numTicks; i++) {
        const tIdx = Math.floor((i / (numTicks - 1)) * (bucketCount - 1));
        const tLabel = timestamps[tIdx] || "";
        const x = leftLabelWidth + (i / (numTicks - 1)) * chartWidth;

        ctx.fillText(tLabel, x, 13);

        // 수직 눈금선
        ctx.strokeStyle = "rgba(51, 65, 85, 0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, 18);
        ctx.lineTo(x, height - 6);
        ctx.stroke();
      }
    }

    // 3. 우측 끝 [LIVE 현재 시점] 유입선
    const liveX = leftLabelWidth + chartWidth;
    ctx.strokeStyle = "rgba(16, 185, 129, 0.95)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(liveX, 6);
    ctx.lineTo(liveX, height - 6);
    ctx.stroke();

    // 4. 레인별 Cubism Horizon / 스택 이벤트 바코드 렌더링
    const isSecondLevel = range === "1m"; // 초단위 뷰 모드 여부

    lanes.forEach((lane, laneIdx) => {
      const laneY = topAxisHeight + laneIdx * laneHeight;
      const laneBottom = laneY + laneHeight;

      // 레인 배경 스트라이프
      ctx.fillStyle = laneIdx % 2 === 0 ? "#090e18" : "#0d131f";
      ctx.fillRect(leftLabelWidth, laneY, chartWidth, laneHeight);

      // 레인 구분선
      ctx.strokeStyle = "rgba(51, 65, 85, 0.55)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, laneBottom);
      ctx.lineTo(width, laneBottom);
      ctx.stroke();

      // 좌측 레이블 영역
      ctx.fillStyle = lane.color || "#10b981";
      ctx.fillRect(8, laneY + laneHeight / 2 - 8, 3.5, 16);

      ctx.fillStyle = "#f1f5f9";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      const truncatedName = lane.name.length > 16 ? lane.name.slice(0, 15) + "…" : lane.name;
      ctx.fillText(truncatedName, 16, laneY + laneHeight / 2 - 4);

      ctx.font = "9px monospace";
      ctx.fillStyle = "rgba(148, 163, 184, 0.8)";
      ctx.fillText(`누적 ${lane.total_count}건`, 16, laneY + laneHeight / 2 + 7);

      // 우측 순간 호출 카운터 (Cubism 스타일)
      const instantCount = lane.current_instant_count ?? (lane.raw_counts ? lane.raw_counts[lane.raw_counts.length - 1] : 0) ?? 0;
      ctx.fillStyle = instantCount > 0 ? "#34d399" : "rgba(100, 116, 139, 0.6)";
      ctx.font = "bold 12px monospace";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(`${instantCount} ${isSecondLevel ? "req/s" : "calls"}`, width - 8, laneY + laneHeight / 2);

      // 🔴 1.0 TPS 엄격 한계 점선 (레인 상단 20%)
      const tps1Y = laneY + laneHeight * 0.2;
      ctx.strokeStyle = "rgba(239, 68, 68, 0.35)";
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(leftLabelWidth, tps1Y);
      ctx.lineTo(leftLabelWidth + chartWidth, tps1Y);
      ctx.stroke();
      ctx.setLineDash([]);

      // ==============================================================================
      // 📊 Cubism 정통 초고밀도 스택 이벤트 바 (2px 고정 미세 틱 바코드)
      // ==============================================================================
      const breakdownList = lane.type_breakdown || [];
      const rawCounts = lane.raw_counts || [];
      const barSlotWidth = chartWidth / bucketCount;
      const barWidth = 2; // 📐 사용자 요구사항: 정확히 2픽셀 고정 미세 틱

      // 초단위 뷰에서는 최대 1.0 TPS(1회/초) 고정 스케일, 장기 뷰에서는 레인 내 피크 기준 스케일링
      const maxCountInLane = isSecondLevel ? 1 : Math.max(3, ...rawCounts, ...(breakdownList.map(b => b.total || 0)));
      const maxBarHeight = laneHeight * 0.76;

      for (let i = 0; i < bucketCount; i++) {
        const x = Math.round(leftLabelWidth + i * barSlotWidth + (barSlotWidth - barWidth) / 2);
        const bData = breakdownList[i];
        const count = rawCounts[i] || (bData ? bData.total : 0) || 0;

        if (count > 0 && bData) {
          // 초단위 뷰(1m)에서는 각 1초당 최대 1개 단일 호출만 발생 (2px 바)
          if (isSecondLevel) {
            const h = maxBarHeight * 0.9;
            const baseY = laneBottom - 2;

            if (bData.seed_scan > 0) {
              ctx.fillStyle = EVENT_COLORS.seed_scan.color;
              ctx.fillRect(x, baseY - h, barWidth, h);
            } else if (bData.article_ingest > 0) {
              ctx.fillStyle = EVENT_COLORS.article_ingest.color;
              ctx.fillRect(x, baseY - h, barWidth, h);
            } else if (bData.image_ingest > 0) {
              ctx.fillStyle = EVENT_COLORS.image_ingest.color;
              ctx.fillRect(x, baseY - h, barWidth, h);
            } else if (bData.llm_enrich > 0) {
              ctx.fillStyle = EVENT_COLORS.llm_enrich.color;
              ctx.fillRect(x, baseY - h, barWidth, h);
            } else if (bData.error > 0) {
              ctx.fillStyle = EVENT_COLORS.error.color;
              ctx.fillRect(x, baseY - h, barWidth, h);
            }
          } else {
            // 시간 범위가 커질 때(10m, 1h, 24h, 7d): 시간 눈금 내 복수 요청이 포함될 때만 중첩(Stack)하여 렌더링
            const totalNorm = Math.min(1.0, count / maxCountInLane);
            const totalH = Math.max(3, totalNorm * maxBarHeight);

            const seedH = (bData.seed_scan / count) * totalH;
            const articleH = (bData.article_ingest / count) * totalH;
            const imageH = (bData.image_ingest / count) * totalH;
            const llmH = (bData.llm_enrich / count) * totalH;
            const errorH = (bData.error / count) * totalH;

            let currBaseY = laneBottom - 2;

            // 1. 🟢 Seed URL 스캔
            if (seedH > 0) {
              ctx.fillStyle = EVENT_COLORS.seed_scan.color;
              ctx.fillRect(x, currBaseY - seedH, barWidth, seedH);
              currBaseY -= seedH;
            }

            // 2. 🔵 신규 기사 페이지 호출
            if (articleH > 0) {
              ctx.fillStyle = EVENT_COLORS.article_ingest.color;
              ctx.fillRect(x, currBaseY - articleH, barWidth, articleH);
              currBaseY -= articleH;
            }

            // 3. 🟣 이미지/미디어 수집
            if (imageH > 0) {
              ctx.fillStyle = EVENT_COLORS.image_ingest.color;
              ctx.fillRect(x, currBaseY - imageH, barWidth, imageH);
              currBaseY -= imageH;
            }

            // 4. 🟡 LLM AI 요약/정제
            if (llmH > 0) {
              ctx.fillStyle = EVENT_COLORS.llm_enrich.color;
              ctx.fillRect(x, currBaseY - llmH, barWidth, llmH);
              currBaseY -= llmH;
            }

            // 5. 🔴 오류/재시도
            if (errorH > 0) {
              ctx.fillStyle = EVENT_COLORS.error.color;
              ctx.fillRect(x, currBaseY - errorH, barWidth, errorH);
              currBaseY -= errorH;
            }
          }
        } else {
          // 유휴(0회) 시점: 얇은 슬레이트 베이스라인 2px 점
          ctx.fillStyle = "rgba(51, 65, 85, 0.4)";
          ctx.fillRect(x, laneBottom - 2, barWidth, 1);
        }
      }

    });

    // 5. 마우스 호버 가이드라인 (Cubism Interactive Crosshair Ruler)
    if (hoverInfo && hoverInfo.x >= leftLabelWidth && hoverInfo.x <= leftLabelWidth + chartWidth) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.75)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([3, 2]);
      ctx.beginPath();
      ctx.moveTo(hoverInfo.x, topAxisHeight);
      ctx.lineTo(hoverInfo.x, height - 6);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.restore();
  }, [streamData, hoverInfo, range]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
        sizeRef.current = { width, height: Math.max(400, height), dpr };
        drawChart();
      }
    });

    ro.observe(container);
    return () => ro.disconnect();
  }, [drawChart]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !streamData || !streamData.timestamps.length) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const { width, height } = sizeRef.current;
    const topAxisHeight = 26;
    const leftLabelWidth = 150;
    const rightValueWidth = 70;
    const chartWidth = Math.max(10, width - leftLabelWidth - rightValueWidth);
    const lanes = streamData.lanes || [];
    const timestamps = streamData.timestamps || [];
    const numLanes = Math.max(1, lanes.length);
    const laneHeight = (height - topAxisHeight - 8) / numLanes;

    if (x < leftLabelWidth || x > leftLabelWidth + chartWidth || y < topAxisHeight) {
      setHoverInfo(null);
      return;
    }

    const relX = x - leftLabelWidth;
    const timeIdx = Math.min(
      timestamps.length - 1,
      Math.max(0, Math.floor((relX / chartWidth) * timestamps.length))
    );
    const timeLabel = timestamps[timeIdx] || "";

    const activeLaneIdx = Math.min(
      lanes.length - 1,
      Math.max(0, Math.floor((y - topAxisHeight) / laneHeight))
    );
    const curLane = lanes[activeLaneIdx];

    const breakdownAll = lanes.map((l) => {
      const bd = l.type_breakdown ? l.type_breakdown[timeIdx] : undefined;
      const count = l.raw_counts ? l.raw_counts[timeIdx] || 0 : bd?.total || 0;
      const tps = l.values ? l.values[timeIdx] || 0 : 0;
      return {
        name: l.name,
        color: l.color,
        breakdown: bd,
        totalCalls: count,
        tps,
      };
    });

    const activeBd = curLane?.type_breakdown ? curLane.type_breakdown[timeIdx] : undefined;

    setHoverInfo({
      x,
      y,
      timeIndex: timeIdx,
      timeLabel,
      laneBreakdown: breakdownAll,
      activeLane: curLane
        ? {
            name: curLane.name,
            breakdown: activeBd,
            totalCalls: curLane.raw_counts ? curLane.raw_counts[timeIdx] || 0 : activeBd?.total || 0,
          }
        : undefined,
    });
  };

  const handleMouseLeave = () => {
    setHoverInfo(null);
  };

  return (
    <div className="space-y-3.5">
      {/* ============================================================================== */}
      {/* 1. 상단 트래픽 현황 & 호출 종류별 범례 및 시간 범위 탭 (Cubism Style) */}
      {/* ============================================================================== */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 flex flex-col gap-3 shadow-inner">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white tracking-tight flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-emerald-400" />
                수집 트래픽 & 호출 시점 타임라인
              </span>
              <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                [기준시간: {currentTimeStr || "LIVE"}]
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              초단위(1분 뷰)에서는 max 1.0 TPS 단일 호출을 정밀 검사하고, 장기 뷰에서는 시간 눈금별 복수 요청을 중첩 확인합니다.
            </p>
          </div>

          {/* ⏱️ 시간 범위 탭 선택기 (1분 초단위 / 10분 / 1시간 / 24시간 / 7일) */}
          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-800 self-start sm:self-auto">
            {(
              [
                { id: "1m", label: "⚡ 1분 (1초 틱)" },
                { id: "10m", label: "⏱️ 10분" },
                { id: "1h", label: "🕐 1시간" },
                { id: "1d", label: "📅 24시간" },
                { id: "7d", label: "🗓️ 7일" },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                onClick={() => handleRangeChange(t.id)}
                className={`px-3 py-1 text-xs font-bold rounded-lg transition ${
                  range === t.id
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* 🎨 호출 종류별 색상 범례 및 라이브 제어 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-medium bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500"></span>
              Seed 스캔
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-medium bg-blue-500/15 text-blue-300 border-blue-500/30">
              <span className="w-2.5 h-2.5 rounded-sm bg-blue-500"></span>
              신규 기사 호출
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-medium bg-purple-500/15 text-purple-300 border-purple-500/30">
              <span className="w-2.5 h-2.5 rounded-sm bg-purple-500"></span>
              이미지/비전 수집
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-medium bg-amber-500/15 text-amber-300 border-amber-500/30">
              <span className="w-2.5 h-2.5 rounded-sm bg-amber-500"></span>
              LLM AI 정제
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-medium bg-rose-500/15 text-rose-300 border-rose-500/30">
              <span className="w-2.5 h-2.5 rounded-sm bg-rose-500"></span>
              오류/재시도
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setIsLiveStreaming(!isLiveStreaming)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition ${
                isLiveStreaming
                  ? "bg-emerald-600/20 text-emerald-300 border-emerald-500/40"
                  : "bg-slate-800 text-slate-400 border-slate-700"
              }`}
            >
              {isLiveStreaming ? <Pause className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3 fill-current" />}
              <span>{isLiveStreaming ? "라이브 갱신 중" : "일시정지"}</span>
            </button>

            <button
              onClick={() => {
                setLoading(true);
                fetchStreamData(range);
              }}
              disabled={loading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="즉시 새로고침"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {/* ============================================================================== */}
      {/* 2. Cubism.js 다중 레인 정밀 타임라인 차트 캔버스 */}
      {/* ============================================================================== */}
      <div
        ref={containerRef}
        className="relative w-full h-[430px] bg-[#070b12] border border-slate-800 rounded-xl overflow-hidden shadow-2xl select-none"
      >
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="w-full h-full block cursor-crosshair"
        />

        {/* ============================================================================== */}
        {/* 3. 인터랙티브 크로스헤어 정밀 팝오버 툴팁 */}
        {/* ============================================================================== */}
        {hoverInfo && (
          <div
            className="absolute z-30 pointer-events-none bg-slate-900 border border-slate-700/90 rounded-xl p-3 shadow-2xl text-xs text-slate-200 min-w-[260px]"
            style={{
              left: Math.min(Math.max(160, hoverInfo.x - 130), (sizeRef.current.width || 800) - 280),
              top: Math.min(hoverInfo.y + 15, (sizeRef.current.height || 400) - 180),
            }}
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-2">
              <span className="font-mono text-emerald-400 font-bold flex items-center gap-1">
                ⏱️ {hoverInfo.timeLabel}
              </span>
              <span className="text-[10px] text-slate-400">호출 타임라인 인스펙터</span>
            </div>

            {hoverInfo.activeLane && (
              <div className="space-y-1.5">
                <div className="font-bold text-white flex items-center justify-between">
                  <span className="truncate max-w-[170px]">{hoverInfo.activeLane.name}</span>
                  <span className="font-mono text-emerald-300">합계 {hoverInfo.activeLane.totalCalls}회</span>
                </div>

                {hoverInfo.activeLane.breakdown ? (
                  <div className="grid grid-cols-2 gap-1.5 pt-1 text-[11px] bg-slate-950/80 p-2 rounded-lg border border-slate-800/80">
                    <div className="flex items-center justify-between text-emerald-300">
                      <span>🟢 Seed 스캔:</span>
                      <span className="font-mono font-bold">{hoverInfo.activeLane.breakdown.seed_scan}건</span>
                    </div>
                    <div className="flex items-center justify-between text-blue-300">
                      <span>🔵 기사 호출:</span>
                      <span className="font-mono font-bold">{hoverInfo.activeLane.breakdown.article_ingest}건</span>
                    </div>
                    <div className="flex items-center justify-between text-purple-300">
                      <span>🟣 이미지 수집:</span>
                      <span className="font-mono font-bold">{hoverInfo.activeLane.breakdown.image_ingest}건</span>
                    </div>
                    <div className="flex items-center justify-between text-amber-300">
                      <span>🟡 LLM 정제:</span>
                      <span className="font-mono font-bold">{hoverInfo.activeLane.breakdown.llm_enrich}건</span>
                    </div>
                    {hoverInfo.activeLane.breakdown.error > 0 && (
                      <div className="col-span-2 flex items-center justify-between text-rose-400 border-t border-slate-800 pt-1">
                        <span>🔴 호출 오류:</span>
                        <span className="font-mono font-bold">{hoverInfo.activeLane.breakdown.error}건</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-[11px] text-slate-400">
                    순간 호출: {hoverInfo.activeLane.totalCalls}건
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>수집 호스트(Seed)별 독립 1.0 TPS 엄격 준수 (각 수집 대상별로 독립 병렬 처리되며, 개별 레인은 1.0 TPS 점선을 초과하지 않습니다)</span>
        </div>
        <span>마우스를 차트 위에 올리면 특정 시점의 호출 상세 정보를 검사할 수 있습니다.</span>
      </div>

    </div>
  );
};
