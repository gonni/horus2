"use client";

import { useEffect, useState } from "react";
import { api, Article } from "@/lib/api";
import { Search, Sparkles, X, ExternalLink, Bot, ArrowRight } from "lucide-react";

export default function NewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    fetchArticles();
  }, []);

  async function fetchArticles(keyword?: string) {
    setLoading(true);
    try {
      if (keyword && keyword.trim().length >= 2) {
        const res = await api.get(`/articles/search?keyword=${encodeURIComponent(keyword)}`);
        setArticles(res.data.items);
      } else {
        const res = await api.get("/articles?page_size=30");
        setArticles(res.data.items);
      }
    } catch (e) {
      console.error("Fetch articles failed:", e);
    } finally {
      setLoading(false);
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchArticles(searchQuery);
  };

  const handleAnalyzeArticle = async (art: Article) => {
    setSelectedArticle(art);
    setAnalyzing(true);
    setAnalysisResult(null);

    try {
      const res = await api.post(`/llm/analyze-article/${art.id}`);
      setAnalysisResult(res.data);
    } catch (e) {
      console.error("AI Analysis failed:", e);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">뉴스 인텔리전스</h1>
          <p className="text-sm text-slate-400">PostgreSQL Trigram 전문검색 및 Hybrid LLM 실시간 기사 분석</p>
        </div>

        {/* 검색창 */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="제목/본문 Trigram 검색..."
              className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition"
          >
            검색
          </button>
        </form>
      </div>

      {/* 기사 목록 그리드 */}
      {loading ? (
        <div className="text-center py-20 text-slate-400">기사를 검색 중입니다...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {articles.map((art) => (
            <div
              key={art.id}
              className="p-5 bg-slate-900/50 border border-slate-800 hover:border-slate-700 rounded-xl space-y-3 transition flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
                  <span className="bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
                    {art.category || "뉴스"}
                  </span>
                  <span>{new Date(art.published_at).toLocaleString()}</span>
                </div>
                <h2 className="text-base font-semibold text-slate-100 line-clamp-2 hover:text-indigo-400 cursor-pointer">
                  {art.title}
                </h2>
                <p className="text-xs text-slate-400 line-clamp-3 mt-2">
                  {art.content}
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
      )}

      {/* AI 분석 모달 */}
      {selectedArticle && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl relative">
            <button
              onClick={() => setSelectedArticle(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2 text-indigo-400 text-sm font-semibold">
              <Bot className="w-4 h-4" />
              Hybrid LLM 분석 리포트 (Qwen + Gemini)
            </div>

            <h3 className="text-lg font-bold text-white">{selectedArticle.title}</h3>

            {analyzing ? (
              <div className="py-12 text-center space-y-2">
                <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                <p className="text-xs text-slate-400">LLM이 기사 본문을 심층 분석하고 있습니다...</p>
              </div>
            ) : analysisResult ? (
              <div className="space-y-4 text-sm">
                <div className="bg-slate-800/60 p-4 rounded-xl space-y-1">
                  <span className="text-xs font-bold text-indigo-400">3줄 핵심 요약</span>
                  <p className="text-slate-300 leading-relaxed">{analysisResult.summary}</p>
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
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
