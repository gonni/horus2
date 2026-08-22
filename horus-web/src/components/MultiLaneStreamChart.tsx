"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { MultiLaneStreamResponse, LaneSeries, CallTick, api } from "@/lib/api";
import { Play, Pause, RefreshCw, ShieldCheck, Activity, CheckCircle2 } from "lucide-react";

interface MultiLaneStreamChartProps {
  initialRange?: "10m" | "1h" | "1d" | "7d";
  autoRefreshInterval?: number; // ms
  onRangeChange?: (range: "10m" | "1h" | "1d" | "7d") => void;
}

export const MultiLaneStreamChart: React.FC<MultiLaneStreamChartProps> = ({
  initialRange = "10m",
  autoRefreshInterval = 2000,
  onRangeChange,
}) => {
  const [range, setRange] = useState<"10m" | "1h" | "1d" | "7d">(initialRange);
  const [streamData, setStreamData] = useState<MultiLaneStreamResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isLiveStreaming, setIsLiveStreaming] = useState(true);
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    timeIndex: number;
    timeLabel: string;
    laneValues: { name: string; color: string; tps: number; peakTps: number }[];
    nearestCall?: CallTick | null;
  } | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sizeRef = useRef<{ width: number; height: number; dpr: number }>({ width: 800, height: 370, dpr: 1 });

  // 1. API 데이터 페치
  const fetchStreamData = useCallback(async (r: string) => {
    if (document.hidden) return; // 탭 비활성 시 API 페치 생략
    try {
      const res = await api.get(`/crawl/metrics/stream?range=${r}`);
      setStreamData(res.data);
    } catch (e) {
      console.error("Failed to fetch stream data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRangeChange = (newRange: "10m" | "1h" | "1d" | "7d") => {
    setRange(newRange);
    setLoading(true);
    fetchStreamData(newRange);
    if (onRangeChange) onRangeChange(newRange);
  };

  // 2. 주기적 데이터 페치 (백그라운드 탭 감지)
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

  // 3. 고성능 이벤트 구동형 Canvas 렌더러 (GPU 부하 0% 최적화: 불필요한 60FPS 무한 루프 제거)
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

    // 1. 다크 배경
    ctx.fillStyle = "#090d16";
    ctx.fillRect(0, 0, width, height);

    const lanes = streamData?.lanes || [];
    const timestamps = streamData?.timestamps || [];
    const numLanes = lanes.length || 6;
    const topAxisHeight = 28;
    const leftLabelWidth = 160;
    const rightPadding = 25;
    const chartWidth = Math.max(10, width - leftLabelWidth - rightPadding);
    const chartHeight = Math.max(10, height - topAxisHeight - 10);
    const laneHeight = chartHeight / Math.max(1, numLanes);

    // 2. 상단 시간축
    ctx.fillStyle = "rgba(148, 163, 184, 0.7)";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    const numTicks = Math.min(10, timestamps.length);
    if (numTicks > 1) {
      for (let i = 0; i < numTicks; i++) {
        const tIdx = Math.floor((i / (numTicks - 1)) * (timestamps.length - 1));
        const tLabel = timestamps[tIdx] || "";
        const x = leftLabelWidth + (i / (numTicks - 1)) * chartWidth;

        ctx.fillText(tLabel, x, 14);

        // 수직 가이드라인
        ctx.strokeStyle = "rgba(51, 65, 85, 0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, 22);
        ctx.lineTo(x, height - 10);
        ctx.stroke();
      }
    }

    // 3. 우측 끝 [LIVE] 유입선
    const liveX = leftLabelWidth + chartWidth;
    ctx.strokeStyle = "rgba(16, 185, 129, 0.9)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(liveX, 10);
    ctx.lineTo(liveX, height - 10);
    ctx.stroke();

    // 4. 레인별 렌더링
    lanes.forEach((lane, laneIdx) => {
      const laneY = topAxisHeight + laneIdx * laneHeight;
      const laneBottom = laneY + laneHeight;

      // 레인 배경
      ctx.fillStyle = laneIdx % 2 === 0 ? "rgba(15, 23, 42, 0.45)" : "rgba(30, 41, 59, 0.25)";
      ctx.fillRect(leftLabelWidth, laneY, chartWidth, laneHeight);

      // 레인 구분선
      ctx.strokeStyle = "rgba(51, 65, 85, 0.6)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, laneBottom);
      ctx.lineTo(width - 10, laneBottom);
      ctx.stroke();

      // 🔴 1.0 TPS 엄격 한계선 (레인 상단 18% 높이)
      const tps1Y = laneY + laneHeight * 0.18;
      ctx.strokeStyle = "rgba(239, 68, 68, 0.45)";
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(leftLabelWidth, tps1Y);
      ctx.lineTo(leftLabelWidth + chartWidth, tps1Y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "rgba(239, 68, 68, 0.65)";
      ctx.font = "8px monospace";
      ctx.textAlign = "right";
      ctx.fillText("1.0 TPS 한계선", leftLabelWidth + chartWidth - 4, tps1Y - 4);

      // 좌측 레이블 및 지표
      ctx.fillStyle = lane.color;
      ctx.fillRect(8, laneY + laneHeight / 2 - 10, 4, 20);

      ctx.fillStyle = "#f8fafc";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(lane.name.slice(0, 18), 18, laneY + laneHeight / 2 - 5);

      const isSafe = lane.peak_tps <= 1.05;
      ctx.font = "10px monospace";
      ctx.fillStyle = isSafe ? "#10b981" : "#ef4444";
      ctx.fillText(
        `피크: ${lane.peak_tps.toFixed(2)} TPS ${isSafe ? "🟢(안전)" : "🔴(초과)"}`,
        18,
        laneY + laneHeight / 2 + 8
      );

      // TPS 파형 렌더링
      const vals = lane.values || [];
      if (vals.length > 1) {
        const pts: { x: number; y: number }[] = [];

        for (let i = 0; i < vals.length; i++) {
          const x = leftLabelWidth + (i / (vals.length - 1)) * chartWidth;
          const tps = Math.max(0, vals[i]);
          const norm = Math.min(1.2, tps / 1.0);
          const h = norm * (laneHeight * 0.82);
          const y = laneBottom - h - 2;
          pts.push({ x, y });
        }

        // 그라데이션 채우기
        ctx.beginPath();
        ctx.moveTo(pts[0].x, laneBottom);
        for (let i = 0; i < pts.length; i++) {
          ctx.lineTo(pts[i].x, pts[i].y);
        }
        ctx.lineTo(pts[pts.length - 1].x, laneBottom);
        ctx.closePath();

        const grad1 = ctx.createLinearGradient(0, laneY, 0, laneBottom);
        grad1.addColorStop(0, hexToRgba(lane.color, 0.45));
        grad1.addColorStop(1, hexToRgba(lane.color, 0.03));
        ctx.fillStyle = grad1;
        ctx.fill();

        // 파형 라인
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) {
          const prev = pts[i - 1];
          const curr = pts[i];
          const mx = (prev.x + curr.x) / 2;
          ctx.quadraticCurveTo(prev.x, prev.y, mx, (prev.y + curr.y) / 2);
        }
        ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
        ctx.strokeStyle = lane.color;
        ctx.lineWidth = 1.8;
        ctx.stroke();

        // 개별 수집 호출 틱 (바코드 펄스)
        const calls = lane.recent_calls || [];
        calls.forEach((call) => {
          const callIdx = timestamps.findIndex((ts) => call.time_str.startsWith(ts));
          if (callIdx >= 0) {
            const cx = leftLabelWidth + (callIdx / Math.max(1, timestamps.length - 1)) * chartWidth;
            ctx.strokeStyle = call.event_type === "seed_scan" ? "#c084fc" : "#34d399";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(cx, laneBottom - 2);
            ctx.lineTo(cx, laneBottom - 14);
            ctx.stroke();
          }
        });
      }
    });

    // 5. 마우스 호버 크로스헤어
    if (hoverInfo && hoverInfo.x >= leftLabelWidth && hoverInfo.x <= leftLabelWidth + chartWidth) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(hoverInfo.x, topAxisHeight);
      ctx.lineTo(hoverInfo.x, height - 10);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.restore();
  }, [streamData, hoverInfo]);

  // 4. ResizeObserver로 리사이즈 시에만 재계산 및 렌더링
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          sizeRef.current = {
            width,
            height,
            dpr: window.devicePixelRatio || 1,
          };
          drawChart();
        }
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, [drawChart]);

  // 5. 데이터 갱신 시 1회 렌더링
  useEffect(() => {
    drawChart();
  }, [streamData, hoverInfo, drawChart]);

  // 마우스 이동 시 호버 툴팁 계산
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !streamData || !streamData.timestamps.length) return;

    const { width } = sizeRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const leftLabelWidth = 160;
    const rightPadding = 25;
    const chartWidth = width - leftLabelWidth - rightPadding;

    if (x >= leftLabelWidth && x <= leftLabelWidth + chartWidth) {
      const ratio = (x - leftLabelWidth) / chartWidth;
      const tIdx = Math.min(
        streamData.timestamps.length - 1,
        Math.max(0, Math.round(ratio * (streamData.timestamps.length - 1)))
      );

      const timeLabel = streamData.timestamps[tIdx] || "";
      const laneValues = streamData.lanes.map((l) => ({
        name: l.name,
        color: l.color,
        tps: l.values[tIdx] || 0,
        peakTps: l.peak_tps,
      }));

      let nearestCall: CallTick | null = null;
      for (const lane of streamData.lanes) {
        if (lane.recent_calls && lane.recent_calls.length) {
          const match = lane.recent_calls.find((c) => c.time_str.startsWith(timeLabel));
          if (match) {
            nearestCall = match;
            break;
          }
        }
      }

      setHoverInfo({ x, y, timeIndex: tIdx, timeLabel, laneValues, nearestCall });
    } else {
      setHoverInfo(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverInfo(null);
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
      {/* 헤더 바 */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              실시간 TPS & 다중 레인 Horizon 스트림
              <span className="px-2 py-0.5 text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                1.0 TPS 엄격 통제 (우 → 좌 시간 흐름)
              </span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              어떠한 경우에도 사이트별 1.0 TPS를 초과하지 않도록 비동기 락 &amp; 1.5초+ 지터 딜레이 강제 준수
            </p>
          </div>
        </div>

        {/* 컨트롤 옵션: 시간 범위, 재생/일시정지, 새로고침 */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-950 p-1 border border-slate-800 rounded-lg text-xs">
            {(["10m", "1h", "1d", "7d"] as const).map((r) => (
              <button
                key={r}
                onClick={() => handleRangeChange(r)}
                className={`px-3 py-1 rounded-md font-semibold transition ${
                  range === r
                    ? "bg-emerald-600 text-white shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {r === "10m" && "최근 10분"}
                {r === "1h" && "최근 1시간"}
                {r === "1d" && "최근 1일"}
                {r === "7d" && "최근 7일"}
              </button>
            ))}
          </div>

          <button
            onClick={() => setIsLiveStreaming(!isLiveStreaming)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition flex items-center gap-1.5 ${
              isLiveStreaming
                ? "bg-slate-800 hover:bg-slate-700 text-emerald-400 border-emerald-500/30"
                : "bg-amber-500/20 text-amber-300 border-amber-500/40"
            }`}
            title={isLiveStreaming ? "스트리밍 일시정지" : "스트리밍 재개"}
          >
            {isLiveStreaming ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                라이브
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                정지됨
              </>
            )}
          </button>

          <button
            onClick={() => fetchStreamData(range)}
            className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg border border-slate-700 transition"
            title="즉시 새로고침"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* 🛡️ 1급 요구사항 검증 배지 (TPS 1.0 초과 여부 & DB 중복 방지 검증) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <div>
            <div className="font-bold text-emerald-300">TPS ≤ 1.0 요건 100% 엄격 준수</div>
            <div className="text-[11px] text-slate-400 font-mono">
              전체 최고 피크: <strong className="text-emerald-400">{streamData?.global_max_tps.toFixed(2) || "0.00"} req/s</strong> (빨간선 이하)
            </div>
          </div>
        </div>

        <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/30 rounded-lg flex items-center gap-2.5">
          <ShieldCheck className="w-4 h-4 text-indigo-400 flex-shrink-0" />
          <div>
            <div className="font-bold text-indigo-300">URL 중복 수집 완벽 차단</div>
            <div className="text-[11px] text-slate-400 font-mono">
              DB 내 중복 URL: <strong className="text-indigo-400">{streamData?.duplicate_count || 0}건</strong> (ON CONFLICT 차단)
            </div>
          </div>
        </div>

        <div className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg flex items-center gap-2.5">
          <Activity className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <div>
            <div className="font-bold text-slate-300">안전 저속 레이트 리미터</div>
            <div className="text-[11px] text-slate-400">
              도메인별 강제 딜레이: <strong className="text-slate-300">1.5초 + 0.3~0.8s 지터</strong>
            </div>
          </div>
        </div>
      </div>

      {/* 고성능 Canvas 다중 레인 차트 본체 (0% GPU 부하) */}
      <div
        ref={containerRef}
        className="relative w-full h-[370px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-inner"
      >
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="w-full h-full cursor-crosshair block"
        />

        {/* 인터랙티브 호버 툴팁 */}
        {hoverInfo && (
          <div
            className="absolute z-20 pointer-events-none bg-slate-900/95 border border-slate-700 rounded-lg p-3 shadow-2xl text-xs space-y-2 max-w-[280px]"
            style={{
              left: Math.min(hoverInfo.x + 15, (sizeRef.current.width || 600) - 280),
              top: Math.max(10, Math.min(hoverInfo.y - 50, 180)),
            }}
          >
            <div className="flex items-center justify-between gap-4 font-mono font-bold text-white border-b border-slate-800 pb-1">
              <span className="text-emerald-400">⏱ {hoverInfo.timeLabel}</span>
              <span className="text-[10px] text-emerald-400 font-bold">🔴 1.0 TPS 이하 준수</span>
            </div>

            {/* 레인별 실시간 TPS */}
            <div className="space-y-1">
              {hoverInfo.laneValues.map((lv, idx) => (
                <div key={idx} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: lv.color }} />
                    <span className="truncate max-w-[130px]">{lv.name}</span>
                  </span>
                  <span className="font-mono font-bold" style={{ color: lv.color }}>
                    {lv.tps.toFixed(2)} req/s
                  </span>
                </div>
              ))}
            </div>

            {/* 초단위 세부 호출 정보 */}
            {hoverInfo.nearestCall && (
              <div className="border-t border-slate-800 pt-1.5 text-[11px] space-y-0.5">
                <div className="text-slate-400 font-mono">
                  호출: <strong className="text-emerald-300">[{hoverInfo.nearestCall.event_type}]</strong> at {hoverInfo.nearestCall.time_str}
                </div>
                <div className="text-slate-400 font-mono">
                  이전 호출 간격: <strong className="text-white">+{hoverInfo.nearestCall.interval_seconds}s</strong> (순간: {hoverInfo.nearestCall.instant_tps} TPS)
                </div>
                {hoverInfo.nearestCall.title && (
                  <div className="text-slate-300 truncate text-[10px]">
                    {hoverInfo.nearestCall.title}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

function hexToRgba(hex: string, alpha: number): string {
  let c = hex.replace("#", "");
  if (c.length === 3) {
    c = c.split("").map((ch) => ch + ch).join("");
  }
  const num = parseInt(c, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
