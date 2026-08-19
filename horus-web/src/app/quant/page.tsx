"use client";

import { useEffect, useState } from "react";
import { api, StockClosingTarget, QuantStats } from "@/lib/api";
import { TrendingUp, CheckCircle2, AlertCircle, Clock, Calendar, BarChart3 } from "lucide-react";

export default function QuantPage() {
  const [targets, setTargets] = useState<StockClosingTarget[]>([]);
  const [stats, setStats] = useState<QuantStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadQuantData() {
      try {
        const [targetsRes, statsRes] = await Promise.all([
          api.get("/stock/closing-targets?limit=50"),
          api.get("/stock/quant-stats")
        ]);
        setTargets(targetsRes.data);
        setStats(statsRes.data);
      } catch (e) {
        console.error("Failed to load quant data:", e);
      } finally {
        setLoading(false);
      }
    }
    loadQuantData();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-emerald-400" />
          종가매매 퀀트 인텔리전스 (BrainStocking 2.0)
        </h1>
        <p className="text-sm text-slate-400">
          매일 15:10 거래대금/모멘텀 기반 자동 추출 및 익일 09:10 시초가/10분 고가 성과 자동 검증
        </p>
      </div>

      {/* 성과 통계 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">총 추천 건수</span>
          <div className="text-2xl font-bold text-white mt-1">
            {stats?.total_trades || 0}건
          </div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">검증 성공 승률</span>
          <div className="text-2xl font-bold text-emerald-400 mt-1">
            {stats ? `${stats.win_rate}%` : "0%"}
          </div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">익일 시초가 평균 수익률</span>
          <div className="text-2xl font-bold text-indigo-400 mt-1">
            {stats ? `${stats.avg_return_rate_open > 0 ? "+" : ""}${stats.avg_return_rate_open}%` : "0%"}
          </div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">익일 10분 고가 평균 수익률</span>
          <div className="text-2xl font-bold text-amber-400 mt-1">
            {stats ? `${stats.avg_return_rate_high > 0 ? "+" : ""}${stats.avg_return_rate_high}%` : "0%"}
          </div>
        </div>
      </div>

      {/* 타겟 종목 테이블 */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-semibold text-white flex items-center gap-2 text-sm">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            추출 종목 및 익일 성과 검증 내역
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/60 text-slate-400 uppercase font-medium">
              <tr>
                <th className="py-3 px-4">추출일자</th>
                <th className="py-3 px-4">종목명 / 코드</th>
                <th className="py-3 px-4">전략명</th>
                <th className="py-3 px-4 text-right">종가</th>
                <th className="py-3 px-4 text-right">익일 시초가</th>
                <th className="py-3 px-4 text-right">익일 고가(10m)</th>
                <th className="py-3 px-4 text-right">고가 수익률</th>
                <th className="py-3 px-4 text-center">검증 결과</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {targets.map((row) => (
                <tr key={row.id} className="hover:bg-slate-800/40 transition">
                  <td className="py-3 px-4 font-mono text-slate-400">{row.target_dt}</td>
                  <td className="py-3 px-4">
                    <span className="font-semibold text-white">{row.name}</span>
                    <span className="text-slate-500 font-mono ml-2">({row.code})</span>
                  </td>
                  <td className="py-3 px-4 text-indigo-400 font-mono">{row.strategy_name}</td>
                  <td className="py-3 px-4 text-right font-medium">{row.closing_price.toLocaleString()}원</td>
                  <td className="py-3 px-4 text-right font-mono text-slate-400">
                    {row.next_day_open ? `${row.next_day_open.toLocaleString()}원` : "-"}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-slate-400">
                    {row.next_day_10m_high ? `${row.next_day_10m_high.toLocaleString()}원` : "-"}
                  </td>
                  <td className="py-3 px-4 text-right font-bold font-mono">
                    {row.return_rate_high != null ? (
                      <span className={row.return_rate_high >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {row.return_rate_high > 0 ? `+${row.return_rate_high}%` : `${row.return_rate_high}%`}
                      </span>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {row.is_success === true && (
                      <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        <CheckCircle2 className="w-3 h-3" /> 성공
                      </span>
                    )}
                    {row.is_success === false && (
                      <span className="inline-flex items-center gap-1 text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                        <AlertCircle className="w-3 h-3" /> 실패
                      </span>
                    )}
                    {row.is_success === null && (
                      <span className="inline-flex items-center gap-1 text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                        <Clock className="w-3 h-3" /> 대기
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
