"use client";

import { useEffect, useState, useCallback } from "react";
import { api, Article, LLMModelsResponse, ArticleAnalysisResponse, LLMModelOption } from "@/lib/api";
import { 
  Search, 
  X, 
  ExternalLink, 
  Bot, 
  RefreshCw, 
  Clock, 
  Newspaper, 
  Sparkles, 
  Server, 
  Cpu, 
  CheckCircle2, 
  AlertCircle,
  Zap,
  TrendingUp,
  Tag
} from "lucide-react";

export default function NewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // LLM Models State
  const [modelsData, setModelsData] = useState<LLMModelsResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("auto");
  const [modelsLoading, setModelsLoading] = useState(false);

  // AI Modal State
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ArticleAnalysisResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [modalSelectedModel, setModalSelectedModel] = useState<string>("auto");

  // Fetch available LLM models
  const fetchModels = useCallback(async () => {
    setModelsLoading(true);
    try {
      const res = await api.get("/llm/models");
      setModelsData(res.data);
      if (res.data?.default_model && !selectedModel) {
        setSelectedModel(res.data.default_model);
      }
    } catch (e) {
      console.error("Fetch LLM models failed:", e);
    } finally {
      setModelsLoading(false);
    }
  }, [selectedModel]);

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
    fetchModels();
  }, [fetchArticles, fetchModels]);

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

  const handleAnalyzeArticle = async (art: Article, overrideModel?: string) => {
    const targetModel = overrideModel || selectedModel || "auto";
    setSelectedArticle(art);
    setModalSelectedModel(targetModel);
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisError(null);

    try {
      const res = await api.post(`/llm/analyze-article/${art.id}?model=${encodeURIComponent(targetModel)}`);
      setAnalysisResult(res.data);
    } catch (e: any) {
      console.error("AI Analysis failed:", e);
      setAnalysisError(
        e?.response?.data?.detail || 
        e?.message || 
        "LLM 모델 연결 또는 분석 중 오류가 발생했습니다."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 상단 헤더 및 검색/모델 컨트롤 */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Newspaper className="w-6 h-6 text-indigo-400" />
            뉴스 인텔리전스
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            PostgreSQL 실시간 기사 피드 & Hybrid LLM (GPU2 vLLM + Ollama MLX) 자연어 분석
          </p>
        </div>

        {/* 모델 선택기 및 검색 컨트롤 */}
        <div className="flex flex-wrap items-center gap-3">
          {/* LLM 모델 셀렉터 */}
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 shadow-sm">
            <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden sm:inline text-slate-400">분석 모델:</span>
            </div>
            
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-slate-800 text-slate-100 text-xs rounded border border-slate-700 px-2.5 py-1 focus:outline-none focus:border-indigo-500 cursor-pointer max-w-[220px] sm:max-w-xs font-medium"
            >
              <option value="auto">
                ⚡ Auto (GPU2 우선 → Ollama 자동 폴백)
              </option>
              
              {modelsData?.options
                ?.filter((m) => m.id !== "auto")
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.provider === "gpu2" ? "🚀 [GPU2] " : "🖥️ [Local] "}
                    {m.name}
                  </option>
                ))}
            </select>

            {/* 서버 상태 인디케이터 */}
            <div className="flex items-center gap-1.5 pl-1.5 border-l border-slate-700 text-[11px]">
              <span 
                title={modelsData?.gpu2_available ? "GPU2 vLLM 활성화" : "GPU2 vLLM 비활성화"}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  modelsData?.gpu2_available 
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                    : "bg-slate-800 text-slate-500"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${modelsData?.gpu2_available ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`}></span>
                GPU2
              </span>

              <span 
                title={modelsData?.ollama_available ? "Local Ollama 활성화" : "Local Ollama 비활성화"}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  modelsData?.ollama_available 
                    ? "bg-sky-500/10 text-sky-400 border border-sky-500/20" 
                    : "bg-slate-800 text-slate-500"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${modelsData?.ollama_available ? "bg-sky-400" : "bg-slate-600"}`}></span>
                Ollama
              </span>
            </div>
          </div>

          {/* 검색 폼 */}
          <form onSubmit={handleSearch} className="flex gap-2 w-full sm:w-auto">
            <div className="relative w-full sm:w-60">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="제목/본문 검색..."
                className="w-full pl-9 pr-4 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition shrink-0"
            >
              검색
            </button>
          </form>

          <button
            onClick={() => {
              fetchArticles();
              fetchModels();
            }}
            disabled={loading || modelsLoading}
            title="기사 및 모델 상태 새로고침"
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading || modelsLoading ? "animate-spin text-indigo-400" : ""}`} />
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
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl relative">
            <button
              onClick={() => setSelectedArticle(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>

            {/* 모달 상단 헤더 & 모델 변경 컨트롤 */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3 pr-8">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    AI 자연어 심층 분석 리포트
                  </h4>
                  <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                    <span>구동 엔진:</span>
                    {analysisResult ? (
                      <span className="font-semibold text-indigo-300">
                        {analysisResult.provider_used === "gpu2" ? "🚀 GPU2 vLLM" : "🖥️ Local Ollama"} ({analysisResult.model_used})
                        {analysisResult.fallback_used && (
                          <span className="text-amber-400 ml-1.5 font-normal">(Ollama 자동 폴백됨)</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-slate-300">{modalSelectedModel === "auto" ? "⚡ Auto (GPU2 우선)" : modalSelectedModel}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* 모달 내 빠른 모델 변경 및 재분석 */}
              <div className="flex items-center gap-1.5 pt-1 sm:pt-0">
                <select
                  value={modalSelectedModel}
                  onChange={(e) => {
                    const newModel = e.target.value;
                    setModalSelectedModel(newModel);
                    if (selectedArticle) {
                      handleAnalyzeArticle(selectedArticle, newModel);
                    }
                  }}
                  disabled={analyzing}
                  className="bg-slate-800 text-slate-200 text-xs rounded border border-slate-700 px-2 py-1 focus:outline-none focus:border-indigo-500"
                >
                  <option value="auto">⚡ Auto (GPU2 우선)</option>
                  {modelsData?.options
                    ?.filter((m) => m.id !== "auto")
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.provider === "gpu2" ? "[GPU2] " : "[Ollama] "}
                        {m.name}
                      </option>
                    ))}
                </select>
                <button
                  onClick={() => selectedArticle && handleAnalyzeArticle(selectedArticle, modalSelectedModel)}
                  disabled={analyzing}
                  title="선택한 모델로 재분석"
                  className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded transition shrink-0"
                >
                  재분석
                </button>
              </div>
            </div>

            {/* 기사 제목 */}
            <h3 className="text-base font-bold text-white leading-snug">{selectedArticle.title}</h3>

            {/* 분석 중 로딩 */}
            {analyzing ? (
              <div className="py-14 text-center space-y-3 bg-slate-950/40 rounded-xl border border-slate-800/80">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-slate-200">
                    {modalSelectedModel.includes("gpu2") || modalSelectedModel === "auto" 
                      ? "GPU2 vLLM 및 AI 모델이 기사 본문을 심층 분석하고 있습니다..." 
                      : "Local Ollama가 기사를 분석하고 있습니다..."}
                  </p>
                  <p className="text-xs text-slate-400">
                    3줄 핵심 요약, 감성 지표, 토픽 및 관련 종목을 실시간 추출합니다.
                  </p>
                </div>
              </div>
            ) : analysisResult ? (
              <div className="space-y-4 text-sm">
                {/* 3줄 핵심 요약 */}
                <div className="bg-slate-800/60 border border-slate-700/60 p-4 rounded-xl space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-400">
                    <Sparkles className="w-3.5 h-3.5" />
                    3줄 핵심 요약
                  </div>
                  <p className="text-slate-200 leading-relaxed whitespace-pre-line text-xs sm:text-sm">
                    {analysisResult.summary}
                  </p>
                </div>

                {/* 감성 점수 & 관련 주식 종목 */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-3.5 bg-slate-800/40 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-slate-400 text-xs flex items-center gap-1">
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> 감성 지수 (Sentiment)
                    </span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-base font-bold ${
                        analysisResult.sentiment_score > 0.2 
                          ? "text-emerald-400" 
                          : analysisResult.sentiment_score < -0.2 
                          ? "text-rose-400" 
                          : "text-amber-400"
                      }`}>
                        {analysisResult.sentiment_label}
                      </span>
                      <span className="text-xs text-slate-400">
                        ({analysisResult.sentiment_score > 0 ? `+${analysisResult.sentiment_score.toFixed(2)}` : analysisResult.sentiment_score.toFixed(2)})
                      </span>
                    </div>
                  </div>

                  <div className="p-3.5 bg-slate-800/40 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-slate-400 text-xs flex items-center gap-1">
                      <Tag className="w-3.5 h-3.5 text-amber-400" /> 관련 주식 / 종목 코드
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {analysisResult.related_stocks && analysisResult.related_stocks.length > 0 ? (
                        analysisResult.related_stocks.map((st, i) => (
                          <span key={i} className="px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded font-mono text-xs font-semibold">
                            {st}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-400 text-xs">관련 종목 없음</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 주요 토픽 및 엔티티 태그 */}
                {analysisResult.key_topics?.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-400 block mb-2 font-medium">주요 키워드 / 토픽</span>
                    <div className="flex flex-wrap gap-1.5">
                      {analysisResult.key_topics.map((t: string, i: number) => (
                        <span key={i} className="text-xs bg-slate-800/90 text-slate-300 px-2.5 py-1 rounded-full border border-slate-700 flex items-center gap-1">
                          #{t}
                        </span>
                      ))}
                      {analysisResult.entities?.map((e: string, i: number) => (
                        <span key={`ent-${i}`} className="text-xs bg-indigo-950/50 text-indigo-300 px-2.5 py-1 rounded-full border border-indigo-800/50">
                          @{e}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : analysisError ? (
              <div className="p-5 bg-rose-500/10 border border-rose-500/30 rounded-xl space-y-3 text-center">
                <div className="flex items-center justify-center gap-2 text-rose-400 font-semibold text-sm">
                  <AlertCircle className="w-4 h-4" />
                  분석 처리 실패
                </div>
                <p className="text-xs text-rose-300 leading-relaxed">{analysisError}</p>
                <div className="flex items-center justify-center gap-2 pt-2">
                  <button
                    onClick={() => selectedArticle && handleAnalyzeArticle(selectedArticle, "auto")}
                    className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg transition"
                  >
                    Auto 모드로 다시 시도
                  </button>
                  <button
                    onClick={() => selectedArticle && handleAnalyzeArticle(selectedArticle, "ollama:gemma4:e4b-mlx")}
                    className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
                  >
                    Local Ollama로 시도
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
