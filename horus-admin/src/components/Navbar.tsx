"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  ShieldCheck,
  Sparkles,
  Settings2,
  Activity,
  ExternalLink
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { href: "/monitor", label: "실시간 수집 모니터링", icon: Activity },
    { href: "/smart-crawl", label: "지능형 5대 수집 허브", icon: Sparkles },
    { href: "/crawl-admin", label: "시드 크롤러 & 작업 관리", icon: Settings2 },
  ];

  return (
    <nav className="border-b border-slate-800 bg-slate-950 sticky top-0 z-50 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Admin Branding */}
          <Link href="/monitor" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-rose-600 flex items-center justify-center font-bold text-white shadow-lg shadow-rose-500/30">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl tracking-tight text-white flex items-center gap-2">
              Horus <span className="text-xs bg-rose-500/20 text-rose-400 px-2.5 py-0.5 rounded-full border border-rose-500/30 font-mono">ADMIN CONSOLE</span>
            </span>
          </Link>

          {/* Admin Navigation */}
          <div className="flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href === "/monitor" && pathname === "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-slate-800 text-rose-400 border border-slate-700 shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>


          {/* Quick External Link to End-User Service UI */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
              <Activity className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
              Core Engine Online (:8000)
            </div>
            <a
              href="http://localhost:3000"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/30 border border-indigo-500/30 transition"
            >
              <span>서비스 UI 열기 (:3000)</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    </nav>
  );
}

