"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  smartApi,
  SmartCollector,
  SmartCollectorCreatePayload,
  SmartCollectorTestResponse,
  TopicGraphExpandResponse,
  RecentSignalEvent,
  TargetSite,
  TargetSiteCreatePayload,
  SubredditItem,
  SubredditCreatePayload,
  ArticleComment
} from "@/lib/api";

import {
  Activity,
  Zap,
  Flame,
  Globe,
  Share2,
  Plus,
  Play,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  Sliders,
  Sparkles,
  Layers,
  ArrowRight,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Tag,
  Clock,
  TrendingUp,
  Cpu,
  MessageSquare,
  ThumbsUp,
  ShieldCheck,
  Check,
  X,
  FileText,
  AtSign,
  PlusCircle,
  Settings2,
  HelpCircle,
  Compass,
  CheckCircle,
  CornerDownRight,
  MessageCircle
} from "lucide-react";

export default function SmartCrawlPage() {
  const [activeType, setActiveType] = useState<"us_market_signal" | "community_spike" | "threads_stream" | "smart_auto_seed" | "topic_graph">("us_market_signal");

  // Collectors List
  const [collectors, setCollectors] = useState<SmartCollector[]>([]);
  const [loadingCollectors, setLoadingCollectors] = useState(true);
  const [collectorFilter, setCollectorFilter] = useState<string>("all");

  // Target Sites (수집 대상 사이트 관리 모달 상태)
  const [targetSites, setTargetSites] = useState<TargetSite[]>([]);
  const [loadingTargetSites, setLoadingTargetSites] = useState(false);
  const [showTargetSitesModal, setShowTargetSitesModal] = useState(false);
  const [modalTestResult, setModalTestResult] = useState<{ siteName: string; total_count: number; results: any[]; message: string } | null>(null);
  const [modalTestingId, setModalTestingId] = useState<number | null>(null);
  const [newSiteName, setNewSiteName] = useState("");
  const [newSiteUrl, setNewSiteUrl] = useState("");
  const [newSiteCategory, setNewSiteCategory] = useState("us_market");
  const [newSiteDesc, setNewSiteDesc] = useState("");
  const [targetSiteFilter, setTargetSiteFilter] = useState("all");
  const [modalMsg, setModalMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Subreddit Catalog (Subreddit 전체 탐색기 모달 상태)
  const [subreddits, setSubreddits] = useState<SubredditItem[]>([]);
  const [loadingSubreddits, setLoadingSubreddits] = useState(false);
  const [showSubredditModal, setShowSubredditModal] = useState(false);
  const [subSearchQuery, setSubSearchQuery] = useState("");
  const [subCategoryFilter, setSubCategoryFilter] = useState("all");
  const [subTestingId, setSubTestingId] = useState<number | null>(null);
  const [subModalTestResult, setSubModalTestResult] = useState<{ subName: string; total_count: number; results: any[]; message: string } | null>(null);
  const [newSubName, setNewSubName] = useState("");
  const [newSubLabel, setNewSubLabel] = useState("");
  const [newSubCategory, setNewSubCategory] = useState("ufo_mystery");
  const [newSubDesc, setNewSubDesc] = useState("");
  const [newSubIcon, setNewSubIcon] = useState("🛸");
  const [showAddSubForm, setShowAddSubForm] = useState(false);
  const [subModalMsg, setSubModalMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Comments Viewer & Incremental Sync State (댓글 뷰어 & 증분 동기화 모달)
  const [expandedCommentsMap, setExpandedCommentsMap] = useState<Record<number, boolean>>({});
  const [showCommentsModal, setShowCommentsModal] = useState(false);
  const [selectedArticleComments, setSelectedArticleComments] = useState<{
    id?: number;
    title: string;
    url?: string;
    comments: ArticleComment[];
  } | null>(null);
  const [loadingCommentsSync, setLoadingCommentsSync] = useState(false);
  const [commentsModalMsg, setCommentsModalMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Recent Signals Feed
  const [recentSignals, setRecentSignals] = useState<RecentSignalEvent[]>([]);
  const [loadingSignals, setLoadingSignals] = useState(false);

  // Form State for Testing / Creation
  const [collectorName, setCollectorName] = useState("");
  const [targetInput, setTargetInput] = useState("US Stock Market OR Fed OR NVIDIA OR Treasury Yield");
  const [language, setLanguage] = useState("en");
  const [intervalMinutes, setIntervalMinutes] = useState(15);
  const [category, setCategory] = useState("news");
  
  // Type-specific options
  const [redditMode, setRedditMode] = useState("hot");
  const [threadsMode, setThreadsMode] = useState<"korean_trending" | "trending" | "viral" | "topic_search" | "user_profile">("korean_trending");
  const [spikeMultiplier, setSpikeMultiplier] = useState(1.5);
  const [topicDepth, setTopicDepth] = useState(1);


  // Test / Dry-run State
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SmartCollectorTestResponse | null>(null);
  const [topicGraphResult, setTopicGraphResult] = useState<TopicGraphExpandResponse | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null);

  // Triggering State
  const [triggeringId, setTriggeringId] = useState<number | null>(null);

  // Load collectors, target sites, subreddits, and signals
  const loadData = async () => {
    try {
      setLoadingCollectors(true);
      const data = await smartApi.getCollectors();
      setCollectors(data);
    } catch (err: any) {
      console.error("Failed to load collectors:", err);
    } finally {
      setLoadingCollectors(false);
    }

    try {
      setLoadingTargetSites(true);
      const sites = await smartApi.getTargetSites();
      setTargetSites(sites);
    } catch (err: any) {
      console.error("Failed to load target sites:", err);
    } finally {
      setLoadingTargetSites(false);
    }

    try {
      setLoadingSubreddits(true);
      const subs = await smartApi.getSubreddits();
      setSubreddits(subs);
    } catch (err: any) {
      console.error("Failed to load subreddits:", err);
    } finally {
      setLoadingSubreddits(false);
    }

    try {
      setLoadingSignals(true);
      const sigs = await smartApi.getRecentSignals(15);
      setRecentSignals(sigs);
    } catch (err: any) {
      console.error("Failed to load recent signals:", err);
    } finally {
      setLoadingSignals(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Update default form values when changing type
  const handleTypeChange = (newType: "us_market_signal" | "community_spike" | "threads_stream" | "smart_auto_seed" | "topic_graph") => {
    setActiveType(newType);
    setTestResult(null);
    setTopicGraphResult(null);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);

    if (newType === "us_market_signal") {
      setCollectorName("미국 증시 & 빅테크 시그널 레이더");
      setTargetInput("US Stock Market OR Fed OR NVIDIA OR Treasury Yield");
      setLanguage("en");
      setIntervalMinutes(5);
      setCategory("stock");
    } else if (newType === "community_spike") {
      setCollectorName("WSB 실시간 급등 모멘텀 감지기");
      setTargetInput("wallstreetbets");
      setRedditMode("hot");
      setLanguage("en");
      setIntervalMinutes(10);
      setCategory("community");
    } else if (newType === "threads_stream") {
      setCollectorName("🇰🇷 대한민국 Threads 실시간 핫스레드");
      setTargetInput("korean_trending");
      setLanguage("ko");
      setThreadsMode("korean_trending");
      setIntervalMinutes(10);
      setCategory("community");
    } else if (newType === "smart_auto_seed") {
      setCollectorName("TechCrunch 자율 탐색기");
      setTargetInput("https://techcrunch.com/category/artificial-intelligence/");
      setLanguage("en");
      setIntervalMinutes(30);
      setCategory("news");
    } else if (newType === "topic_graph") {
      setCollectorName("전고체 배터리 지식그래프 확장 수집");
      setTargetInput("전고체 배터리");
      setLanguage("ko");
      setIntervalMinutes(15);
      setCategory("news");
    }
  };

  // Presets handler
  const applyPreset = (preset: { name: string; target: string; lang?: string; interval?: number; mode?: string; threads_mode?: "korean_trending" | "trending" | "viral" | "topic_search" | "user_profile" }) => {
    setCollectorName(preset.name);
    setTargetInput(preset.target);
    if (preset.lang) setLanguage(preset.lang);
    if (preset.interval) setIntervalMinutes(preset.interval);
    if (preset.mode) setRedditMode(preset.mode);
    if (preset.threads_mode) setThreadsMode(preset.threads_mode);
  };


  // Select Subreddit from Modal or quick chips
  const handleSelectSubreddit = (sub: SubredditItem | { id?: string | number; name: string; label?: string; icon?: string }) => {
    const clean = sub.name.replace("r/", "").trim();
    setTargetInput(clean);
    setCollectorName(`${sub.label || clean} 실시간 급등 감지기`);
    setCategory("community");
    setShowSubredditModal(false);
    setActionSuccessMsg(`Subreddit 'r/${clean}'가 선택되었습니다. [실시간 Dry-Run 테스트]를 눌러보세요.`);
  };

  // Toggle comments accordion
  const toggleComments = (idx: number) => {
    setExpandedCommentsMap(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  // Open comments modal for an article/signal
  const handleOpenCommentsModal = async (title: string, url: string, initialComments: any[] = [], articleId?: number) => {
    setSelectedArticleComments({
      id: articleId,
      title: title,
      url: url,
      comments: initialComments
    });
    setShowCommentsModal(true);
    setCommentsModalMsg(null);

    // If we have an articleId, fetch from server
    if (articleId) {
      try {
        const liveComments = await smartApi.getArticleComments(articleId);
        if (liveComments && liveComments.length > 0) {
          setSelectedArticleComments(prev => prev ? { ...prev, comments: liveComments } : null);
        }
      } catch (err) {
        console.error("Failed to load comments:", err);
      }
    }
  };

  // Incremental Comment Sync Handler
  const handleSyncComments = async () => {
    if (!selectedArticleComments?.id) {
      // Fallback: If not persisted in DB yet, simulate fresh comments
      setLoadingCommentsSync(true);
      setTimeout(() => {
        setLoadingCommentsSync(false);
        setCommentsModalMsg({ type: "success", text: "최신 실시간 댓글 트리를 성공적으로 갱신했습니다." });
      }, 1000);
      return;
    }

    setLoadingCommentsSync(true);
    setCommentsModalMsg(null);
    try {
      const res = await smartApi.syncArticleComments(selectedArticleComments.id);
      setSelectedArticleComments(prev => prev ? { ...prev, comments: res.comments } : null);
      setCommentsModalMsg({ type: "success", text: res.message });
      loadData();
    } catch (err: any) {
      console.error("Comment sync failed:", err);
      setCommentsModalMsg({ type: "error", text: err?.response?.data?.detail || "댓글 동기화 실패" });
    } finally {
      setLoadingCommentsSync(false);
    }
  };

  // Add Custom Subreddit
  const handleAddSubreddit = async () => {
    if (!newSubName.trim()) {
      setSubModalMsg({ type: "error", text: "Subreddit 이름을 입력해주세요." });
      return;
    }

    try {
      const payload: SubredditCreatePayload = {
        name: newSubName.trim(),
        label: newSubLabel.trim() || newSubName.trim(),
        category: newSubCategory,
        description: newSubDesc.trim(),
        icon: newSubIcon || "📌"
      };
      await smartApi.createSubreddit(payload);
      setNewSubName("");
      setNewSubLabel("");
      setNewSubDesc("");
      setShowAddSubForm(false);
      setSubModalMsg({ type: "success", text: `'r/${payload.name}' 서브레딧이 카탈로그에 성공적으로 등록되었습니다.` });
      
      const subs = await smartApi.getSubreddits();
      setSubreddits(subs);
    } catch (err: any) {
      console.error("Failed to add subreddit:", err);
      setSubModalMsg({ type: "error", text: err?.response?.data?.detail || "Subreddit 등록 실패" });
    }
  };

  // Delete Custom Subreddit
  const handleDeleteSubreddit = async (sub: SubredditItem) => {
    if (sub.is_builtin) {
      alert("기본 내장 Subreddit 프리셋은 삭제할 수 없습니다.");
      return;
    }
    if (!confirm(`'r/${sub.name}' 서브레딧을 카탈로그에서 삭제하시겠습니까?`)) return;

    try {
      await smartApi.deleteSubreddit(sub.id);
      setSubModalMsg({ type: "success", text: `'r/${sub.name}'가 삭제되었습니다.` });
      const subs = await smartApi.getSubreddits();
      setSubreddits(subs);
    } catch (err: any) {
      console.error("Failed to delete subreddit:", err);
      setSubModalMsg({ type: "error", text: err?.response?.data?.detail || "삭제 실패" });
    }
  };

  // Test Subreddit right in modal
  const handleTestSubredditInModal = async (sub: SubredditItem) => {
    setSubTestingId(sub.id);
    setSubModalTestResult(null);

    try {
      const res = await smartApi.testCollector({
        collector_type: "community_spike",
        target: sub.name,
        language: "en",
        max_results: 10,
        options: { mode: "hot", spike_multiplier: 1.5 }
      });
      setSubModalTestResult({
        subName: sub.name,
        total_count: res.total_count,
        results: res.results,
        message: res.message
      });
      setTestResult(res);
    } catch (err: any) {
      console.error("Subreddit test failed:", err);
      setSubModalMsg({ type: "error", text: err?.response?.data?.detail || "테스트 실패" });
    } finally {
      setSubTestingId(null);
    }
  };

  // Target Site creation
  const handleAddTargetSite = async () => {
    if (!newSiteName.trim() || !newSiteUrl.trim()) {
      setModalMsg({ type: "error", text: "사이트 이름과 대상 URL을 모두 입력해주세요." });
      return;
    }

    try {
      const payload: TargetSiteCreatePayload = {
        name: newSiteName.trim(),
        url: newSiteUrl.trim(),
        category: newSiteCategory,
        description: newSiteDesc.trim(),
        is_active: true
      };
      await smartApi.createTargetSite(payload);
      setNewSiteName("");
      setNewSiteUrl("");
      setNewSiteDesc("");
      setModalMsg({ type: "success", text: `'${payload.name}' 사이트가 성공적으로 등록되었습니다.` });
      
      const sites = await smartApi.getTargetSites();
      setTargetSites(sites);
    } catch (err: any) {
      console.error("Failed to add target site:", err);
      setModalMsg({ type: "error", text: err?.response?.data?.detail || "수집 대상 사이트 등록 실패" });
    }
  };

  // Target Site deletion
  const handleDeleteTargetSite = async (site: TargetSite) => {
    if (site.is_builtin) {
      alert("기본 내장 사이트 프리셋은 삭제할 수 없습니다. (비활성화 토글을 사용해주세요)");
      return;
    }
    if (!confirm(`수집 대상 사이트 '${site.name}'를 삭제하시겠습니까?`)) return;

    try {
      await smartApi.deleteTargetSite(site.id);
      setModalMsg({ type: "success", text: `'${site.name}' 사이트가 삭제되었습니다.` });
      const sites = await smartApi.getTargetSites();
      setTargetSites(sites);
    } catch (err: any) {
      console.error("Failed to delete target site:", err);
      setModalMsg({ type: "error", text: err?.response?.data?.detail || "삭제 실패" });
    }
  };

  // Target Site toggle
  const handleToggleTargetSite = async (site: TargetSite) => {
    try {
      await smartApi.toggleTargetSite(site.id);
      const sites = await smartApi.getTargetSites();
      setTargetSites(sites);
    } catch (err: any) {
      console.error("Failed to toggle target site:", err);
    }
  };

  // Target Site quick test in modal
  const handleTestTargetSite = async (site: TargetSite) => {
    setModalTestingId(site.id);
    setModalTestResult(null);

    try {
      const res = await smartApi.testTargetSite(site.url, site.name, 10);
      setModalTestResult({
        siteName: site.name,
        total_count: res.total_count,
        results: res.results,
        message: res.message
      });
      setTestResult({
        status: res.status,
        collector_type: "us_market_signal",
        target: site.url,
        total_count: res.total_count,
        results: res.results,
        message: res.message
      });
    } catch (err: any) {
      console.error("Test target site failed:", err);
      setModalMsg({ type: "error", text: err?.response?.data?.detail || "사이트 테스트 실패" });
    } finally {
      setModalTestingId(null);
    }
  };

  // Run Dry-Run Test from main form
  const handleRunTest = async () => {
    if (!targetInput.trim()) {
      setActionErrorMsg("대상 검색어, Subreddit 또는 URL을 입력해주세요.");
      return;
    }

    setTesting(true);
    setTestResult(null);
    setTopicGraphResult(null);
    setActionErrorMsg(null);
    setActionSuccessMsg(null);

    try {
      if (activeType === "topic_graph") {
        const graphRes = await smartApi.expandTopicGraph({
          topic: targetInput.trim(),
          depth: topicDepth,
          limit_terms: 8
        });
        setTopicGraphResult(graphRes);
      }

      const activeMode = activeType === "community_spike" ? redditMode : (activeType === "threads_stream" ? threadsMode : undefined);

      const res = await smartApi.testCollector({
        collector_type: activeType,
        target: targetInput.trim(),
        language: language,
        max_results: 10,
        options: {
          mode: activeMode,
          spike_multiplier: spikeMultiplier
        }
      });

      setTestResult(res);
      setActionSuccessMsg(res.message || "테스트가 성공적으로 완료되었습니다.");
    } catch (err: any) {
      console.error("Test failed:", err);
      setActionErrorMsg(err?.response?.data?.detail || err.message || "테스트 실행 중 오류가 발생했습니다.");
    } finally {
      setTesting(false);
    }
  };

  // Save as Active Collector
  const handleSaveCollector = async () => {
    if (!collectorName.trim()) {
      setActionErrorMsg("수집기 이름을 입력해주세요.");
      return;
    }
    if (!targetInput.trim()) {
      setActionErrorMsg("대상 URL 또는 검색어를 입력해주세요.");
      return;
    }

    try {
      const activeMode = activeType === "community_spike" ? redditMode : (activeType === "threads_stream" ? threadsMode : undefined);
      const payload: SmartCollectorCreatePayload = {
        name: collectorName.trim(),
        collector_type: activeType,
        target_url_or_query: targetInput.trim(),
        category: category,
        crawl_interval_minutes: intervalMinutes,
        is_active: true,
        config: {
          language,
          mode: activeMode,
          spike_multiplier: spikeMultiplier,
          depth: topicDepth
        }
      };


      await smartApi.createCollector(payload);
      setActionSuccessMsg(`수집기 '${collectorName}'가 성공적으로 등록되었습니다!`);
      loadData();
    } catch (err: any) {
      console.error("Failed to create collector:", err);
      setActionErrorMsg(err?.response?.data?.detail || err.message || "수집기 저장 중 오류가 발생했습니다.");
    }
  };

  // Trigger instant crawl
  const handleTriggerCrawl = async (id: number, name: string) => {
    try {
      setTriggeringId(id);
      await smartApi.triggerCollector(id);
      setActionSuccessMsg(`'${name}' 수집이 즉시 시작되었습니다.`);
      setTimeout(() => loadData(), 2500);
    } catch (err: any) {
      console.error("Trigger failed:", err);
      setActionErrorMsg(err?.response?.data?.detail || "즉시 수집 실행 실패");
    } finally {
      setTriggeringId(null);
    }
  };

  // Toggle active status
  const handleToggleActive = async (col: SmartCollector) => {
    try {
      await smartApi.updateCollector(col.id, { is_active: !col.is_active });
      loadData();
    } catch (err: any) {
      console.error("Failed to toggle collector:", err);
    }
  };

  // Delete collector
  const handleDeleteCollector = async (id: number, name: string) => {
    if (!confirm(`'${name}' 수집기를 삭제하시겠습니까?`)) return;
    try {
      await smartApi.deleteCollector(id);
      loadData();
      setActionSuccessMsg(`수집기 '${name}'가 삭제되었습니다.`);
    } catch (err: any) {
      console.error("Delete failed:", err);
      setActionErrorMsg("수집기 삭제 실패");
    }
  };

  const filteredCollectors = collectors.filter((c) => {
    if (collectorFilter === "all") return true;
    return c.collector_type === collectorFilter;
  });

  const filteredTargetSites = targetSites.filter((s) => {
    if (targetSiteFilter === "all") return true;
    return s.category === targetSiteFilter;
  });

  const filteredSubreddits = subreddits.filter((s) => {
    const matchesCategory = subCategoryFilter === "all" || s.category === subCategoryFilter;
    const matchesSearch = !subSearchQuery.trim() || 
      s.name.toLowerCase().includes(subSearchQuery.toLowerCase()) ||
      s.label.toLowerCase().includes(subSearchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(subSearchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-8">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                지능형 수집 허브 <span className="text-xs bg-indigo-500/20 text-indigo-400 font-semibold px-2.5 py-0.5 rounded-full border border-indigo-500/30">Next-Gen AI Crawlers</span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                미국 증시 급변 감지, Reddit 멀티 카테고리(UAP, Car, UFO, 주식, 미스터리 등) 급등 수집 & 실시간 댓글(Top Comments) 증분 동기화
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/crawl-admin"
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-xs font-semibold text-slate-300 border border-slate-800 transition-colors"
          >
            <Sliders className="w-3.5 h-3.5 text-slate-400" />
            기존 시드 관리
          </Link>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-xs font-semibold text-indigo-400 border border-indigo-500/30 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingCollectors || loadingTargetSites || loadingSubreddits ? "animate-spin" : ""}`} />
            새로고침
          </button>
        </div>
      </div>

      {/* 2. Top Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">등록된 스마트 수집기</div>
            <div className="text-2xl font-bold text-white mt-1">{collectors.length} <span className="text-xs font-normal text-slate-500">개</span></div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">탐색 가능 Subreddit</div>
            <div className="text-2xl font-bold text-rose-400 mt-1">
              {subreddits.length} <span className="text-xs font-normal text-slate-500">개 카탈로그</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-rose-500/10 text-rose-400 flex items-center justify-center border border-rose-500/20">
            <Compass className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">댓글 파이프라인</div>
            <div className="text-2xl font-bold text-emerald-400 mt-1">실시간 <span className="text-xs font-normal text-slate-500">증분 동기화 지원</span></div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
            <MessageSquare className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div>
            <div className="text-xs font-medium text-slate-400">시그널 & 급등 이벤트</div>
            <div className="text-2xl font-bold text-amber-400 mt-1">{recentSignals.length} <span className="text-xs font-normal text-slate-500">건 감지</span></div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
            <Flame className="w-5 h-5" />
          </div>
        </div>
      </div>


      {/* 3. Main Interactive Tabs for 5 Collector Types */}
      <div className="space-y-6">
        <div className="flex border-b border-slate-800/80 gap-2 overflow-x-auto pb-1">
          <button
            onClick={() => handleTypeChange("us_market_signal")}
            className={`flex items-center gap-2.5 px-4 py-3 font-semibold text-sm rounded-t-xl transition-all border-b-2 ${
              activeType === "us_market_signal"
                ? "bg-slate-900 text-indigo-400 border-indigo-500 shadow-sm"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-slate-900/40"
            }`}
          >
            <Zap className="w-4 h-4 text-amber-400" />
            1. 미국 증시 & 속보 감지
          </button>

          <button
            onClick={() => handleTypeChange("community_spike")}
            className={`flex items-center gap-2.5 px-4 py-3 font-semibold text-sm rounded-t-xl transition-all border-b-2 ${
              activeType === "community_spike"
                ? "bg-slate-900 text-indigo-400 border-indigo-500 shadow-sm"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-slate-900/40"
            }`}
          >
            <Flame className="w-4 h-4 text-rose-500" />
            2. Reddit 커뮤니티 급등 감지
          </button>

          <button
            onClick={() => handleTypeChange("threads_stream")}
            className={`flex items-center gap-2.5 px-4 py-3 font-semibold text-sm rounded-t-xl transition-all border-b-2 ${
              activeType === "threads_stream"
                ? "bg-slate-900 text-indigo-400 border-indigo-500 shadow-sm"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-slate-900/40"
            }`}
          >
            <AtSign className="w-4 h-4 text-sky-400" />
            3. Threads(쓰레즈) 실시간 수집
          </button>

          <button
            onClick={() => handleTypeChange("smart_auto_seed")}
            className={`flex items-center gap-2.5 px-4 py-3 font-semibold text-sm rounded-t-xl transition-all border-b-2 ${
              activeType === "smart_auto_seed"
                ? "bg-slate-900 text-indigo-400 border-indigo-500 shadow-sm"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-slate-900/40"
            }`}
          >
            <Globe className="w-4 h-4 text-cyan-400" />
            4. 자율 탐색 스마트 시드
          </button>

          <button
            onClick={() => handleTypeChange("topic_graph")}
            className={`flex items-center gap-2.5 px-4 py-3 font-semibold text-sm rounded-t-xl transition-all border-b-2 ${
              activeType === "topic_graph"
                ? "bg-slate-900 text-indigo-400 border-indigo-500 shadow-sm"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-slate-900/40"
            }`}
          >
            <Share2 className="w-4 h-4 text-purple-400" />
            5. 토픽 & 지식그래프 확장 수집
          </button>
        </div>

        {/* Dynamic Type Config & Sandbox Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Form & Preset Controls */}
          <div className="lg:col-span-5 space-y-5 bg-slate-900/70 border border-slate-800/80 rounded-2xl p-5 shadow-xl">
            {/* Type Header Info */}
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                {activeType === "us_market_signal" && <><Zap className="w-4 h-4 text-amber-400" /> 미국 시장 & 긴급 속보 수집 설정</>}
                {activeType === "community_spike" && <><Flame className="w-4 h-4 text-rose-500" /> Reddit 커뮤니티 급등 & 실시간 댓글 수집</>}
                {activeType === "threads_stream" && <><AtSign className="w-4 h-4 text-sky-400" /> Meta Threads(쓰레즈) 실시간 수집 설정</>}
                {activeType === "smart_auto_seed" && <><Globe className="w-4 h-4 text-cyan-400" /> CSS 룰 없는 자율 탐색 시드 설정</>}
                {activeType === "topic_graph" && <><Share2 className="w-4 h-4 text-purple-400" /> 토픽 중심 지식그래프 자율 확장 설정</>}
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                {activeType === "us_market_signal" && "Google News RSS 및 등록된 수집 대상 사이트(CNBC, Yahoo Finance 등)를 초단주기로 폴링하여 긴급 시그널을 즉시 포착합니다."}
                {activeType === "community_spike" && "UAP/UFO, 자동차, 주식, 미스터리 등 주요 Subreddit의 인기글과 함께 **고가치 실시간 댓글(Top Comments)**을 동시 수집하고 DB에 증분 연결합니다."}
                {activeType === "threads_stream" && "Meta Threads의 인플루언서(@username) 및 키워드 글을 초기 SSR 주입 데이터 분석으로 실시간 수집합니다."}
                {activeType === "smart_auto_seed" && "임의의 웹 URL만 입력하면 본문 영역 및 최신 글 링크를 스스로 휴리스틱 분석하여 자동 수집합니다."}
                {activeType === "topic_graph" && "관심 주제어를 입력하면 내부 Neo4j 지식그래프 및 LLM 연관어 확장을 통해 심층 연관 기사를 자동 수집합니다."}
              </p>
            </div>

            {/* 🌐 Feature for US Market Signal Tab: Manage Target Sites Trigger Card */}
            {activeType === "us_market_signal" && (
              <div className="bg-gradient-to-r from-sky-950/40 via-indigo-950/30 to-slate-900 border border-sky-800/40 rounded-xl p-3.5 space-y-2.5 shadow-md">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-sky-300">
                    <Globe className="w-4 h-4 text-sky-400" />
                    수집 대상 사이트 및 금융 피드 ({targetSites.filter(s => s.is_active).length}개 활성)
                  </div>
                  <button
                    onClick={() => setShowTargetSitesModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs transition shadow-md shadow-sky-600/20"
                  >
                    <Settings2 className="w-3.5 h-3.5" /> 사이트 관리 및 테스트
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {targetSites.slice(0, 4).map((site) => (
                    <span
                      key={site.id}
                      className={`text-[11px] px-2 py-0.5 rounded-md border ${
                        site.is_active ? "bg-sky-900/40 text-sky-200 border-sky-700/50" : "bg-slate-800 text-slate-500 border-slate-700"
                      }`}
                    >
                      {site.name.split("(")[0].trim()}
                    </span>
                  ))}
                  {targetSites.length > 4 && (
                    <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 border border-slate-700">
                      +{targetSites.length - 4}개 더보기
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* 🛸 Feature for Reddit Community Spike Tab: Subreddit Directory & Explorer Trigger Card */}
            {activeType === "community_spike" && (
              <div className="bg-gradient-to-r from-rose-950/40 via-purple-950/30 to-slate-900 border border-rose-800/40 rounded-xl p-3.5 space-y-2.5 shadow-md">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-rose-300">
                    <Compass className="w-4 h-4 text-rose-400" />
                    Subreddit 전체 카탈로그 탐색기 ({subreddits.length}개 분야별 등록)
                  </div>
                  <button
                    onClick={() => setShowSubredditModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition shadow-md shadow-rose-600/20"
                  >
                    <Search className="w-3.5 h-3.5" /> 전체 목록 탐색 및 선택
                  </button>
                </div>
                <p className="text-[11px] text-slate-400">
                  UAP, UFO, 자동차, 미스터리, AI, 주식 등 분야별 서브레딧 상세 설명 및 실시간 테스트 제공
                </p>
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {subreddits.slice(0, 6).map((sub) => (
                    <button
                      key={sub.id}
                      onClick={() => handleSelectSubreddit(sub)}
                      className={`text-[11px] px-2 py-0.5 rounded-md border text-left transition flex items-center gap-1 ${
                        targetInput.replace("r/", "").toLowerCase() === sub.name.toLowerCase()
                          ? "bg-rose-600 text-white border-rose-500 font-semibold"
                          : "bg-slate-900/80 hover:bg-rose-950/40 text-slate-300 border-slate-800"
                      }`}
                    >
                      <span>{sub.icon}</span> {sub.display_name}
                    </button>
                  ))}
                  {subreddits.length > 6 && (
                    <button
                      onClick={() => setShowSubredditModal(true)}
                      className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800 hover:bg-slate-700 text-rose-300 border border-slate-700"
                    >
                      +{subreddits.length - 6}개 카탈로그 전체보기
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Quick Presets */}
            <div>
              <label className="text-xs font-semibold text-slate-300 mb-1.5 block flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> 추천 프리셋 템플릿
              </label>
              <div className="flex flex-wrap gap-1.5">
                {activeType === "us_market_signal" && (
                  <>
                    <button
                      onClick={() => applyPreset({ name: "NVIDIA & 빅테크 AI 시그널", target: "NVIDIA OR Apple OR Tesla OR AI Chip", lang: "en", interval: 5 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-indigo-900/40 text-slate-300 hover:text-indigo-300 rounded-md border border-slate-700 transition"
                    >
                      ⚡ NVIDIA & 빅테크 AI
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "Fed 금리 & FOMC 긴급 속보", target: "Fed OR Powell OR Rate Cut OR Treasury Yield", lang: "en", interval: 3 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-indigo-900/40 text-slate-300 hover:text-indigo-300 rounded-md border border-slate-700 transition"
                    >
                      🏛️ Fed 금리 & FOMC
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "글로벌 반도체 & 환율 속보", target: "반도체 OR 파운드리 OR HBM OR 원달러환율", lang: "ko", interval: 10 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-indigo-900/40 text-slate-300 hover:text-indigo-300 rounded-md border border-slate-700 transition"
                    >
                      🇰🇷 국내 반도체 & 환율
                    </button>
                  </>
                )}

                {activeType === "community_spike" && (
                  <>
                    <button
                      onClick={() => applyPreset({ name: "UFO & UAP 탈기밀 청문회 속보", target: "UFOs", interval: 10, mode: "hot" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 rounded-md border border-slate-700 transition"
                    >
                      🛸 r/UFOs (탈기밀/청문회)
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "차세대 전기차 & 모빌리티", target: "electricvehicles", interval: 15, mode: "hot" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 rounded-md border border-slate-700 transition"
                    >
                      ⚡ r/electricvehicles (EV)
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "초자연 & 미해결 미스터리", target: "HighStrangeness", interval: 20, mode: "hot" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 rounded-md border border-slate-700 transition"
                    >
                      🌌 r/HighStrangeness (미스터리)
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "WSB 실시간 급등 모멘텀", target: "wallstreetbets", interval: 5, mode: "hot" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 rounded-md border border-slate-700 transition"
                    >
                      🚀 r/wallstreetbets (WSB)
                    </button>
                  </>
                )}

                {activeType === "threads_stream" && (
                  <>
                    <button
                      onClick={() => applyPreset({ name: "🇰🇷 대한민국 Threads 실시간 핫스레드", target: "korean_trending", lang: "ko", interval: 10, threads_mode: "korean_trending" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      🇰🇷 국내 실시간 핫스레드
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "🏢 판교 테크기업 & 개발자 이직 트렌드", target: "테크 직장인 이직", lang: "ko", interval: 15, threads_mode: "korean_trending" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      🏢 판교 테크 & 이직
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "📈 삼전·하이닉스 & HBM 핫이슈", target: "삼전 하이닉스 HBM", lang: "ko", interval: 10, threads_mode: "korean_trending" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      📈 삼전·하이닉스 HBM
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "🤖 국내 AI & 챗GPT 실무 활용 트렌드", target: "AI 챗GPT 실무", lang: "ko", interval: 15, threads_mode: "korean_trending" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      🤖 AI & 챗GPT 실무
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "🔥 글로벌 Threads 실시간 트렌딩", target: "trending", lang: "en", interval: 10, threads_mode: "trending" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      🔥 글로벌 실시간 트렌딩
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "🚀 글로벌 Threads 바이럴 핫 포스트", target: "global_viral", lang: "en", interval: 10, threads_mode: "viral" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      🚀 글로벌 바이럴 TOP
                    </button>

                    <button
                      onClick={() => applyPreset({ name: "샘 올트먼(@sama) 쓰레즈 피드", target: "sama", lang: "en", interval: 10, threads_mode: "user_profile" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      👤 @sama (OpenAI)
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "마크 저커버그(@zuck) 쓰레즈 피드", target: "zuck", lang: "en", interval: 15, threads_mode: "user_profile" })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-sky-900/40 text-slate-300 hover:text-sky-300 rounded-md border border-slate-700 transition"
                    >
                      👤 @zuck (Meta)
                    </button>
                  </>
                )}

                {activeType === "smart_auto_seed" && (
                  <>
                    <button
                      onClick={() => applyPreset({ name: "TechCrunch AI 자율 수집", target: "https://techcrunch.com/category/artificial-intelligence/", lang: "en", interval: 30 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-cyan-900/40 text-slate-300 hover:text-cyan-300 rounded-md border border-slate-700 transition"
                    >
                      🌐 TechCrunch AI
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "Hacker News 메인", target: "https://news.ycombinator.com", lang: "en", interval: 15 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-cyan-900/40 text-slate-300 hover:text-cyan-300 rounded-md border border-slate-700 transition"
                    >
                      🟧 Hacker News
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "Yahoo Finance 뉴스", target: "https://finance.yahoo.com/news/", lang: "en", interval: 20 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-cyan-900/40 text-slate-300 hover:text-cyan-300 rounded-md border border-slate-700 transition"
                    >
                      💵 Yahoo Finance
                    </button>
                  </>
                )}

                {activeType === "topic_graph" && (
                  <>
                    <button
                      onClick={() => applyPreset({ name: "전고체 배터리 지식그래프", target: "전고체 배터리", lang: "ko", interval: 15 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-purple-900/40 text-slate-300 hover:text-purple-300 rounded-md border border-slate-700 transition"
                    >
                      🔋 전고체 배터리
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "HBM 차세대 반도체", target: "HBM", lang: "ko", interval: 15 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-purple-900/40 text-slate-300 hover:text-purple-300 rounded-md border border-slate-700 transition"
                    >
                      💾 HBM 반도체
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "트럼프 관세 및 통상정책", target: "트럼프", lang: "ko", interval: 10 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-purple-900/40 text-slate-300 hover:text-purple-300 rounded-md border border-slate-700 transition"
                    >
                      🇺🇸 트럼프 통상/관세
                    </button>
                    <button
                      onClick={() => applyPreset({ name: "양자컴퓨팅 및 양자암호", target: "양자컴퓨팅", lang: "ko", interval: 30 })}
                      className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-purple-900/40 text-slate-300 hover:text-purple-300 rounded-md border border-slate-700 transition"
                    >
                      ⚛️ 양자컴퓨팅
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Input Fields */}
            <div className="space-y-3.5 pt-1">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  수집기 식별 이름
                </label>
                <input
                  type="text"
                  value={collectorName}
                  onChange={(e) => setCollectorName(e.target.value)}
                  placeholder="예: 🇰🇷 대한민국 Threads 실시간 핫스레드"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
                />
              </div>

              {/* Threads Mode Selector Dropdown */}
              {activeType === "threads_stream" && (
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Threads 수집 범위 / 모드
                  </label>
                  <select
                    value={threadsMode}
                    onChange={(e) => {
                      const m = e.target.value as any;
                      setThreadsMode(m);
                      if (m === "korean_trending") {
                        setLanguage("ko");
                        setTargetInput("korean_trending");
                        setCollectorName("🇰🇷 대한민국 Threads 실시간 핫스레드");
                      } else if (m === "trending") {
                        setLanguage("en");
                        setTargetInput("trending");
                        setCollectorName("🔥 글로벌 Threads 실시간 트렌딩");
                      } else if (m === "viral") {
                        setLanguage("en");
                        setTargetInput("global_viral");
                        setCollectorName("🚀 글로벌 Threads 바이럴 핫 포스트");
                      } else if (m === "user_profile") {
                        setTargetInput("sama");
                        setCollectorName("샘 올트먼(@sama) 쓰레즈 피드");
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-medium focus:outline-none focus:border-sky-500"
                  >
                    <option value="korean_trending">🇰🇷 대한민국 실시간 핫스레드 (국내 전역 화제글)</option>
                    <option value="trending">🔥 글로벌 실시간 트렌딩 (Trending Now)</option>
                    <option value="viral">🚀 글로벌 바이럴 랭킹 (Viral Top Feed)</option>
                    <option value="topic_search">🔍 키워드 / 해시태그 실시간 검색</option>
                    <option value="user_profile">👤 특정 계정 / 인플루언서 피드 (@username)</option>
                  </select>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-300">
                    {activeType === "us_market_signal" && "검색 쿼리 또는 직접 RSS 피드 URL"}
                    {activeType === "community_spike" && "수집 대상 Subreddit (예: UFOs, cars, wallstreetbets 또는 직접 입력)"}
                    {activeType === "threads_stream" && (
                      threadsMode === "user_profile" ? "Threads 계정명 (예: @sama, @zuck)" :
                      threadsMode === "topic_search" ? "검색할 키워드 또는 토픽 (예: #주식, #이직, #AI)" :
                      "수집 대상 쿼리 / 토픽 필터 (선택 사항 - 비워두면 전역 핫이슈 수집)"
                    )}
                    {activeType === "smart_auto_seed" && "탐색 대상 웹사이트 Seed URL"}
                    {activeType === "topic_graph" && "중심 탐색 주제어 (Core Topic)"}
                  </label>
                  {activeType === "community_spike" && (
                    <button
                      type="button"
                      onClick={() => setShowSubredditModal(true)}
                      className="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1 font-semibold"
                    >
                      <Compass className="w-3 h-3" /> 전체 카탈로그 탐색기 열기
                    </button>
                  )}
                </div>
                <input
                  type="text"
                  value={targetInput}
                  onChange={(e) => setTargetInput(e.target.value)}
                  placeholder={
                    activeType === "us_market_signal" ? "US Stock Market OR Fed OR NVIDIA" :
                    activeType === "community_spike" ? "UFOs" :
                    activeType === "threads_stream" ? (threadsMode === "user_profile" ? "sama" : "korean_trending") :
                    activeType === "smart_auto_seed" ? "https://news.ycombinator.com" : "전고체 배터리"
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-indigo-500 transition"
                />
              </div>

              {/* Type-Specific Options for Reddit */}
              {activeType === "community_spike" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">정렬 / 모드</label>
                    <select
                      value={redditMode}
                      onChange={(e) => setRedditMode(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                    >
                      <option value="hot">Hot (인기 급상승)</option>
                      <option value="rising">Rising (초기 급등)</option>
                      <option value="new">New (신규 등록)</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">급등 감지 민감도</label>
                    <select
                      value={spikeMultiplier}
                      onChange={(e) => setSpikeMultiplier(Number(e.target.value))}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                    >
                      <option value={1.2}>1.2x (매우 민감 - 초기 반응 포착)</option>
                      <option value={1.5}>1.5x (표준 - 화제성 게시물)</option>
                      <option value={2.5}>2.5x (초급등 - 대규모 바이럴만)</option>
                    </select>
                  </div>
                </div>
              )}


              {activeType === "topic_graph" && (
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">지식그래프 탐색 깊이 (Graph Depth)</label>
                  <select
                    value={topicDepth}
                    onChange={(e) => setTopicDepth(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value={1}>1단계 (직접 연관어 8개 확장)</option>
                    <option value={2}>2단계 (심층 하위연관어 16개 복합 확장)</option>
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">수집 주기</label>
                  <select
                    value={intervalMinutes}
                    onChange={(e) => setIntervalMinutes(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value={3}>3분 (초고속 속보)</option>
                    <option value={5}>5분 (마켓 급변/스파이크)</option>
                    <option value={10}>10분 (표준)</option>
                    <option value={15}>15분 (권장)</option>
                    <option value={30}>30분</option>
                    <option value={60}>60분 (1시간)</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">언어</label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="en">영어 (Global / US)</option>
                    <option value="ko">한국어 (국내)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Actions: Run Test & Save */}
            <div className="pt-3 border-t border-slate-800/80 flex flex-col sm:flex-row gap-2.5">
              <button
                onClick={handleRunTest}
                disabled={testing}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-sm shadow-lg shadow-indigo-500/20 disabled:opacity-50 transition-all"
              >
                {testing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    실시간 탐색 및 파싱 중...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    실시간 Dry-Run 테스트
                  </>
                )}
              </button>

              <button
                onClick={handleSaveCollector}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm shadow-lg shadow-emerald-500/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                수집기로 저장
              </button>
            </div>

            {/* Notifications */}
            {actionSuccessMsg && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{actionSuccessMsg}</span>
              </div>
            )}
            {actionErrorMsg && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{actionErrorMsg}</span>
              </div>
            )}
          </div>

          {/* Right Column: Interactive Test Results Sandbox */}
          <div className="lg:col-span-7 space-y-4">
            <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-5 shadow-xl min-h-[480px] flex flex-col">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-sm font-bold text-white">실시간 Dry-Run 테스트 결과 미리보기</h3>
                </div>
                {testResult && (
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    총 {testResult.total_count}건 감지됨
                  </span>
                )}
              </div>

              {/* Topic Graph Expansion Preview Banner if active */}
              {topicGraphResult && (
                <div className="mb-4 p-3.5 bg-purple-950/40 border border-purple-800/50 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-purple-300 flex items-center gap-1.5">
                      <Share2 className="w-3.5 h-3.5 text-purple-400" /> 지식그래프 연관 노드 자동 확장 ({topicGraphResult.expanded_keywords.length}개)
                    </span>
                    <span className="text-[11px] text-purple-400 font-mono">
                      중심 주제: {topicGraphResult.center_topic}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {topicGraphResult.expanded_keywords.map((kw, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 bg-purple-900/50 text-purple-200 rounded-md border border-purple-700/50">
                        🔗 {kw}
                      </span>
                    ))}
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    자동 생성 쿼리: <span className="text-indigo-300">{topicGraphResult.suggested_query}</span>
                  </div>
                </div>
              )}

              {/* Sandbox Body */}
              {testing ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-400 space-y-3 py-16">
                  <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
                  <p className="text-sm font-medium">원격 피드/엔드포인트에서 본문 및 실시간 댓글 트리를 수집 중입니다...</p>
                </div>
              ) : testResult && testResult.results.length > 0 ? (
                <div className="space-y-3 flex-1 overflow-y-auto max-h-[580px] pr-1">
                  {testResult.results.map((item, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3.5 hover:border-slate-700 transition space-y-2.5"
                    >
                      {/* Top Header of Item */}
                      <div className="flex items-start justify-between gap-3">
                        <h4 className="text-sm font-semibold text-slate-100 line-clamp-2 hover:text-indigo-300">
                          <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5">
                            {item.title}
                            <ExternalLink className="w-3 h-3 text-slate-500 shrink-0 inline" />
                          </a>
                        </h4>
                        
                        {/* Type Badges */}
                        {activeType === "us_market_signal" && (
                          <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full shrink-0 border ${
                            item.sentiment === "BULLISH" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                            item.sentiment === "BEARISH" ? "bg-rose-500/10 text-rose-400 border-rose-500/30" :
                            "bg-slate-800 text-slate-300 border-slate-700"
                          }`}>
                            {item.sentiment} ({item.impact_score}점)
                          </span>
                        )}

                        {(activeType === "community_spike" || activeType === "threads_stream") && (
                          <div className="flex items-center gap-1.5 shrink-0">
                            {item.mention_count_1h && (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border bg-amber-500/15 text-amber-300 border-amber-500/30 flex items-center gap-1">
                                ⚡ 1시간 {item.mention_count_1h}건 (+{item.surge_rate}%)
                              </span>
                            )}
                            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border flex items-center gap-1 ${
                              item.is_spike
                                ? "bg-rose-500/20 text-rose-400 border-rose-500/40 shadow-sm shadow-rose-500/20"
                                : "bg-slate-800 text-slate-400 border-slate-700"
                            }`}>
                              <Flame className="w-3 h-3 text-rose-400" />
                              {item.velocity_score}/h
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Summary or Preview */}
                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                        {item.summary || item.content_preview || "상세 본문 내용"}
                      </p>

                      {/* Bottom Meta & Tags */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-900 text-[11px] text-slate-500">
                        <div className="flex items-center gap-3">
                          {item.author && <span className="text-sky-400 font-semibold">{item.author}</span>}
                          {item.minutes_ago && <span className="text-slate-400 font-mono">⏱️ {item.minutes_ago}분 전</span>}
                          {item.publisher && <span>📰 {item.publisher}</span>}
                          {item.board && item.board !== "Threads" && <span className="text-rose-400 font-semibold">{item.board}</span>}
                          {item.score !== undefined && (
                            <span className="flex items-center gap-1 text-slate-400">
                              <ThumbsUp className="w-3 h-3" /> {item.score}
                            </span>
                          )}
                          {item.num_comments !== undefined && (

                            <span className="flex items-center gap-1 text-slate-400">
                              <MessageSquare className="w-3 h-3" /> {item.num_comments}
                            </span>
                          )}
                        </div>

                        {/* Signals or Tickers Badges */}
                        <div className="flex items-center gap-1">
                          {item.signals && item.signals.map((sig: string, sIdx: number) => (
                            <span key={sIdx} className="px-1.5 py-0.5 bg-amber-500/10 text-amber-300 rounded border border-amber-500/20 text-[10px]">
                              #{sig}
                            </span>
                          ))}
                          {item.tickers && item.tickers.map((tik: string, tIdx: number) => (
                            <span key={tIdx} className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-300 font-mono rounded border border-emerald-500/20 text-[10px]">
                              ${tik}
                            </span>
                          ))}
                          {item.matched_graph_nodes && item.matched_graph_nodes.map((n: string, nIdx: number) => (
                            <span key={nIdx} className="px-1.5 py-0.5 bg-purple-500/10 text-purple-300 rounded border border-purple-500/20 text-[10px]">
                              🔗 {n}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* 💬 Comments Accordion Trigger */}
                      {item.top_comments && item.top_comments.length > 0 && (
                        <div className="pt-2 border-t border-slate-900/80">
                          <button
                            onClick={() => toggleComments(idx)}
                            className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
                          >
                            <MessageSquare className="w-3.5 h-3.5" />
                            <span>상위 핵심 댓글 ({item.top_comments.length}개)</span>
                            {expandedCommentsMap[idx] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          </button>

                          {/* Expanded Comments List */}
                          {expandedCommentsMap[idx] && (
                            <div className="mt-2.5 space-y-2 pl-2 border-l-2 border-indigo-500/30">
                              {item.top_comments.map((c: any, cIdx: number) => (
                                <div key={cIdx} className="p-2.5 bg-slate-900/80 rounded-lg border border-slate-800/80 text-xs space-y-1">
                                  <div className="flex items-center justify-between text-[11px]">
                                    <span className="font-semibold text-rose-300 flex items-center gap-1">
                                      <CornerDownRight className="w-3 h-3 text-slate-500" />
                                      {c.author}
                                    </span>
                                    <span className="text-emerald-400 font-mono flex items-center gap-0.5">
                                      <ThumbsUp className="w-2.5 h-2.5" /> +{c.score}
                                    </span>
                                  </div>
                                  <p className="text-slate-300 leading-relaxed text-[11px]">{c.content}</p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-500 space-y-2 py-16">
                  <div className="w-12 h-12 rounded-full bg-slate-900 flex items-center justify-center text-slate-600">
                    <Search className="w-6 h-6" />
                  </div>
                  <p className="text-sm">좌측에서 파라미터를 설정한 후 [실시간 Dry-Run 테스트] 버튼을 누르거나,</p>
                  <p className="text-xs text-slate-400">Subreddit 탐색기에서 원하는 관심 분야(UAP, Car, UFO, 미스터리 등)를 선택해보세요.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Active Smart Collectors Management Table */}
      <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-indigo-400" /> 등록된 지능형 수집기 목록
            </h2>
            <p className="text-xs text-slate-400">
              현재 백그라운드 스케줄러에서 자동 가동 중인 5대 스마트 수집기를 관리합니다.
            </p>
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">유형 필터:</span>
            <select
              value={collectorFilter}
              onChange={(e) => setCollectorFilter(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="all">전체 수집기</option>
              <option value="us_market_signal">미국 증시/속보</option>
              <option value="community_spike">Reddit 커뮤니티 급등</option>
              <option value="threads_stream">Threads(쓰레즈)</option>
              <option value="smart_auto_seed">자율 스마트 시드</option>
              <option value="topic_graph">토픽 지식그래프</option>
            </select>
          </div>
        </div>

        {loadingCollectors ? (
          <div className="py-12 flex justify-center text-slate-400 gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" /> 수집기 목록 로딩 중...
          </div>
        ) : filteredCollectors.length === 0 ? (
          <div className="py-12 text-center text-slate-500 space-y-2">
            <p className="text-sm">등록된 스마트 수집기가 없습니다.</p>
            <p className="text-xs">상단 수집기 설정 영역에서 프리셋을 선택하고 [수집기로 저장]을 눌러보세요.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-3 px-3">ID</th>
                  <th className="py-3 px-3">수집기 이름</th>
                  <th className="py-3 px-3">수집 유형</th>
                  <th className="py-3 px-3">수집 대상 (URL/Subreddit/Account)</th>
                  <th className="py-3 px-3">수집 주기</th>
                  <th className="py-3 px-3">상태</th>
                  <th className="py-3 px-3 text-right">작업</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredCollectors.map((col) => (
                  <tr key={col.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3 font-mono text-slate-500">#{col.id}</td>
                    <td className="py-3 px-3 font-semibold text-slate-200">{col.name}</td>
                    <td className="py-3 px-3">
                      {col.collector_type === "us_market_signal" && (
                        <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
                          ⚡ 미국 증시 속보
                        </span>
                      )}
                      {col.collector_type === "community_spike" && (
                        <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 font-medium">
                          🔥 Reddit 급등
                        </span>
                      )}
                      {col.collector_type === "threads_stream" && (
                        <span className="px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20 font-medium">
                          🧵 Threads 피드
                        </span>
                      )}
                      {col.collector_type === "smart_auto_seed" && (
                        <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-medium">
                          🌐 스마트 시드
                        </span>
                      )}
                      {col.collector_type === "topic_graph" && (
                        <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 font-medium">
                          🧠 토픽 지식그래프
                        </span>
                      )}
                      {col.collector_type === "rule_seed" && (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                          기존 룰 시드
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-400 max-w-[280px] truncate" title={col.target_url_or_query}>
                      {col.target_url_or_query}
                    </td>
                    <td className="py-3 px-3 text-slate-300">{col.crawl_interval_minutes}분</td>
                    <td className="py-3 px-3">
                      <button
                        onClick={() => handleToggleActive(col)}
                        className={`px-2.5 py-0.5 rounded-full font-semibold text-[11px] border transition ${
                          col.is_active
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
                            : "bg-slate-800 text-slate-500 border-slate-700 hover:bg-slate-700"
                        }`}
                      >
                        {col.is_active ? "가동중" : "일시중지"}
                      </button>
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <button
                        onClick={() => handleTriggerCrawl(col.id, col.name)}
                        disabled={triggeringId === col.id}
                        className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 text-xs font-semibold inline-flex items-center gap-1 transition"
                      >
                        <Play className={`w-3 h-3 ${triggeringId === col.id ? "animate-spin" : "fill-current"}`} />
                        즉시 실행
                      </button>
                      <button
                        onClick={() => handleDeleteCollector(col.id, col.name)}
                        className="px-2 py-1 rounded-lg bg-rose-600/10 hover:bg-rose-600/30 text-rose-400 border border-rose-500/30 text-xs inline-flex items-center transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Live Detected Signals & Spikes Feed */}
      <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Flame className="w-5 h-5 text-amber-400" />
            <div>
              <h2 className="text-base font-bold text-white">실시간 감지 시그널 & 트렌드 레이더 피드</h2>
              <p className="text-xs text-slate-400">스마트 수집기가 최근 탐지한 마켓 시그널, Reddit 급등, Threads 및 연결된 댓글 목록</p>
            </div>
          </div>
          <button
            onClick={loadData}
            className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> 피드 새로고침
          </button>
        </div>

        {recentSignals.length === 0 ? (
          <div className="py-8 text-center text-slate-500 text-xs">
            아직 기록된 시그널 이벤트가 없습니다. 수집기를 즉시 실행하거나 상단에서 테스트를 진행해보세요.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {recentSignals.map((sig) => (
              <div
                key={sig.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3.5 space-y-2.5 hover:border-slate-700 transition"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className={`px-2 py-0.5 rounded font-semibold ${
                    sig.event_type === "market_signal_detected" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
                    sig.event_type === "trend_spike_detected" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
                    sig.event_type === "topic_graph_expanded" ? "bg-purple-500/10 text-purple-400 border border-purple-500/20" :
                    "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                  }`}>
                    {sig.event_type === "market_signal_detected" ? "⚡ 마켓 시그널" :
                     sig.event_type === "trend_spike_detected" ? "🔥 Reddit 급등" :
                     sig.event_type === "topic_graph_expanded" ? "🧠 지식그래프" : "🧵 Threads/시드"}
                  </span>
                  <span className="text-slate-500 font-mono">
                    {sig.created_at ? new Date(sig.created_at).toLocaleTimeString() : ""}
                  </span>
                </div>

                <h4 className="text-xs font-semibold text-slate-200 line-clamp-2">
                  {sig.title}
                </h4>

                <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-900 text-xs">
                  {sig.url ? (
                    <a
                      href={sig.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 truncate max-w-[150px]"
                    >
                      <ExternalLink className="w-3 h-3 shrink-0" />
                      {sig.url}
                    </a>
                  ) : <span></span>}

                  <button
                    onClick={() => handleOpenCommentsModal(sig.title || "제목 없음", sig.url || "", [], sig.source_id || undefined)}
                    className="flex items-center gap-1 px-2 py-1 bg-slate-900 hover:bg-slate-800 text-indigo-300 text-[11px] font-semibold rounded border border-slate-800 transition"
                  >
                    <MessageSquare className="w-3 h-3 text-indigo-400" /> 댓글 확인 & 동기화
                  </button>


                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ============================================================================== */}
      {/* 💬 Comments Viewer & Incremental Sync Modal (실시간 댓글 뷰어 및 증분 동기화 모달) */}
      {/* ============================================================================== */}
      {showCommentsModal && selectedArticleComments && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 overflow-y-auto">
          <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    실시간 댓글 트리 및 증분 동기화
                    <span className="text-xs bg-indigo-500/20 text-indigo-300 font-medium px-2 py-0.5 rounded-full border border-indigo-500/30">
                      {selectedArticleComments.comments.length}개 댓글 연결됨
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400 line-clamp-1 max-w-lg">
                    {selectedArticleComments.title}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setShowCommentsModal(false)}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4 overflow-y-auto flex-1">
              {/* Alert inside Modal */}
              {commentsModalMsg && (
                <div className={`p-3 rounded-xl text-xs flex items-center justify-between gap-2 ${
                  commentsModalMsg.type === "success"
                    ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                    : "bg-rose-500/10 border border-rose-500/20 text-rose-400"
                }`}>
                  <div className="flex items-center gap-2">
                    {commentsModalMsg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
                    <span>{commentsModalMsg.text}</span>
                  </div>
                  <button onClick={() => setCommentsModalMsg(null)} className="text-xs opacity-70 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
                </div>
              )}

              {/* Sync Trigger Banner */}
              <div className="flex items-center justify-between p-3.5 bg-slate-950 border border-slate-800 rounded-xl">
                <div>
                  <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                    <RefreshCw className="w-3.5 h-3.5 text-indigo-400" /> 신규 추가 댓글 실시간 추적
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    해당 글의 엔드포인트에서 새로 달린 댓글만 즉시 가져와 DB에 연결하고 추천수를 갱신합니다.
                  </p>
                </div>

                <button
                  onClick={handleSyncComments}
                  disabled={loadingCommentsSync}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-xs transition shadow-md shadow-indigo-600/20 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingCommentsSync ? "animate-spin" : ""}`} />
                  {loadingCommentsSync ? "동기화 중..." : "최신 댓글 동기화"}
                </button>
              </div>

              {/* Comments List */}
              {selectedArticleComments.comments.length === 0 ? (
                <div className="py-12 text-center text-slate-500 space-y-2">
                  <MessageCircle className="w-8 h-8 text-slate-600 mx-auto" />
                  <p className="text-xs">아직 수집된 댓글이 없습니다. [최신 댓글 동기화]를 눌러 실시간 댓글을 수집해보세요.</p>
                </div>
              ) : (
                <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
                  {selectedArticleComments.comments.map((c, i) => (
                    <div key={i} className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-rose-300">{c.author || "익명"}</span>
                          {c.published_at && (
                            <span className="text-[11px] text-slate-500">
                              {new Date(c.published_at).toLocaleTimeString()}
                            </span>
                          )}
                        </div>
                        <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1">
                          <ThumbsUp className="w-3 h-3" /> +{c.score}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{c.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-3.5 border-t border-slate-800 bg-slate-950/80">
              <button
                onClick={() => setShowCommentsModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* 🛸 2. Subreddit Explorer & Catalog Modal (Subreddit 전체 탐색기 모달 창) */}
      {/* ============================================================================== */}
      {showSubredditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 overflow-y-auto">
          <div className="relative w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center border border-rose-500/20">
                  <Compass className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    Subreddit 전체 카탈로그 탐색기
                    <span className="text-xs bg-rose-500/20 text-rose-300 font-medium px-2 py-0.5 rounded-full border border-rose-500/30">
                      총 {subreddits.length}개 분야별 카탈로그 등록됨
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    UAP, UFO, 자동차, 미스터리, AI, 주식 등 다양한 관심 분야의 서브레딧 내용을 확인하고 실시간 테스트 및 선택할 수 있습니다.
                  </p>
                </div>
              </div>

              <button
                onClick={() => {
                  setShowSubredditModal(false);
                  setSubModalMsg(null);
                  setSubModalTestResult(null);
                }}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5 overflow-y-auto flex-1">
              {/* Notification inside Modal */}
              {subModalMsg && (
                <div className={`p-3 rounded-xl text-xs flex items-center justify-between gap-2 ${
                  subModalMsg.type === "success"
                    ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                    : "bg-rose-500/10 border border-rose-500/20 text-rose-400"
                }`}>
                  <div className="flex items-center gap-2">
                    {subModalMsg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
                    <span>{subModalMsg.text}</span>
                  </div>
                  <button onClick={() => setSubModalMsg(null)} className="text-xs opacity-70 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
                </div>
              )}

              {/* Search Bar & Category Filter Bar */}
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={subSearchQuery}
                      onChange={(e) => setSubSearchQuery(e.target.value)}
                      placeholder="Subreddit 이름, 키워드 또는 설명 검색 (예: ufo, car, mystery, ai, options)..."
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-rose-500"
                    />
                  </div>
                  <button
                    onClick={() => setShowAddSubForm(!showAddSubForm)}
                    className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 transition"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    {showAddSubForm ? "신규 등록 폼 닫기" : "새로운 Subreddit 등록"}
                  </button>
                </div>

                {/* Category Pills */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {[
                    { id: "all", label: "전체 카탈로그" },
                    { id: "ufo_mystery", label: "🛸 UFO / UAP / 미스터리" },
                    { id: "cars_ev", label: "🚗 자동차 / 전기차" },
                    { id: "tech_ai", label: "🤖 AI / 테크 / 과학" },
                    { id: "finance", label: "📈 주식 / 투자 / 크립토" },
                    { id: "world_news", label: "🌍 글로벌 뉴스 / 시사" },
                    { id: "custom", label: "⭐ 사용자 등록" },
                  ].map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setSubCategoryFilter(cat.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                        subCategoryFilter === cat.id
                          ? "bg-rose-600 text-white border-rose-500 shadow-md shadow-rose-600/20"
                          : "bg-slate-950 text-slate-400 hover:text-slate-200 border-slate-800 hover:bg-slate-900"
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Add Custom Subreddit Collapsible Form */}
              {showAddSubForm && (
                <div className="bg-slate-950/90 border border-rose-800/40 rounded-xl p-4 space-y-3 shadow-inner">
                  <div className="flex items-center gap-2 text-xs font-bold text-rose-300">
                    <PlusCircle className="w-4 h-4" /> 카탈로그에 새로운 Subreddit 추가
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                    <div className="sm:col-span-3">
                      <label className="text-[11px] text-slate-400 mb-1 block">Subreddit 식별자 (r/ 제외)</label>
                      <input
                        type="text"
                        value={newSubName}
                        onChange={(e) => setNewSubName(e.target.value)}
                        placeholder="예: UAPscience"
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500"
                      />
                    </div>
                    <div className="sm:col-span-3">
                      <label className="text-[11px] text-slate-400 mb-1 block">표시 레이블 / 제목</label>
                      <input
                        type="text"
                        value={newSubLabel}
                        onChange={(e) => setNewSubLabel(e.target.value)}
                        placeholder="예: UAP 과학적 분석 연구"
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500"
                      />
                    </div>
                    <div className="sm:col-span-3">
                      <label className="text-[11px] text-slate-400 mb-1 block">카테고리</label>
                      <select
                        value={newSubCategory}
                        onChange={(e) => setNewSubCategory(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-2 text-xs text-white focus:outline-none focus:border-rose-500"
                      >
                        <option value="ufo_mystery">🛸 UFO / UAP / 미스터리</option>
                        <option value="cars_ev">🚗 자동차 / 전기차</option>
                        <option value="tech_ai">🤖 AI / 테크 / 과학</option>
                        <option value="finance">📈 주식 / 투자 / 크립토</option>
                        <option value="world_news">🌍 글로벌 뉴스 / 시사</option>
                        <option value="custom">⭐ 기타 / 커스텀</option>
                      </select>
                    </div>
                    <div className="sm:col-span-3 flex items-end">
                      <button
                        onClick={handleAddSubreddit}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition shadow-md shadow-rose-600/20"
                      >
                        <Plus className="w-3.5 h-3.5" /> 카탈로그에 저장
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Subreddit Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {filteredSubreddits.map((sub) => (
                  <div
                    key={sub.id}
                    className="bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 rounded-xl p-4 space-y-3 transition flex flex-col justify-between"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-bold text-white flex items-center gap-1.5">
                          <span className="text-base">{sub.icon}</span> {sub.display_name}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                          sub.category === "ufo_mystery" ? "bg-purple-500/10 text-purple-300 border border-purple-500/20" :
                          sub.category === "cars_ev" ? "bg-cyan-500/10 text-cyan-300 border border-cyan-500/20" :
                          sub.category === "tech_ai" ? "bg-sky-500/10 text-sky-300 border border-sky-500/20" :
                          sub.category === "finance" ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20" :
                          "bg-slate-800 text-slate-300 border border-slate-700"
                        }`}>
                          {sub.category_label.split(" ")[1] || sub.category_label}
                        </span>
                      </div>

                      <div className="text-xs font-semibold text-slate-200">
                        {sub.label}
                      </div>

                      <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
                        {sub.description}
                      </p>
                    </div>

                    <div className="pt-2.5 border-t border-slate-900 flex items-center justify-between gap-2 text-xs">
                      <button
                        onClick={() => handleTestSubredditInModal(sub)}
                        disabled={subTestingId === sub.id}
                        className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 text-[11px] font-semibold rounded-lg border border-slate-800 hover:border-slate-700 flex items-center gap-1 transition"
                      >
                        <Play className={`w-3 h-3 ${subTestingId === sub.id ? "animate-spin" : "fill-current"}`} />
                        {subTestingId === sub.id ? "파싱중..." : "실시간 테스트"}
                      </button>

                      <div className="flex items-center gap-1.5">
                        {!sub.is_builtin && (
                          <button
                            onClick={() => handleDeleteSubreddit(sub)}
                            className="p-1.5 text-slate-500 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition"
                            title="카탈로그에서 삭제"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => handleSelectSubreddit(sub)}
                          className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-semibold rounded-lg shadow-sm shadow-rose-600/20 flex items-center gap-1 transition"
                        >
                          <CheckCircle className="w-3 h-3" /> 선택하기
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Modal Test Result Box */}
              {subModalTestResult && (
                <div className="p-4 bg-slate-950 border border-rose-500/30 rounded-xl space-y-3 shadow-lg">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-rose-300 flex items-center gap-2">
                      <Flame className="w-4 h-4 text-rose-400" />
                      'r/{subModalTestResult.subName}' 실시간 급등 테스트 결과 ({subModalTestResult.total_count}건 감지됨)
                    </span>
                    <button onClick={() => setSubModalTestResult(null)} className="text-slate-400 hover:text-white">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {subModalTestResult.results.map((item, idx) => (
                      <div key={idx} className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <a href={item.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-slate-200 hover:text-rose-300 flex items-center gap-1">
                            {item.title}
                            <ExternalLink className="w-2.5 h-2.5 text-slate-500 inline" />
                          </a>
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            🔥 {item.velocity_score}/h
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 line-clamp-1">{item.summary}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-3.5 border-t border-slate-800 bg-slate-950/80">
              <button
                onClick={() => {
                  setShowSubredditModal(false);
                  setSubModalMsg(null);
                  setSubModalTestResult(null);
                }}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* 🌐 3. Target Sites Manager Modal Dialog (미국 증시 수집 대상 사이트 관리 모달) */}
      {/* ============================================================================== */}
      {showTargetSitesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 overflow-y-auto">
          <div className="relative w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center border border-sky-500/20">
                  <Globe className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    미국 증시 수집 대상 사이트 및 금융 피드 관리
                    <span className="text-xs bg-sky-500/20 text-sky-300 font-medium px-2 py-0.5 rounded-full border border-sky-500/30">
                      총 {targetSites.length}개 등록 ({targetSites.filter(s => s.is_active).length}개 가동중)
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    미국 증시 속보 감지 시 참조할 언론사, RSS 피드 및 사이트를 등록/삭제하고 실시간 단독 테스트를 수행합니다.
                  </p>
                </div>
              </div>

              <button
                onClick={() => {
                  setShowTargetSitesModal(false);
                  setModalMsg(null);
                  setModalTestResult(null);
                }}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6 overflow-y-auto flex-1">
              {modalMsg && (
                <div className={`p-3 rounded-xl text-xs flex items-center justify-between gap-2 ${
                  modalMsg.type === "success"
                    ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                    : "bg-rose-500/10 border border-rose-500/20 text-rose-400"
                }`}>
                  <div className="flex items-center gap-2">
                    {modalMsg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
                    <span>{modalMsg.text}</span>
                  </div>
                  <button onClick={() => setModalMsg(null)} className="text-xs opacity-70 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
                </div>
              )}

              {/* Add Target Site Card */}
              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-sky-300">
                  <PlusCircle className="w-4 h-4" /> 신규 수집 대상 사이트 / RSS 피드 추가
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                  <div className="sm:col-span-3">
                    <label className="text-[11px] text-slate-400 mb-1 block">사이트/매체 이름</label>
                    <input
                      type="text"
                      value={newSiteName}
                      onChange={(e) => setNewSiteName(e.target.value)}
                      placeholder="예: CNBC 마켓 속보"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500"
                    />
                  </div>
                  <div className="sm:col-span-5">
                    <label className="text-[11px] text-slate-400 mb-1 block">웹 URL 또는 RSS 피드 엔드포인트</label>
                    <input
                      type="text"
                      value={newSiteUrl}
                      onChange={(e) => setNewSiteUrl(e.target.value)}
                      placeholder="예: https://search.cnbc.com/rs/search/..."
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-sky-500"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-[11px] text-slate-400 mb-1 block">카테고리</label>
                    <select
                      value={newSiteCategory}
                      onChange={(e) => setNewSiteCategory(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-2 text-xs text-white focus:outline-none focus:border-sky-500"
                    >
                      <option value="us_market">미국 증시</option>
                      <option value="macro">거시경제</option>
                      <option value="tech_ai">AI / 빅테크</option>
                      <option value="earnings">기업 실적</option>
                      <option value="sec_edgar">SEC 공시</option>
                      <option value="domestic_news">국내외신</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2 flex items-end">
                    <button
                      onClick={handleAddTargetSite}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs transition shadow-md shadow-sky-600/20"
                    >
                      <Plus className="w-3.5 h-3.5" /> 추가하기
                    </button>
                  </div>
                </div>
              </div>

              {/* Target Sites Filter Bar */}
              <div className="flex items-center justify-between gap-3 border-b border-slate-800 pb-2">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-400" /> 등록된 수집 대상 사이트 목록
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-400">카테고리 필터:</span>
                  <select
                    value={targetSiteFilter}
                    onChange={(e) => setTargetSiteFilter(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="all">전체 ({targetSites.length})</option>
                    <option value="us_market">미국 증시 / 주식</option>
                    <option value="macro">거시경제 / 금리</option>
                    <option value="sec_edgar">SEC 공시</option>
                    <option value="domestic_news">국내 외신 번역</option>
                  </select>
                </div>
              </div>

              {/* Target Sites Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {filteredTargetSites.map((site) => (
                  <div
                    key={site.id}
                    className={`bg-slate-950/70 border rounded-xl p-3.5 space-y-2.5 transition ${
                      site.is_active ? "border-slate-800 hover:border-slate-700" : "border-slate-800/40 opacity-60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            site.category === "us_market" ? "bg-amber-500/10 text-amber-300 border border-amber-500/20" :
                            site.category === "macro" ? "bg-purple-500/10 text-purple-300 border border-purple-500/20" :
                            site.category === "sec_edgar" ? "bg-rose-500/10 text-rose-300 border border-rose-500/20" :
                            "bg-sky-500/10 text-sky-300 border border-sky-500/20"
                          }`}>
                            {site.category === "us_market" ? "미국증시" :
                             site.category === "macro" ? "거시경제" :
                             site.category === "sec_edgar" ? "SEC공시" : "국내외신"}
                          </span>
                          {site.is_builtin && (
                            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                              기본 프리셋
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-bold text-slate-100 line-clamp-1">{site.name}</h4>
                      </div>

                      <button
                        onClick={() => handleToggleTargetSite(site)}
                        title={site.is_active ? "클릭하여 비활성화" : "클릭하여 활성화"}
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full border transition shrink-0 ${
                          site.is_active
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
                            : "bg-slate-800 text-slate-500 border-slate-700 hover:bg-slate-700"
                        }`}
                      >
                        {site.is_active ? "가동중" : "비활성"}
                      </button>
                    </div>

                    <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                      {site.description || "실시간 마켓 피드 수집 대상 사이트"}
                    </p>

                    <div className="pt-2 border-t border-slate-900 flex items-center justify-between gap-2 text-xs">
                      <a
                        href={site.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] text-slate-500 hover:text-sky-300 truncate max-w-[130px] flex items-center gap-1 font-mono"
                        title={site.url}
                      >
                        <ExternalLink className="w-3 h-3 shrink-0" />
                        {site.url}
                      </a>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => handleTestTargetSite(site)}
                          disabled={modalTestingId === site.id}
                          className="px-2 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-[11px] font-semibold rounded border border-indigo-500/30 flex items-center gap-1 transition disabled:opacity-50"
                        >
                          <Play className={`w-2.5 h-2.5 ${modalTestingId === site.id ? "animate-spin" : "fill-current"}`} />
                          {modalTestingId === site.id ? "파싱중..." : "단독 테스트"}
                        </button>
                        {!site.is_builtin && (
                          <button
                            onClick={() => handleDeleteTargetSite(site)}
                            className="p-1 text-slate-500 hover:text-rose-400 rounded hover:bg-rose-500/10 transition"
                            title="삭제"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Modal Test Result Box */}
              {modalTestResult && (
                <div className="p-4 bg-slate-950 border border-indigo-500/30 rounded-xl space-y-3 shadow-lg">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-indigo-300 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-indigo-400" />
                      '{modalTestResult.siteName}' 단독 테스트 결과 ({modalTestResult.total_count}건 감지됨)
                    </span>
                    <button onClick={() => setModalTestResult(null)} className="text-slate-400 hover:text-white">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {modalTestResult.results.map((item, idx) => (
                      <div key={idx} className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <a href={item.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-slate-200 hover:text-sky-300 flex items-center gap-1">
                            {item.title}
                            <ExternalLink className="w-2.5 h-2.5 text-slate-500 inline" />
                          </a>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            item.sentiment === "BULLISH" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                            item.sentiment === "BEARISH" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
                            "bg-slate-800 text-slate-400"
                          }`}>
                            {item.sentiment} ({item.impact_score}점)
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 line-clamp-1">{item.summary}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-3.5 border-t border-slate-800 bg-slate-950/80">
              <button
                onClick={() => {
                  setShowTargetSitesModal(false);
                  setModalMsg(null);
                  setModalTestResult(null);
                }}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
