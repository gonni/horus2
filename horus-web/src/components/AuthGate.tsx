"use client";

import { useEffect, useState, FormEvent } from "react";
import { Lock, KeyRound, ShieldAlert, ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { AUTH_STORAGE_KEY } from "@/lib/api";

const ACCESS_PASSWORD = process.env.NEXT_PUBLIC_ACCESS_PASSWORD || "Being20##";

export function AuthGate() {
  const [mounted, setMounted] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [shake, setShake] = useState(false);

  useEffect(() => {
    try {
      const savedAuth = localStorage.getItem(AUTH_STORAGE_KEY);
      if (savedAuth === "granted") {
        setIsAuthenticated(true);
      }
    } catch {
      // ignore storage errors
    }
    setMounted(true);
  }, []);

  // 인증되지 않은 경우 백그라운드 스크롤 방지
  useEffect(() => {
    if (mounted && !isAuthenticated) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mounted, isAuthenticated]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!password) {
      setError("비밀번호를 입력해주세요.");
      return;
    }

    if (password === ACCESS_PASSWORD) {
      try {
        localStorage.setItem(AUTH_STORAGE_KEY, "granted");
      } catch (err) {
        console.error("Storage error:", err);
      }
      setError("");
      setIsAuthenticated(true);
      window.location.reload();
    } else {
      setError("비밀번호가 올바르지 않습니다. 다시 확인해주세요.");
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
  };

  // 마운트 전(서버 SSR 및 초기 하이드레이션) 또는 인증 완료 시에는 아무것도 렌더링하지 않음
  if (!mounted || isAuthenticated) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[99999] bg-slate-950/98 backdrop-blur-2xl flex items-center justify-center p-4">
      <div
        className={`w-full max-w-md bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl space-y-6 transition-transform ${
          shake ? "animate-shake ring-2 ring-rose-500/50" : ""
        }`}
      >
        {/* 헤더 및 아이콘 */}
        <div className="text-center space-y-3">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner">
            <Lock className="w-7 h-7 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Horus 2.0 시스템 접근 제한
            </h2>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
              현재 시스템 보호 및 GPU 부하 관리를 위해 접근이 제한되어 있습니다. 시스템 인증 비밀번호를 입력해주세요.
            </p>
          </div>
        </div>

        {/* 패스워드 입력 폼 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5 text-indigo-400" />
              접근 비밀번호 (Password)
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError("");
                }}
                placeholder="비밀번호를 입력하세요"
                autoFocus
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-3 text-slate-400 hover:text-slate-200 transition"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-xs">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 cursor-pointer"
          >
            <span>인증 및 서비스 접속</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* 하단 보안 뱃지 */}
        <div className="pt-2 border-t border-slate-800/80 text-center">
          <div className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
            <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
            <span>Horus Intelligence Secure Gate</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function logoutAuth() {
  try {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    window.location.reload();
  } catch (err) {
    console.error("Logout error:", err);
  }
}
