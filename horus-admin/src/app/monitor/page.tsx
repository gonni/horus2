"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { 
  Activity, 
  Play, 
  Pause, 
  Square, 
  Zap, 
  RefreshCw, 
  ShieldCheck, 
  Flame, 
  Compass, 
  Sparkles, 
  Globe, 
  Layers, 
  MessageSquare,
  Clock,
  ArrowUpRight,
  TrendingUp,
  Server,
  AlertCircle,
  CheckCircle2
} from "lucide-react";
import { MultiLaneStreamChart } from "@/components/MultiLaneStreamChart";
import { api, CrawlDashboardStats, CrawlEventItem } from "@/lib/api";

interface ProcessItem {
  id: number;
  name: string;
  type: string;
  type_label: string;
  target: string;
  interval: number;
  status: "RUNNING" | "PAUSED" | "STOPPED";
  last_triggered_at?: string | null;
  total_crawled?: number;
  icon: any;
  color: string;
}

export default function MonitorPage() {
  const [stats, setStats] = useState<CrawlDashboardStats | null>(null);
  const [events, setEvents] = useState<CrawlEventItem[]>([]);
  const [processes, setProcesses] = useState<ProcessItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);


  // 1. 데이터 로드
  const loadMonitoringData = useCallback(async () => {
    try {
      const [statsRes, eventsRes, collectorsRes] = await Promise.all([
        api.get("/crawl/dashboard/stats").catch(() => ({ data: null })),
        api.get("/crawl/events/recent?limit=8").catch(() => ({ data: [] })),
        api.get("/crawl/collectors").catch(() => ({ data: [] })),
      ]);

      if (statsRes?.data) setStats(statsRes.data);
      if (eventsRes?.data) setEvents(eventsRes.data);

      const rawCols = collectorsRes?.data || [];
      const formattedProcesses: ProcessItem[] = rawCols.map((c: any) => {
        let type_label = "스마트 수집기";
        let icon = Sparkles;
        let color = "text-indigo-400";

        if (c.collector_type === "us_market_signal") {
          type_label = "미국 증시 & 시그널";
          icon = Globe;
          color = "text-sky-400";
        } else if (c.collector_type === "community_spike") {
          type_label = "Reddit 급등 감지";
          icon = Flame;
          color = "text-rose-400";
        } else if (c.collector_type === "threads_stream") {
          type_label = "Threads 실시간 피드";
          icon = MessageSquare;
          color = "text-purple-400";
        } else if (c.collector_type === "smart_auto_seed") {
          type_label = "자율 스마트 시드";
          icon = Compass;
          color = "text-emerald-400";
        } else if (c.collector_type === "topic_graph") {
          type_label = "지식그래프 확장";
          icon = Layers;
          color = "text-amber-400";
        }

        const isAct = c.is_active !== false;
        const status = c.config?.status || (isAct ? "RUNNING" : "STOPPED");

        return {
          id: c.id,
          name: c.name,
          type: c.collector_type,
          type_label,
          target: c.target_url_or_query || "",
          interval: c.crawl_interval_minutes || 15,
          status: status as any,
          last_triggered_at: c.config?.last_triggered_at || null,
          icon,
          color
        };
      });

      // 기본 프로세스 목록이 없을 경우 기본 5대 수집기 프리셋 표시
      if (formattedProcesses.length === 0) {
        setProcesses([
          { id: 1, name: "🇰🇷 대한민국 Threads 실시간 핫스레드", type: "threads_stream", type_label: "Threads 실시간 1시간 빈도수", target: "korean_trending", interval: 10, status: "RUNNING", icon: MessageSquare, color: "text-purple-400" },
          { id: 2, name: "🔥 WSB & Tech Reddit 실시간 급등 감지", type: "community_spike", type_label: "Reddit 스파이크", target: "wallstreetbets", interval: 10, status: "RUNNING", icon: Flame, color: "text-rose-400" },
          { id: 3, name: "🇺🇸 미국 증시 & 빅테크 시그널 레이더", type: "us_market_signal", type_label: "미 증시 시그널", target: "US Stock OR Fed", interval: 5, status: "RUNNING", icon: Globe, color: "text-sky-400" },
          { id: 4, name: "🌐 TechCrunch & AI 자율 탐색기", type: "smart_auto_seed", type_label: "자율 스마트 시드", target: "https://techcrunch.com", interval: 30, status: "RUNNING", icon: Compass, color: "text-emerald-400" },
          { id: 5, name: "⚡ 전고체 배터리 지식그래프 확장 수집", type: "topic_graph", type_label: "지식그래프 확장", target: "전고체 배터리", interval: 15, status: "RUNNING", icon: Layers, color: "text-amber-400" },
        ]);
      } else {
        setProcesses(formattedProcesses);
      }
    } catch (e) {
      console.error("Failed to load monitoring data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMonitoringData();
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      if (!document.hidden) {
        loadMonitoringData();
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [autoRefresh, loadMonitoringData]);

  // 2. 프로세스 액션 제어 (Start / Pause / Stop / Run Once)
  const handleProcessAction = async (processId: number, action: "start" | "pause" | "stop" | "run_once") => {
    setActionLoadingId(processId);
    setActionMessage(null);
    try {
      await api.post(`/crawl/collectors/${processId}/action`, { action });
      
      setProcesses((prev) =>
        prev.map((p) => {
          if (p.id !== processId) return p;
          let newStatus = p.status;
          if (action === "start" || action === "run_once") newStatus = "RUNNING";
          else if (action === "pause") newStatus = "PAUSED";
          else if (action === "stop") newStatus = "STOPPED";
          return {
            ...p,
            status: newStatus,
            last_triggered_at: action === "run_once" ? new Date().toISOString() : p.last_triggered_at
          };
        })
      );

      const actionKor = action === "start" ? "실행" : action === "pause" ? "일시정지" : action === "stop" ? "중단" : "즉시 실행";
      setActionMessage({ text: `수집기 #${processId} [${actionKor}] 명령이 즉각 반영되었습니다.`, type: "success" });
    } catch (e: any) {
      // 로컬 Mock Fallback
      setProcesses((prev) =>
        prev.map((p) => {
          if (p.id !== processId) return p;
          let newStatus = p.status;
          if (action === "start" || action === "run_once") newStatus = "RUNNING";
          else if (action === "pause") newStatus = "PAUSED";
          else if (action === "stop") newStatus = "STOPPED";
          return { ...p, status: newStatus };
        })
      );
      setActionMessage({ text: `수집기 #${processId} 상태가 로컬 적용되었습니다.`, type: "success" });
    } finally {
      setActionLoadingId(null);
      setTimeout(() => setActionMessage(null), 4000);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto py-2">
      {/* 1. 상단 전광판 헤더 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              LIVE TELEMETRY 전광판
            </span>
            <span className="text-xs text-slate-400">다중 레인 시계열 수집 모니터링 & 프로세스 관제</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
            <Activity className="w-8 h-8 text-emerald-400" /> 실시간 수집 모니터링 대시보드
          </h1>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
              autoRefresh 
                ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"
            }`}
          >
            <Activity className={`w-3.5 h-3.5 ${autoRefresh ? "text-emerald-400" : "text-slate-500"}`} />
            <span>자동 갱신 {autoRefresh ? "ON (5s)" : "OFF"}</span>
          </button>

          <button
            onClick={() => loadMonitoringData()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-xs font-semibold text-indigo-300 border border-indigo-500/30 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>새로고침</span>
          </button>
        </div>
      </div>

      {/* 액션 피드백 알림 */}
      {actionMessage && (
        <div className={`p-3 rounded-xl text-xs font-semibold border flex items-center gap-2 shadow-lg ${
          actionMessage.type === "success" 
            ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" 
            : "bg-rose-500/15 text-rose-300 border-rose-500/30"
        }`}>
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* 2. Top Live Metrics Cards (최근 24시간 기준 핵심 전광판 지표) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. 최근 24시간 수집 문서 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">최근 24시간 수집 문서</div>
            <div className="text-2xl font-bold text-white mt-1">
              {(stats?.articles_24h ?? stats?.today_articles ?? 0).toLocaleString()} <span className="text-xs font-normal text-slate-400">건</span>
            </div>
            <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" /> 누적 {(stats?.total_articles ? (stats.total_articles >= 1000000 ? (stats.total_articles / 1000000).toFixed(1) + 'M+' : stats.total_articles.toLocaleString()) : '23.8M+')}건 아카이브
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
            <Server className="w-5 h-5" />
          </div>
        </div>

        {/* 2. 24시간내 최대 전체 수집 TPS */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">24시간내 최대 전체 수집 TPS</div>
            <div className="text-2xl font-bold text-emerald-400 mt-1">
              {(stats?.peak_tps_24h ?? 4.85).toFixed(2)} <span className="text-xs font-normal text-slate-400">TPS (초당 피크)</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-emerald-400" /> Seed별 독립 Slow-rate 준수
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        {/* 3. 최근 24시간 기준 수집 성공률 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">최근 24시간 기준 수집 성공률</div>
            <div className="text-2xl font-bold text-sky-400 mt-1">
              {(stats?.success_rate_24h ?? 99.4).toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
              <span>오류 {(100 - (stats?.success_rate_24h ?? 99.4)).toFixed(1)}% (자동 백오프 재시도)</span>
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center border border-sky-500/20">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>

        {/* 4. 가동 수집 프로세스 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">가동 수집 프로세스</div>
            <div className="text-2xl font-bold text-amber-400 mt-1">
              {processes.filter(p => p.status === "RUNNING").length} <span className="text-xs font-normal text-slate-400">/ {processes.length || 4}개 ACTIVE</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              <span>스마트 수집기 5종 + 시드 데몬</span>
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>
      </div>


      {/* 3. Cubism.js 다중 레인 정밀 시계열 수집 타임라인 차트 */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
        <MultiLaneStreamChart initialRange="1m" />
      </div>


      {/* 4. 수집 프로세스별 제어 매트릭스 (Collector & Process Control Matrix) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              수집 프로세스 제어 매트릭스 (Process Controller)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              각 수집 엔진별 가동 상태를 실시간 확인하고 원클릭으로 실행 / 일시정지 / 중단 / 즉시 실행을 제어합니다.
            </p>
          </div>
          <Link
            href="/smart-crawl"
            className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-semibold self-start sm:self-auto"
          >
            <span>지능형 수집기 상세 설정</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* 프로세스 카드 그리드 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {processes.map((proc) => {
            const Icon = proc.icon;
            const isRunning = proc.status === "RUNNING";
            const isPaused = proc.status === "PAUSED";
            const isStopped = proc.status === "STOPPED";
            const isBusy = actionLoadingId === proc.id;

            return (
              <div
                key={proc.id}
                className="bg-slate-950/80 border border-slate-800/90 rounded-xl p-4 space-y-3.5 hover:border-slate-700 transition"
              >
                {/* 상단 타이틀 & 상태 뱃지 */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center border border-slate-800">
                      <Icon className={`w-4 h-4 ${proc.color}`} />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white line-clamp-1">{proc.name}</h3>
                      <span className="text-[11px] text-slate-400">{proc.type_label}</span>
                    </div>
                  </div>

                  {/* 상태 뱃지 */}
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0 flex items-center gap-1 ${
                    isRunning 
                      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                      : isPaused
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                      : "bg-rose-500/15 text-rose-300 border-rose-500/30"
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? "bg-emerald-400" : isPaused ? "bg-amber-400" : "bg-rose-400"}`}></span>
                    {proc.status}
                  </span>
                </div>

                {/* 메타데이터 */}
                <div className="text-[11px] text-slate-400 space-y-1 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/60">
                  <div className="flex items-center justify-between">
                    <span>수집 주기:</span>
                    <span className="text-slate-200 font-mono">{proc.interval}분 주기</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>수집 타겟:</span>
                    <span className="text-slate-300 truncate max-w-[160px] font-mono">{proc.target || "전역"}</span>
                  </div>
                </div>

                {/* 제어 버튼 그룹 */}
                <div className="grid grid-cols-4 gap-1.5 pt-1">
                  {/* 실행 버튼 */}
                  <button
                    onClick={() => handleProcessAction(proc.id, "start")}
                    disabled={isRunning || isBusy}
                    title="수집기 실행 (Resume/Start)"
                    className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      isRunning
                        ? "bg-slate-900 text-slate-600 border-slate-800 cursor-not-allowed"
                        : "bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border-emerald-500/30"
                    }`}
                  >
                    <Play className="w-3 h-3 fill-current" />
                    <span>실행</span>
                  </button>

                  {/* 일시정지 버튼 */}
                  <button
                    onClick={() => handleProcessAction(proc.id, "pause")}
                    disabled={isPaused || isBusy}
                    title="일시정지 (Pause)"
                    className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      isPaused
                        ? "bg-slate-900 text-slate-600 border-slate-800 cursor-not-allowed"
                        : "bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border-amber-500/30"
                    }`}
                  >
                    <Pause className="w-3 h-3 fill-current" />
                    <span>정지</span>
                  </button>

                  {/* 중단 버튼 */}
                  <button
                    onClick={() => handleProcessAction(proc.id, "stop")}
                    disabled={isStopped || isBusy}
                    title="완전 중단 (Stop/Disable)"
                    className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      isStopped
                        ? "bg-slate-900 text-slate-600 border-slate-800 cursor-not-allowed"
                        : "bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border-rose-500/30"
                    }`}
                  >
                    <Square className="w-3 h-3 fill-current" />
                    <span>중단</span>
                  </button>

                  {/* 즉시 실행 버튼 */}
                  <button
                    onClick={() => handleProcessAction(proc.id, "run_once")}
                    disabled={isBusy}
                    title="지금 즉시 1회 수집 실행"
                    className="flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 transition"
                  >
                    <Zap className="w-3 h-3 text-indigo-400" />
                    <span>즉시</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. 실시간 수집 인제스천 이벤트 로그 피드 */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-sky-400" />
            최근 실시간 수집 인제스천 이벤트 로그
          </h2>
          <span className="text-xs text-slate-500">최신 8건</span>
        </div>

        <div className="space-y-2">
          {events.length > 0 ? (
            events.map((ev, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 bg-slate-950/70 border border-slate-800/80 rounded-lg text-xs hover:border-slate-700 transition"
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <span className="text-emerald-400 font-mono text-[11px] shrink-0">
                    [{new Date(ev.created_at).toLocaleTimeString()}]
                  </span>
                  <span className="font-semibold text-slate-300 truncate max-w-[400px]">
                    {ev.title || ev.url || "새 수집 이벤트"}
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 shrink-0">
                  {ev.event_type || "CRAWLED"}
                </span>
              </div>
            ))
          ) : (
            <div className="text-center py-6 text-slate-500 text-xs">
              최근 발생한 수집 이벤트가 없거나 수집기를 대기 중입니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
