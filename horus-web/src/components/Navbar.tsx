"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Newspaper, 
  Share2, 
  TrendingUp, 
  Bot,
  Zap,
  Lock
} from "lucide-react";
import { api, LLMModelsResponse } from "@/lib/api";
import { logoutAuth } from "@/components/AuthGate";

export function Navbar() {
  const pathname = usePathname();
  const [llmStatus, setLlmStatus] = useState<LLMModelsResponse | null>(null);

  useEffect(() => {
    async function loadLlmStatus() {
      try {
        const res = await api.get("/llm/models");
        setLlmStatus(res.data);
      } catch (e) {
        // silent fallback
      }
    }
    loadLlmStatus();
  }, []);

  const navItems = [
    { href: "/", label: "대시보드", icon: LayoutDashboard },
    { href: "/news", label: "뉴스 인텔리전스", icon: Newspaper },
    { href: "/graph3d", label: "3D 단어/토픽망", icon: Share2 },
    { href: "/quant", label: "종가매매 퀀트", icon: TrendingUp },
  ];

  const hasGpu2 = llmStatus?.gpu2_available ?? true;
  const hasOllama = llmStatus?.ollama_available ?? true;

  return (
    <nav className="border-b border-slate-800 bg-slate-900/95 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
              H
            </div>
            <span className="font-bold text-xl tracking-tight text-white flex items-center gap-2">
              Horus <span className="text-xs bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-500/30">2.0 AI</span>
            </span>
          </div>

          <div className="flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-slate-800 text-indigo-400 border border-slate-700 shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs bg-slate-800/80 px-3 py-1 rounded-full border border-slate-700">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <div className="flex items-center gap-1.5 font-medium">
                <span className="text-slate-300">AI:</span>
                {hasGpu2 ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    GPU2 Qwen3.8
                  </span>
                ) : hasOllama ? (
                  <span className="text-sky-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
                    Local Ollama
                  </span>
                ) : (
                  <span className="text-slate-400">대기 중</span>
                )}
                {hasGpu2 && hasOllama && (
                  <span className="text-[10px] text-slate-500 font-mono">+Ollama</span>
                )}
              </div>
            </div>

            <button
              onClick={() => logoutAuth()}
              title="보안 잠금 (로그아웃)"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/80 rounded-lg border border-transparent hover:border-slate-700 transition flex items-center gap-1 text-xs cursor-pointer"
            >
              <Lock className="w-3.5 h-3.5" />
              <span className="hidden sm:inline text-[11px]">잠금</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
