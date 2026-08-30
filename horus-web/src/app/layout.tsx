import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { AuthGate } from "@/components/AuthGate";

export const metadata: Metadata = {
  title: "Horus 2.0 - Next-Gen AI Data Intelligence Platform",
  description: "Real-time News Intelligence, Knowledge Graph, and Quant Trading",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
        <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
          © 2026 Horus Intelligence System. Built with Next.js 15, FastAPI, PostgreSQL TimescaleDB, and Neo4j.
        </footer>
        <AuthGate />
      </body>
    </html>
  );
}
