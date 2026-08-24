"use client";

import { useEffect, useState, useCallback } from "react";
import { api, Article } from "@/lib/api";
import { Search, X, ExternalLink, Bot, RefreshCw, Clock, Newspaper } from "lucide-react";

export default function NewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const fetchArticles = useCallback(async (keyword?: string, category?: string) => {
    setLoading(true);
    try {
      let url = "/articles?page_size=40";
      const cat = category !== undefined ? category : selectedCategory;
      const kw = keyword !== undefined ? keyword : searchQuery;

      if (kw && kw.trim().length >= 2) {
        url = `/articles/search?keyword=${encodeURIComponent(kw.trim())}`;
      } else if (cat && cat !== "all") {
        url = `/articles?page_size=40&category=${encodeURIComponent(cat)}`;
      }

      const res = await api.get(url);
      const items = Array.isArray(res.data?.items) ? res.data.items : (Array.isArray(res.data) ? res.data : []);
      setArticles(items);
    } catch (e) {
      console.error("Fetch articles failed:", e);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, searchQuery]);

  // Initial load
  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  // Real-time auto-refresh interval (every 6 seconds if active and no search)
  useEffect(() => {
    if (!autoRefresh || searchQuery.trim().length >= 2 || selectedArticle) return;
    const interval = setInterval(() => {
      fetchArticles();
    }, 6000);
    return () => clearInterval(interval);
  }, [autoRefresh, searchQuery, selectedArticle, fetchArticles]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchArticles(searchQuery, selectedCategory);
  };

  const handleCategoryChange = (cat: string) => {
    setSelectedCategory(cat);
    setSearchQuery("");
    fetchArticles("", cat);
  };

  const handleAnalyzeArticle = async (art: Article) => {
    setSelectedArticle(art);
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisError(null);

    try {
      const res = await api.post(`/llm/analyze-article/${art.id}`);
      setAnalysisResult(res.data);
    } catch (e: any) {
      console.error("AI Analysis failed:", e);
      setAnalysisError(e?.response?.data?.detail || e?.message || "Ollama gemma4:e4b 모델 연결 또는 분석 중 오류가 발생했습니다.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 상단 헤더 및 검색 바 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Newspaper className="w-6 h-6 text-indigo-400" />
            뉴스 인텔리전스
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            PostgreSQL Trigram 전문검색 및 Ollama gemma4:e4b 실시간 기사 분석 피드
          </p>
        </div>

        {/* 검색 및 새로고침 컨트롤 */}
        <div className="flex items-center gap-2">
          <form onSubmit={handleSearch} className="flex gap-2 w-full sm:w-auto">
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="제목/본문 검색 (2자 이상)..."
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition shrink-0"
            >
              검색
            </button>
          </form>

          <button
            onClick={() => fetchArticles()}
            disabled={loading}
            title="기사 목록 새로고침"
            className="p-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shrink-0"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-indigo-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* 카테고리 필터 탭 & 상태 바 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
          {[
            { id: "all", label: "전체 기사" },
            { id: "news", label: "주요 뉴스" },
            { id: "smart_collect", label: "스마트 수집" },
            { id: "community", label: "커뮤니티" },
            { id: "stock", label: "증시/금융" }
          ].map((c) => (
            <button
              key={c.id}
              onClick={() => handleCategoryChange(c.id)}
              className={`px-3 py-1.5 rounded-lg border transition ${
                selectedCategory === c.id
                  ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40 shadow-sm"
                  : "bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>총 <strong>{articles.length}</strong>건 표시 중</span>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-2.5 py-1 rounded-md border text-[11px] font-semibold transition ${
              autoRefresh
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-slate-800 text-slate-400 border-slate-700"
            }`}
          >
            {autoRefresh ? "● 실시간 갱신 On" : "○ 자동갱신 일시정지"}
          </button>
        </div>
      </div>

      {/* 기사 목록 그리드 */}
      {loading && articles.length === 0 ? (
        <div className="py-24 text-center space-y-3">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-sm text-slate-400">수집된 기사를 불러오는 중입니다...</p>
        </div>
      ) : articles.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {articles.map((art) => (
            <div
              key={art.id}
              className="p-5 bg-slate-900/50 border border-slate-800 hover:border-slate-700 rounded-xl space-y-3 transition flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                  <span className="bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20 font-medium">
                    {art.category || "뉴스"}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {art.published_at ? new Date(art.published_at).toLocaleString() : "방금 전"}
                  </span>
                </div>
                <h2 className="text-base font-semibold text-slate-100 line-clamp-2 hover:text-indigo-400 transition cursor-pointer">
                  {art.title}
                </h2>
                <p className="text-xs text-slate-400 line-clamp-3 mt-2 leading-relaxed">
                  {art.summary || art.content}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                <a
                  href={art.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1"
                >
                  원문 링크 <ExternalLink className="w-3 h-3" />
                </a>
                <button
                  onClick={() => handleAnalyzeArticle(art)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 rounded-md text-xs font-semibold transition"
                >
                  <Bot className="w-3.5 h-3.5" />
                  AI 스마트 분석
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center space-y-4 shadow-sm">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto border border-indigo-500/20">
            <Newspaper className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">수집된 기사가 없습니다</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto leading-relaxed">
              현재 크롤러 데몬 또는 스마트 수집기를 통해 새로운 기사를 수집 중입니다.
              기사가 수집되면 자동으로 실시간 갱신되어 표시됩니다.
            </p>
          </div>
          <div className="flex items-center justify-center pt-2">
            <button
              onClick={() => fetchArticles()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition shadow-md shadow-indigo-600/20"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              지금 새로고침
            </button>
          </div>
        </div>
      )}

      {/* AI 분석 모달 */}
      {selectedArticle && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl relative">
            <button
              onClick={() => setSelectedArticle(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2 text-indigo-400 text-sm font-semibold">
              <Bot className="w-4 h-4" />
              Ollama 자연어 분석 리포트 (gemma4:e4b)
            </div>

            <h3 className="text-lg font-bold text-white">{selectedArticle.title}</h3>

            {analyzing ? (
              <div className="py-12 text-center space-y-2">
                <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                <p className="text-xs text-slate-400">gemma4:e4b가 기사 본문을 심층 분석하고 있습니다...</p>
              </div>
            ) : analysisResult ? (
              <div className="space-y-4 text-sm">
                <div className="bg-slate-800/60 p-4 rounded-xl space-y-1">
                  <span className="text-xs font-bold text-indigo-400">3줄 핵심 요약</span>
                  <p className="text-slate-300 leading-relaxed whitespace-pre-line">{analysisResult.summary}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg">
                    <span className="text-slate-400">감성 스코어</span>
                    <div className="text-base font-bold text-emerald-400 mt-1">
                      {analysisResult.sentiment_label} ({analysisResult.sentiment_score})
                    </div>
                  </div>
                  <div className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg">
                    <span className="text-slate-400">관련 주식/종목</span>
                    <div className="text-base font-bold text-amber-400 mt-1">
                      {analysisResult.related_stocks?.join(", ") || "해당 없음"}
                    </div>
                  </div>
                </div>

                {analysisResult.key_topics?.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-400 block mb-2">주요 토픽 키워드</span>
                    <div className="flex flex-wrap gap-1.5">
                      {analysisResult.key_topics.map((t: string, i: number) => (
                        <span key={i} className="text-xs bg-slate-800 text-slate-300 px-2.5 py-1 rounded-full border border-slate-700">
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : analysisError ? (
              <div className="p-5 bg-rose-500/10 border border-rose-500/30 rounded-xl space-y-3 text-center">
                <p className="text-xs text-rose-300 font-medium">{analysisError}</p>
                <button
                  onClick={() => selectedArticle && handleAnalyzeArticle(selectedArticle)}
                  className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg transition"
                >
                  분석 다시 시도
                </button>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
