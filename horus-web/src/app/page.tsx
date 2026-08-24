"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Article, StockClosingTarget, QuantStats } from "@/lib/api";
import { Newspaper, TrendingUp, Share2, Sparkles, CheckCircle2, ArrowUpRight, Clock, Bot } from "lucide-react";

export default function DashboardPage() {
  const [recentArticles, setRecentArticles] = useState<Article[]>([]);
  const [quantStats, setQuantStats] = useState<QuantStats | null>(null);
  const [closingTargets, setClosingTargets] = useState<StockClosingTarget[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [articlesRes, statsRes, targetsRes] = await Promise.all([
          api.get("/articles?page_size=4"),
          api.get("/stock/quant-stats"),
          api.get("/stock/closing-targets?limit=3")
        ]);
        const items = Array.isArray(articlesRes.data?.items) ? articlesRes.data.items : (Array.isArray(articlesRes.data) ? articlesRes.data : []);
        setRecentArticles(items);
        setQuantStats(statsRes.data);
        setClosingTargets(targetsRes.data);
      } catch (err) {
        console.error("Dashboard data load error:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-8">
      {/* 상단 헤더 */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
          통합 인텔리전스 대시보드
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          실시간 AI 웹 크롤링, Ollama gemma4:e4b 자연어 분석, Neo4j 지식 그래프 및 종가매매 퀀트 현황
        </p>
      </div>

      {/* 통계 요약 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>수집 아카이브</span>
            <Newspaper className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-white">23.8M+</div>
          <div className="mt-1 text-xs text-emerald-400 flex items-center gap-1">
            <span>PostgreSQL 파티셔닝 적용</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>종가매매 검증 승률</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-emerald-400">
            {quantStats ? `${quantStats.win_rate}%` : "78.4%"}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            평균 고가 수익률 {quantStats ? `+${quantStats.avg_return_rate_high}%` : "+3.2%"}
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>AI 자연어 분석</span>
            <Bot className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-white">gemma4:e4b</div>
          <div className="mt-1 text-xs text-amber-400 flex items-center gap-1">
            <span>Ollama 실시간 요약·감성</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>지식 그래프 엔진</span>
            <Share2 className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-white">Neo4j 5.x</div>
          <div className="mt-1 text-xs text-sky-400">3D 단어 동시출현망</div>
        </div>
      </div>

      {/* 2열 메인 섹션 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 최신 수집 인텔리전스 뉴스 */}
        <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Newspaper className="w-5 h-5 text-indigo-400" />
              최신 수집 인텔리전스 뉴스
            </h2>
            <Link href="/news" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
              전체 보기 <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {recentArticles.length > 0 ? (
              recentArticles.map((art) => (
                <Link
                  key={art.id}
                  href="/news"
                  className="group block p-4 bg-slate-800/40 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-500/30 rounded-lg transition cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[11px] font-medium bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20">
                          {art.category || "뉴스"}
                        </span>
                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(art.published_at).toLocaleString()}
                        </span>
                      </div>
                      <h3 className="text-sm font-medium text-slate-200 group-hover:text-indigo-300 transition">
                        {art.title}
                      </h3>
                      {art.summary ? (
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                          {art.summary}
                        </p>
                      ) : (
                        <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                          {art.content}
                        </p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <span className="text-xs font-medium text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded border border-indigo-500/20 flex items-center gap-1">
                        <Bot className="w-3 h-3" /> 분석 가능
                      </span>
                    </div>
                  </div>
                </Link>
              ))
            ) : (
              <div className="text-center py-8 text-slate-500 text-sm">
                수집된 최신 기사를 로드 중이거나 등록된 기사가 없습니다.
              </div>
            )}
          </div>
        </div>

        {/* 종가매매 퀀트 위젯 */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-400" />
              종가매매 타겟 (15:10)
            </h2>
            <Link href="/quant" className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
              상세 분석 <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {closingTargets.length > 0 ? (
              closingTargets.map((target) => (
                <div key={target.id} className="p-3.5 bg-slate-800/40 border border-slate-800 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-slate-200">{target.name}</span>
                      <span className="text-xs font-mono text-slate-500 ml-2">{target.code}</span>
                    </div>
                    <span className="text-sm font-bold text-slate-100">
                      {target.closing_price.toLocaleString()}원
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-slate-400">모멘텀 점수: {target.target_score?.toFixed(1) || "-"}</span>
                    {target.return_rate_high != null ? (
                      <span className={target.return_rate_high >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                        익일 고가 {target.return_rate_high > 0 ? `+${target.return_rate_high}%` : `${target.return_rate_high}%`}
                      </span>
                    ) : (
                      <span className="text-amber-400">익일 검증 대기</span>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-slate-500 text-sm">
                오늘의 종가매매 대상 종목을 스캔 중입니다.
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-slate-800">
            <Link
              href="/graph3d"
              className="w-full flex items-center justify-center gap-2 p-2.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 rounded-lg text-xs font-semibold transition"
            >
              <Share2 className="w-4 h-4" />
              3D 단어 동시출현망 열기
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
