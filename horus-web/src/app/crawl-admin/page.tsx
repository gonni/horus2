"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  api,
  CrawlSource,
  CrawlDashboardStats,
  BackfillStatus,
  CrawlTestResponse,
  ExtractedLinkItem,
  DetailedArticlePreview,
  WrapperRules,
  WrapperSynthesisResponse,
  DOMInspectItem,
  DOMContainerGroup,
  DOMInspectResponse,
  DaemonStatusResponse,
  LLMWorkerStatusResponse,
  GPUUnifiedStatusResponse,
  CrawlEventItem,
  TimeSeriesMetricsResponse,
  MultiLaneStreamResponse,
  LaneSeries
} from "@/lib/api";

import { MultiLaneStreamChart } from "@/components/MultiLaneStreamChart";
const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });
import {
  Activity,
  Calendar,
  CheckCircle,
  Database,
  Eye,
  Globe,
  Layers,
  Pause,
  Play,
  Square,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  TrendingUp,
  X,
  Zap,
  ExternalLink,
  Copy,
  Check,
  FileText,
  Clock,
  User,
  Image as ImageIcon,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  FolderTree,
  MousePointerClick,
  Tag,
  Share2,
  Sparkles,
  Wand2,
  Sliders,
  Code,
  Target,
  Crosshair,
  ListFilter,
  CheckCircle2,
  MinusCircle,
  PlusCircle,
  HelpCircle,
  Cpu,
  Flame,
  Radio
} from "lucide-react";

// React JSX 렌더링 에러(Objects are not valid as a React child) 방지용 안전 문자열 포맷터
const formatErrorMessage = (error: any, fallback: string = "오류가 발생했습니다."): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  const detail = error?.response?.data?.detail ?? error?.message ?? error;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: any) => (typeof d === "string" ? d : d.msg || JSON.stringify(d))).join(", ");
  }
  if (typeof detail === "object") {
    return JSON.stringify(detail);
  }
  return String(detail);
};

export default function CrawlAdminDashboard() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "backfill" | "seeds">("dashboard");

  // Dashboard Stats
  const [stats, setStats] = useState<CrawlDashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Seeds State
  const [sources, setSources] = useState<CrawlSource[]>([]);
  const [triggering, setTriggering] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newCategory, setNewCategory] = useState("news");
  const [newInterval, setNewInterval] = useState(15);
  const [newLinkSelector, setNewLinkSelector] = useState(".sa_text_title, .sa_text a");
  const [newContentSelector, setNewContentSelector] = useState("#dic_area, #articeBody");

  // Backfill State
  const [backfillStart, setBackfillStart] = useState("2026-08-01");
  const [backfillEnd, setBackfillEnd] = useState("2026-08-15");
  const [backfillSection, setBackfillSection] = useState("economy");
  const [backfillMaxArticles, setBackfillMaxArticles] = useState(30);
  const [backfillStatus, setBackfillStatus] = useState<BackfillStatus | null>(null);
  const [backfillPolling, setBackfillPolling] = useState(false);

  // Test / Dry-run State
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<CrawlTestResponse | null>(null);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [currentTestContentSelector, setCurrentTestContentSelector] = useState<string | undefined>(undefined);
  const [currentTestHints, setCurrentTestHints] = useState<Record<string, any>>({});
  const [linkSearchKeyword, setLinkSearchKeyword] = useState("");

  // Interactive Article Preview State
  const [selectedArticleUrl, setSelectedArticleUrl] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<DetailedArticlePreview | null>(null);
  const [articleLoading, setArticleLoading] = useState(false);
  const [articleError, setArticleError] = useState<string | null>(null);
  const [copiedContent, setCopiedContent] = useState(false);
  const [activeDetailTab, setActiveDetailTab] = useState<"parsed" | "metadata">("parsed");

  // Edit Wrapper / AI Builder State
  const [isWrapperModalOpen, setIsWrapperModalOpen] = useState(false);
  const [selectedSourceForWrapper, setSelectedSourceForWrapper] = useState<CrawlSource | null>(null);
  const [wrapperMode, setWrapperMode] = useState<"anchor" | "auto" | "manual">("anchor");
  const [wrapperModelName, setWrapperModelName] = useState("gemma4:e4b-mlx");
  const [customModelInput, setCustomModelInput] = useState(false);
  const [synthesizingWrapper, setSynthesizingWrapper] = useState(false);
  const [wrapperResult, setWrapperResult] = useState<WrapperSynthesisResponse | null>(null);
  const [wrapperError, setWrapperError] = useState<string | null>(null);
  const [editedRules, setEditedRules] = useState<WrapperRules>({
    link_selector: "",
    content_selector: "",
    title_selector: "",
    author_selector: "",
    date_selector: "",
    views_selector: "",
    category_selector: "",
    image_selector: "",
    llm_model: "gemma4:e4b-mlx",
  });
  const [testingRules, setTestingRules] = useState(false);
  const [savingWrapper, setSavingWrapper] = useState(false);
  const [wrapperStep, setWrapperStep] = useState<"step1_list" | "step2_article">("step1_list");
  const [wrapperActiveTab, setWrapperActiveTab] = useState<"rules" | "preview" | "reasoning">("rules");

  // 🔄 지속 크롤러 데몬(Continuous Daemon) 상태
  const [daemonStatus, setDaemonStatus] = useState<DaemonStatusResponse | null>(null);
  const [daemonIntervalInput, setDaemonIntervalInput] = useState<number>(60);
  const [controllingDaemon, setControllingDaemon] = useState(false);

  // 🧠 단일 직렬 GPU 작업 큐 & 텍스트/비전 듀얼 서브시스템 상태
  const [gpuStatus, setGpuStatus] = useState<GPUUnifiedStatusResponse | null>(null);
  const [textModelName, setTextModelName] = useState<string>("gemma4:e4b-mlx");
  const [visionModelName, setVisionModelName] = useState<string>("qwen3.5:2b-mlx");
  const [controllingText, setControllingText] = useState(false);
  const [controllingVision, setControllingVision] = useState(false);
  const [llmWorkerStatus, setLlmWorkerStatus] = useState<LLMWorkerStatusResponse | null>(null);
  const [selectedWorkerModel, setSelectedWorkerModel] = useState<string>("gemma4:e4b-mlx");
  const [controllingWorker, setControllingWorker] = useState(false);

  // 📊 시계열 분석 차트 & 실시간 라이브 이벤트 스트림 상태
  const [timeSeriesRange, setTimeSeriesRange] = useState<"10m" | "1h" | "1d" | "7d">("10m");
  const [timeSeriesSourceId, setTimeSeriesSourceId] = useState<string>("all");
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesMetricsResponse | null>(null);
  const [loadingTimeSeries, setLoadingTimeSeries] = useState(false);
  const [recentEvents, setRecentEvents] = useState<CrawlEventItem[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);

  // 다수 페이지(Multi-sample) 본문 및 메타데이터 자동 합성 상태
  const [synthesizingArticleMeta, setSynthesizingArticleMeta] = useState(false);
  const [articleMetaPreviews, setArticleMetaPreviews] = useState<DetailedArticlePreview[]>([]);
  const [activeArticlePreviewIndex, setActiveArticlePreviewIndex] = useState(0);

  // DOM 컨테이너 그룹화 기반 수집 영역 선택기 상태
  const [inspectedGroups, setInspectedGroups] = useState<DOMContainerGroup[]>([]);
  const [totalInspectedLinks, setTotalInspectedLinks] = useState(0);
  const [expandedGroupIds, setExpandedGroupIds] = useState<string[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [negativeAnchors, setNegativeAnchors] = useState<string[]>(["[공지]", "[안내]", "공지"]);
  const [newNegativeInput, setNewNegativeInput] = useState("");

  // 🎯 수집대상 앵커 검색 & 동일 패턴 그룹 자동 추출 상태
  const [targetAnchorSearch, setTargetAnchorSearch] = useState("");
  const [groupingByAnchor, setGroupingByAnchor] = useState(false);
  const [groupedAnchorResult, setGroupedAnchorResult] = useState<any>(null);

  // 🎯 텍스트 복사-붙여넣기 기반 셀렉터 역추적 상태
  const [reverseSnippetInput, setReverseSnippetInput] = useState("");
  const [reverseTargetField, setReverseTargetField] = useState<"content_selector" | "author_selector" | "title_selector" | "date_selector">("content_selector");
  const [runningReverse, setRunningReverse] = useState(false);
  const [reverseResultMsg, setReverseResultMsg] = useState<string | null>(null);
  const [inspectedDomLinks, setInspectedDomLinks] = useState<DOMInspectItem[]>([]);
  const [inspectingDom, setInspectingDom] = useState(false);
  const [domSearchQuery, setDomSearchQuery] = useState("");
  const [installedModels, setInstalledModels] = useState<string[]>([
    "gemma4:e4b-mlx",
    "gemma4:12b-mlx",
    "gemma4:12b",
    "qwen2.5:27b",
    "llama3.3:70b"
  ]);

  // 🖼️ Vision LLM 본문 이미지 텍스트 변환 상태
  const [enableVision, setEnableVision] = useState(false);
  const [visionModel, setVisionModel] = useState("llama3.2-vision");
  const [runningVision, setRunningVision] = useState(false);

  // 1. 통계 로드
  const fetchDashboardStats = async () => {
    try {
      const res = await api.get("/crawl/dashboard/stats");
      setStats(res.data);
    } catch (e) {
      console.error("Failed to load dashboard stats:", e);
    } finally {
      setStatsLoading(false);
    }
  };

  // 2. 소스 목록 로드
  const fetchSources = async () => {
    try {
      const res = await api.get("/crawl/sources");
      setSources(res.data);
    } catch (e) {
      console.error("Failed to load crawl sources:", e);
    }
  };

  // 3. 백필 상태 로드
  const fetchBackfillStatus = async () => {
    try {
      const res = await api.get("/crawl/backfill/status");
      setBackfillStatus(res.data);
      if (res.data.status === "running") {
        setBackfillPolling(true);
      } else {
        setBackfillPolling(false);
      }
    } catch (e) {
      console.error("Failed to fetch backfill status:", e);
    }
  };

  // 4. 지속 크롤러 데몬 상태 로드 & 제어
  const fetchDaemonStatus = async () => {
    try {
      const res = await api.get("/crawl/daemon/status");
      setDaemonStatus(res.data);
      if (res.data.interval_seconds) {
        setDaemonIntervalInput(res.data.interval_seconds);
      }
    } catch (e) {
      console.error("Failed to fetch daemon status:", e);
    }
  };

  const handleStartDaemon = async (interval?: number) => {
    setControllingDaemon(true);
    try {
      const res = await api.post("/crawl/daemon/start", {
        interval_seconds: interval || daemonIntervalInput,
      });
      setDaemonStatus(res.data);
    } catch (e: any) {
      console.error("Start daemon failed:", e);
      alert(formatErrorMessage(e, "크롤러 데몬 시작 실패"));
    } finally {
      setControllingDaemon(false);
    }
  };

  const handlePauseDaemon = async () => {
    setControllingDaemon(true);
    try {
      const res = await api.post("/crawl/daemon/pause");
      setDaemonStatus(res.data);
    } catch (e: any) {
      console.error("Pause daemon failed:", e);
    } finally {
      setControllingDaemon(false);
    }
  };

  const handleResumeDaemon = async () => {
    setControllingDaemon(true);
    try {
      const res = await api.post("/crawl/daemon/resume");
      setDaemonStatus(res.data);
    } catch (e: any) {
      console.error("Resume daemon failed:", e);
    } finally {
      setControllingDaemon(false);
    }
  };

  const handleStopDaemon = async () => {
    setControllingDaemon(true);
    try {
      const res = await api.post("/crawl/daemon/stop");
      setDaemonStatus(res.data);
    } catch (e: any) {
      console.error("Stop daemon failed:", e);
    } finally {
      setControllingDaemon(false);
    }
  };

  // 5. 단일 직렬 GPU 작업 큐 & 텍스트/비전 듀얼 서브시스템 상태 로드 & 제어
  const fetchGPUStatus = async () => {
    try {
      const res = await api.get("/crawl/gpu/status");
      setGpuStatus(res.data);
      if (res.data.text_model_name) setTextModelName(res.data.text_model_name);
      if (res.data.vision_model_name) setVisionModelName(res.data.vision_model_name);
    } catch (e) {
      console.error("Failed to fetch GPU status:", e);
    }
  };

  // 📝 텍스트 NLP 제어
  const handleStartTextWorker = async (model?: string) => {
    setControllingText(true);
    try {
      const res = await api.post("/crawl/gpu/text/start", {
        model_name: model || textModelName,
      });
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Start text worker failed:", e);
      alert(formatErrorMessage(e, "텍스트 NLP 시작 실패"));
    } finally {
      setControllingText(false);
    }
  };

  const handlePauseTextWorker = async () => {
    setControllingText(true);
    try {
      const res = await api.post("/crawl/gpu/text/pause");
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Pause text worker failed:", e);
    } finally {
      setControllingText(false);
    }
  };

  const handleResumeTextWorker = async () => {
    setControllingText(true);
    try {
      const res = await api.post("/crawl/gpu/text/resume");
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Resume text worker failed:", e);
    } finally {
      setControllingText(false);
    }
  };

  const handleStopTextWorker = async () => {
    setControllingText(true);
    try {
      const res = await api.post("/crawl/gpu/text/stop");
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Stop text worker failed:", e);
    } finally {
      setControllingText(false);
    }
  };

  // 🖼️ 비전 Image-to-Text 제어
  const handleStartVisionWorker = async (model?: string) => {
    setControllingVision(true);
    try {
      const res = await api.post("/crawl/gpu/vision/start", {
        model_name: model || visionModelName,
      });
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Start vision worker failed:", e);
      alert(formatErrorMessage(e, "비전 Image-to-Text 시작 실패"));
    } finally {
      setControllingVision(false);
    }
  };

  const handlePauseVisionWorker = async () => {
    setControllingVision(true);
    try {
      const res = await api.post("/crawl/gpu/vision/pause");
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Pause vision worker failed:", e);
    } finally {
      setControllingVision(false);
    }
  };

  const handleResumeVisionWorker = async () => {
    setControllingVision(true);
    try {
      const res = await api.post("/crawl/gpu/vision/resume");
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Resume vision worker failed:", e);
    } finally {
      setControllingVision(false);
    }
  };

  const handleStopVisionWorker = async () => {
    setControllingVision(true);
    try {
      const res = await api.post("/crawl/gpu/vision/stop");
      setGpuStatus(res.data);
    } catch (e: any) {
      console.error("Stop vision worker failed:", e);
    } finally {
      setControllingVision(false);
    }
  };

  const fetchLLMWorkerStatus = fetchGPUStatus;
  const handleStartLLMWorker = handleStartTextWorker;
  const handlePauseLLMWorker = handlePauseTextWorker;
  const handleResumeLLMWorker = handleResumeTextWorker;
  const handleStopLLMWorker = handleStopTextWorker;

  // 6. 시계열 메트릭 & 최근 이벤트 피드 로드
  const fetchTimeSeries = async (rangeParam?: string, sourceParam?: string) => {
    setLoadingTimeSeries(true);
    try {
      const r = rangeParam || timeSeriesRange;
      const s = sourceParam || timeSeriesSourceId;
      const res = await api.get(`/crawl/metrics/timeseries?range=${r}&source_id=${s}`);
      setTimeSeriesData(res.data);
    } catch (e) {
      console.error("Failed to load timeseries metrics:", e);
    } finally {
      setLoadingTimeSeries(false);
    }
  };

  const fetchRecentEvents = async () => {
    try {
      const res = await api.get("/crawl/events/recent?limit=50");
      setRecentEvents(res.data);
    } catch (e) {
      console.error("Failed to load recent events:", e);
    }
  };

  useEffect(() => {
    fetchDashboardStats();
    fetchSources();
    fetchBackfillStatus();
    fetchDaemonStatus();
    fetchLLMWorkerStatus();
    fetchTimeSeries(timeSeriesRange, timeSeriesSourceId);
    fetchRecentEvents();

    // 3초 주기 실시간 데몬/워커/시계열/이벤트 갱신
    const interval = setInterval(() => {
      if (!isWrapperModalOpen && !isTestModalOpen) {
        fetchDashboardStats();
        fetchDaemonStatus();
        fetchLLMWorkerStatus();
        fetchRecentEvents();
        fetchTimeSeries(timeSeriesRange, timeSeriesSourceId);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [isWrapperModalOpen, isTestModalOpen, timeSeriesRange, timeSeriesSourceId]);

  // 백필 폴링
  useEffect(() => {
    let timer: any;
    if (backfillPolling) {
      timer = setInterval(() => {
        fetchBackfillStatus();
        fetchDashboardStats();
      }, 2000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [backfillPolling]);

  // 소스 생성
  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/crawl/sources", {
        name: newName,
        base_url: newUrl,
        category: newCategory,
        crawl_interval_minutes: newInterval,
        ai_parsing_hints: {
          link_selector: newLinkSelector,
          content_selector: newContentSelector,
          language: "ko",
        },
      });

      setNewName("");
      setNewUrl("");
      fetchSources();
      fetchDashboardStats();
      alert("새로운 수집처(Seed)가 성공적으로 등록되었습니다.");
    } catch (e) {
      console.error("Create source failed:", e);
      alert("수집처 등록 중 오류가 발생했습니다.");
    }
  };

  // 소스 삭제
  const handleDeleteSource = async (id: number) => {
    if (!confirm("정말 이 수집처를 삭제하시겠습니까?")) return;
    try {
      await api.delete(`/crawl/sources/${id}`);
      fetchSources();
      fetchDashboardStats();
    } catch (e) {
      console.error("Delete source failed:", e);
      alert("수집처 삭제 실패");
    }
  };

  // 즉시 수집 트리거
  const handleTriggerCrawl = async (sourceId: number) => {
    setTriggering(sourceId);
    try {
      await api.post("/crawl/trigger", { source_id: sourceId });
      alert("해당 수집처의 저속 크롤링(TPS < 1) 작업이 안전하게 시작되었습니다.");
      fetchDashboardStats();
    } catch (e) {
      console.error("Trigger crawl failed:", e);
      alert("크롤링 트리거 중 오류가 발생했습니다.");
    } finally {
      setTriggering(null);
    }
  };

  // 실시간 Seed 파싱 테스트 실행
  const handleRunTest = async (url: string, linkSel?: string, contentSel?: string, hints?: Record<string, any>) => {
    if (!url) {
      alert("테스트할 URL을 입력해주세요.");
      return;
    }
    const fullHints = hints || {};
    setTesting(true);
    setTestResult(null);
    setSelectedArticle(null);
    setSelectedArticleUrl(null);
    setArticleError(null);
    setLinkSearchKeyword("");
    setCurrentTestContentSelector(contentSel);
    setCurrentTestHints(fullHints);
    setIsTestModalOpen(true);

    try {
      const res = await api.post("/crawl/test-preview", {
        url: url,
        link_selector: linkSel || fullHints.link_selector || undefined,
        content_selector: contentSel || fullHints.content_selector || undefined,
        title_selector: fullHints.title_selector || undefined,
        author_selector: fullHints.author_selector || undefined,
        date_selector: fullHints.date_selector || undefined,
        views_selector: fullHints.views_selector || undefined,
        category_selector: fullHints.category_selector || undefined,
        image_selector: fullHints.image_selector || undefined,
      });
      setTestResult(res.data);
      if (res.data.sample_article) {
        setSelectedArticle(res.data.sample_article);
        setSelectedArticleUrl(res.data.sample_article.url);
      } else if (res.data.items && res.data.items.length > 0) {
        setSelectedArticleUrl(res.data.items[0].url);
      }
    } catch (e: any) {
      console.error("Crawl test preview failed:", e);
      setTestResult({
        status: "error",
        list_url: url,
        extracted_links_count: 0,
        sample_links: [],
        items: [],
        message: e?.response?.data?.detail || "서버 통신 중 오류가 발생했습니다.",
      });
    } finally {
      setTesting(false);
    }
  };

  // 선택된 기사 실시간 On-demand 파싱
  const handleSelectArticle = async (url: string) => {
    if (selectedArticleUrl === url && selectedArticle) return;
    setSelectedArticleUrl(url);
    setArticleLoading(true);
    setArticleError(null);

    try {
      const res = await api.post("/crawl/test-article", {
        url: url,
        content_selector: currentTestHints.content_selector || currentTestContentSelector || undefined,
        title_selector: currentTestHints.title_selector || undefined,
        author_selector: currentTestHints.author_selector || undefined,
        date_selector: currentTestHints.date_selector || undefined,
        views_selector: currentTestHints.views_selector || undefined,
        category_selector: currentTestHints.category_selector || undefined,
        image_selector: currentTestHints.image_selector || undefined,
      });
      setSelectedArticle(res.data);
    } catch (e: any) {
      console.error("Fetch article preview failed:", e);
      setArticleError(e?.response?.data?.detail || "해당 기사의 본문 파싱 중 오류가 발생했습니다.");
    } finally {
      setArticleLoading(false);
    }
  };

  // 본문 클립보드 복사
  const handleCopyContent = () => {
    if (!selectedArticle?.content) return;
    navigator.clipboard.writeText(selectedArticle.content);
    setCopiedContent(true);
    setTimeout(() => setCopiedContent(false), 2000);
  };

  // Local Ollama 설치 모델 목록 실시간 조회
  const fetchInstalledModels = async () => {
    try {
      const res = await api.get("/crawl/ollama/models");
      if (res.data?.models && res.data.models.length > 0) {
        setInstalledModels(res.data.models);
        return res.data.models;
      }
    } catch (e) {
      console.warn("Failed to fetch installed Ollama models:", e);
    }
    return installedModels;
  };

  // AI Wrapper 모달 열기
  const handleOpenWrapperModal = async (src: CrawlSource) => {
    setSelectedSourceForWrapper(src);
    const models = await fetchInstalledModels();
    const hints = src.ai_parsing_hints || {};
    let model = hints.llm_model;
    if (!model) {
      if (models.includes("gemma4:12b-mlx")) model = "gemma4:12b-mlx";
      else if (models.includes("gemma4:12b")) model = "gemma4:12b";
      else model = models[0] || "gemma4:12b-mlx";
    }
    setWrapperModelName(model);
    setCustomModelInput(!models.includes(model));
    setEditedRules({
      link_selector: hints.link_selector || "",
      content_selector: hints.content_selector || "",
      title_selector: hints.title_selector || "",
      author_selector: hints.author_selector || "",
      date_selector: hints.date_selector || "",
      views_selector: hints.views_selector || "",
      category_selector: hints.category_selector || "",
      image_selector: hints.image_selector || "",
      llm_model: model,
    });
    setWrapperResult(null);
    setWrapperError(null);
    setWrapperMode("anchor");
    setNegativeAnchors(["[공지]", "[안내]", "공지"]);
    setInspectedGroups([]);
    setTotalInspectedLinks(0);
    setExpandedGroupIds([]);
    setSelectedGroupId(null);
    setInspectedDomLinks([]);
    setDomSearchQuery("");
    setWrapperStep("step1_list"); // 1단계 목록 추출부터 시작
    setWrapperActiveTab("rules");
    setArticleMetaPreviews([]);
    setActiveArticlePreviewIndex(0);
    setIsWrapperModalOpen(true);
    // 페이지 링크 DOM 스캔 자동 실행
    fetchInspectDom(src.base_url);
  };

  // 페이지 DOM 앵커 링크 및 컨테이너 그룹 스캔
  const fetchInspectDom = async (url: string) => {
    setInspectingDom(true);
    try {
      const res = await api.post("/crawl/wrapper/inspect-dom", { url });
      const groups: DOMContainerGroup[] = res.data.groups || [];
      const total = res.data.total_links || 0;
      const allItems = res.data.all_items || res.data.items || [];
      
      setInspectedGroups(groups);
      setTotalInspectedLinks(total);
      setInspectedDomLinks(allItems);

      // 추천 게시글 그룹이 있으면 기본 펼침 처리
      const probableGroups = groups.filter(g => g.is_probable_article_list).map(g => g.group_id);
      if (probableGroups.length > 0) {
        setExpandedGroupIds(probableGroups);
      } else if (groups.length > 0) {
        setExpandedGroupIds([groups[0].group_id]);
      }
    } catch (e: any) {
      console.warn("DOM inspection failed:", e);
    } finally {
      setInspectingDom(false);
    }
  };

  // 컨테이너 그룹 펼침/접기 토글
  const toggleGroupExpand = (groupId: string) => {
    if (expandedGroupIds.includes(groupId)) {
      setExpandedGroupIds(expandedGroupIds.filter(id => id !== groupId));
    } else {
      setExpandedGroupIds([...expandedGroupIds, groupId]);
    }
  };

  // 🎯 특정 DOM 그룹을 수집 대상으로 원클릭 선택 & 즉시 검증
  const handleSelectGroup = async (group: DOMContainerGroup) => {
    setSelectedGroupId(group.group_id);
    const updatedRules: WrapperRules = {
      ...editedRules,
      link_selector: group.selector
    };
    setEditedRules(updatedRules);
    await handleTestSpecificRules(updatedRules);
  };

  // 특정 규칙으로 즉시 실시간 검증 실행
  const handleTestSpecificRules = async (rulesToTest: WrapperRules) => {
    if (!selectedSourceForWrapper) return;
    setTestingRules(true);
    setWrapperError(null);
    try {
      const res = await api.post("/crawl/wrapper/test-rule", {
        url: selectedSourceForWrapper.base_url,
        rules: rulesToTest,
      });
      setWrapperResult(res.data);
      setWrapperActiveTab("preview");
      if (res.data.sample_links && res.data.sample_links.length > 0) {
        setSelectedArticleUrl(res.data.sample_links[0]);
      }
    } catch (e: any) {
      console.error("Test wrapper rules failed:", e);
      setWrapperError(formatErrorMessage(e, "규칙 테스트 중 오류가 발생했습니다."));
    } finally {
      setTestingRules(false);
    }
  };

  // 🎯 Edit Wrapper 모달 내에서 특정 기사 링크 클릭 시 On-demand 본문 및 메타 파싱
  const handleSelectArticleForWrapper = async (url: string) => {
    setSelectedArticleUrl(url);
    setArticleLoading(true);
    setArticleError(null);
    setWrapperStep("step2_article"); // 🌟 Step 2 (본문 & 메타데이터 추출) 화면으로 즉시 전환!
    setWrapperActiveTab("preview");

    try {
      const res = await api.post("/crawl/test-article", {
        url: url,
        content_selector: editedRules.content_selector || undefined,
        title_selector: editedRules.title_selector || undefined,
        author_selector: editedRules.author_selector || undefined,
        date_selector: editedRules.date_selector || undefined,
        views_selector: editedRules.views_selector || undefined,
        category_selector: editedRules.category_selector || undefined,
        image_selector: editedRules.image_selector || undefined,
        enable_vision: enableVision,
        vision_model: visionModel,
      });
      setSelectedArticle(res.data);
      if (wrapperResult) {
        setWrapperResult({
          ...wrapperResult,
          sample_article_preview: res.data,
        });
      }
    } catch (e: any) {
      console.error("Article on-demand parsing failed:", e);
      setArticleError(formatErrorMessage(e, "해당 기사의 본문 파싱 중 오류가 발생했습니다."));
    } finally {
      setArticleLoading(false);
    }
  };

  // 🖼️ 본문 첨부 이미지에 대해 Vision LLM 실행하여 텍스트 설명 생성 및 본문 주입
  const handleRunVisionForArticle = async () => {
    const currentArticle = selectedArticle || (articleMetaPreviews.length > 0 ? articleMetaPreviews[activeArticlePreviewIndex] : null);
    if (!currentArticle || !currentArticle.images || currentArticle.images.length === 0) {
      alert("분석할 본문 첨부 이미지가 없습니다.");
      return;
    }
    setRunningVision(true);
    try {
      const descriptions: Record<string, string> = { ...(currentArticle.image_descriptions || {}) };
      for (const imgUrl of currentArticle.images.slice(0, 5)) {
        if (!descriptions[imgUrl]) {
          const res = await api.post("/crawl/vision/describe-image", {
            image_url: imgUrl,
            model_name: visionModel
          });
          if (res.data?.description) {
            descriptions[imgUrl] = res.data.description;
          }
        }
      }

      // 본문 텍스트 내에 설명 주입
      let updatedContent = currentArticle.content;
      const injectedBlocks: string[] = [];
      Object.entries(descriptions).forEach(([url, desc], idx) => {
        injectedBlocks.push(`[🖼️ 첨부 이미지 #${idx + 1} 내용: ${desc}]`);
      });

      if (injectedBlocks.length > 0 && !updatedContent.includes("[🖼️ 첨부 이미지")) {
        updatedContent = updatedContent + "\n\n" + injectedBlocks.join("\n\n") + "\n\n";
      }

      const updatedArticle = {
        ...currentArticle,
        image_descriptions: descriptions,
        content: updatedContent,
        char_count: updatedContent.length
      };

      setSelectedArticle(updatedArticle);
      if (articleMetaPreviews.length > 0) {
        const nextPreviews = [...articleMetaPreviews];
        nextPreviews[activeArticlePreviewIndex] = updatedArticle;
        setArticleMetaPreviews(nextPreviews);
      }
    } catch (e: any) {
      console.error("Vision transcription failed:", e);
      alert("이미지 Vision 변환 중 오류가 발생했습니다: " + formatErrorMessage(e));
    } finally {
      setRunningVision(false);
    }
  };

  // 🌟 다수 페이지(5건 무작위) 교차 분석으로 본문 및 상세 메타데이터 규칙 자동 도출
  const handleSynthesizeArticleMeta = async () => {
    if (!wrapperResult || !wrapperResult.sample_links || wrapperResult.sample_links.length === 0) {
      alert("먼저 Step 1(목록 추출)에서 기사 링크를 탐색하거나 선택해주세요.");
      return;
    }
    setSynthesizingArticleMeta(true);
    setWrapperError(null);
    const sampleUrls = wrapperResult.sample_links; // 백엔드에서 무작위 5개 랜덤 샘플링

    try {
      const res = await api.post("/crawl/wrapper/synthesize-article-meta", {
        sample_urls: sampleUrls,
        model_name: wrapperModelName,
        base_rules: editedRules,
      });
      const generatedRules = res.data.rules;
      const updatedRules: WrapperRules = {
        ...editedRules,
        ...generatedRules,
        link_selector: editedRules.link_selector, // 기존 링크 셀렉터 유지
      };
      setEditedRules(updatedRules);
      setArticleMetaPreviews(res.data.sample_previews || []);
      if (res.data.sample_previews && res.data.sample_previews.length > 0) {
        setSelectedArticle(res.data.sample_previews[0]);
        setSelectedArticleUrl(res.data.sample_previews[0].url);
        setActiveArticlePreviewIndex(0);
      }
      setWrapperStep("step2_article");
    } catch (e: any) {
      console.error("Article metadata synthesis failed:", e);
      setWrapperError(formatErrorMessage(e, "상세 페이지 메타 분석 중 오류가 발생했습니다."));
    } finally {
      setSynthesizingArticleMeta(false);
    }
  };

  // 부정 앵커 추가
  const handleAddNegativeAnchor = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (!negativeAnchors.includes(trimmed)) {
      setNegativeAnchors([...negativeAnchors, trimmed]);
    }
    setNewNegativeInput("");
  };

  // 부정 앵커 제거
  const handleRemoveNegativeAnchor = (idx: number) => {
    setNegativeAnchors(negativeAnchors.filter((_, i) => i !== idx));
  };

  // 🎯 수집대상 앵커 검색 및 동일 패턴 그룹 1-클릭 자동 추출
  const handleGroupByAnchor = async (snippetParam?: string) => {
    const snippet = (snippetParam || targetAnchorSearch).trim();
    if (!snippet || !selectedSourceForWrapper) {
      alert("수집대상 본문 기사 제목이나 앵커 텍스트를 입력해주세요.");
      return;
    }
    setGroupingByAnchor(true);
    setGroupedAnchorResult(null);
    try {
      const res = await api.post("/crawl/wrapper/group-by-anchor", {
        url: selectedSourceForWrapper.base_url,
        target_snippet: snippet,
      });
      if (res.data.status === "success") {
        setGroupedAnchorResult(res.data);
        const updatedRules: WrapperRules = {
          ...editedRules,
          link_selector: res.data.suggested_link_selector,
        };
        setEditedRules(updatedRules);
        await handleTestSpecificRules(updatedRules);
      }
    } catch (e: any) {
      console.error("Group by anchor failed:", e);
      alert(formatErrorMessage(e, "동일 패턴 그룹 추출 중 오류가 발생했습니다."));
    } finally {
      setGroupingByAnchor(false);
    }
  };

  // 🎯 텍스트 복사-붙여넣기 기반 CSS Selector 1초 역추적 실행
  const handleReverseLookupSelector = async () => {
    if (!reverseSnippetInput.trim()) {
      alert("역추적할 텍스트 문자열을 입력해주세요.");
      return;
    }
    const targetUrl = selectedArticleUrl || (selectedSourceForWrapper ? selectedSourceForWrapper.base_url : null);
    if (!targetUrl) {
      alert("역추적 대상 상세 페이지 URL이 없습니다. 우측에서 기사를 먼저 선택해주세요.");
      return;
    }
    setRunningReverse(true);
    setReverseResultMsg(null);
    try {
      const res = await api.post("/crawl/wrapper/reverse-selector", {
        url: targetUrl,
        snippet: reverseSnippetInput.trim(),
        target_field: reverseTargetField,
      });
      const sel = res.data.suggested_selector;
      if (sel) {
        const updated = { ...editedRules, [reverseTargetField]: sel };
        setEditedRules(updated);
        setReverseResultMsg(`✅ '${sel}' (${res.data.tag_name} 태그) 도출 성공 및 적용 완료!`);
        setTimeout(() => setReverseResultMsg(null), 5000);
      }
    } catch (e: any) {
      setReverseResultMsg("❌ 역추적 실패: " + formatErrorMessage(e));
    } finally {
      setRunningReverse(false);
    }
  };

  // AI 래퍼 자동 생성 실행 (LLM 호출)
  const handleSynthesizeWrapper = async () => {
    if (!selectedSourceForWrapper) return;
    setSynthesizingWrapper(true);
    setWrapperError(null);
    try {
      const res = await api.post("/crawl/wrapper/synthesize", {
        source_id: selectedSourceForWrapper.id,
        url: selectedSourceForWrapper.base_url,
        model_name: wrapperModelName,
      });
      setWrapperResult(res.data);
      setEditedRules(res.data.rules);
      
      // 도출된 link_selector와 일치하는 DOM 그룹이 있으면 자동 선택
      if (res.data.rules?.link_selector) {
        const matchedGroup = inspectedGroups.find(g => g.selector === res.data.rules.link_selector);
        if (matchedGroup) {
          setSelectedGroupId(matchedGroup.group_id);
          setExpandedGroupIds(prev => Array.from(new Set([...prev, matchedGroup.group_id])));
        }
      }

      if (res.data.sample_article_preview) {
        setSelectedArticle(res.data.sample_article_preview);
        setSelectedArticleUrl(res.data.sample_article_preview.url);
      }
    } catch (e: any) {
      console.error("AI wrapper synthesis failed:", e);
      const errDetail = e?.response?.data?.detail || "AI 래퍼 분석 중 오류가 발생했습니다.";
      setWrapperError(errDetail);
    } finally {
      setSynthesizingWrapper(false);
    }
  };

  // 래퍼 규칙 실시간 검증 테스트
  const handleTestWrapperRules = async () => {
    if (!selectedSourceForWrapper) return;
    setTestingRules(true);
    setWrapperError(null);
    try {
      const res = await api.post("/crawl/wrapper/test-rule", {
        url: selectedSourceForWrapper.base_url,
        rules: editedRules,
      });
      setWrapperResult(res.data);
      setWrapperActiveTab("preview");
    } catch (e: any) {
      console.error("Test wrapper rules failed:", e);
      const errDetail = e?.response?.data?.detail || "규칙 테스트 중 오류가 발생했습니다.";
      setWrapperError(errDetail);
    } finally {
      setTestingRules(false);
    }
  };

  // 검증된 규칙을 Seed DB에 영구 저장
  const handleSaveWrapperRules = async () => {
    if (!selectedSourceForWrapper) return;
    setSavingWrapper(true);
    try {
      await api.put(`/crawl/sources/${selectedSourceForWrapper.id}/wrapper`, {
        rules: editedRules,
      });
      alert(`'${selectedSourceForWrapper.name}'에 AI 래퍼 규칙이 성공적으로 저장되었습니다.`);
      fetchSources();
      fetchDashboardStats();
      setIsWrapperModalOpen(false);
    } catch (e: any) {
      console.error("Save wrapper rules failed:", e);
      alert(e?.response?.data?.detail || "규칙 저장 중 오류가 발생했습니다.");
    } finally {
      setSavingWrapper(false);
    }
  };

  // 백필 시작
  const handleStartBackfill = async () => {
    try {
      const res = await api.post("/crawl/backfill", {
        start_date: backfillStart,
        end_date: backfillEnd,
        section: backfillSection,
        max_articles_per_day: backfillMaxArticles,
      });
      setBackfillStatus(res.data);
      setBackfillPolling(true);
    } catch (e) {
      console.error("Start backfill failed:", e);
      alert("백필 작업 시작 중 오류가 발생했습니다.");
    }
  };

  // 백필 중지
  const handleStopBackfill = async () => {
    try {
      await api.post("/crawl/backfill/stop");
      fetchBackfillStatus();
    } catch (e) {
      console.error("Stop backfill failed:", e);
    }
  };

  // ECharts 시계열 차트 옵션 빌더
  const getEChartsOption = () => {
    if (!timeSeriesData || !timeSeriesData.timestamps) return {};
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.95)",
        borderColor: "#334155",
        textStyle: { color: "#f8fafc", fontSize: 12 },
        axisPointer: { type: "cross", label: { backgroundColor: "#1e293b" } },
      },
      legend: {
        data: [
          "Seed 스캔 (Seed Scan)",
          "신규 기사 (Articles)",
          "본문 이미지 (Images)",
          "LLM 정제 완료 (LLM Enriched)",
        ],
        textStyle: { color: "#94a3b8", fontSize: 11 },
        top: 0,
        right: 10,
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "3%",
        top: "40px",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: timeSeriesData.timestamps,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#64748b", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#1e293b" } },
        axisLabel: { color: "#64748b", fontSize: 11 },
      },
      series: [
        {
          name: "Seed 스캔 (Seed Scan)",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          data: timeSeriesData.seed_scans,
          itemStyle: { color: "#a855f7" }, // Purple
          lineStyle: { width: 2, color: "#a855f7" },
        },
        {
          name: "신규 기사 (Articles)",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(16, 185, 129, 0.35)" },
                { offset: 1, color: "rgba(16, 185, 129, 0.0)" },
              ],
            },
          },
          data: timeSeriesData.articles_ingested,
          itemStyle: { color: "#10b981" }, // Emerald
          lineStyle: { width: 2.5, color: "#10b981" },
        },
        {
          name: "본문 이미지 (Images)",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          data: timeSeriesData.images_ingested,
          itemStyle: { color: "#f59e0b" }, // Amber
          lineStyle: { width: 2, color: "#f59e0b" },
        },
        {
          name: "LLM 정제 완료 (LLM Enriched)",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(6, 182, 212, 0.35)" },
                { offset: 1, color: "rgba(6, 182, 212, 0.0)" },
              ],
            },
          },
          data: timeSeriesData.llm_enriched,
          itemStyle: { color: "#06b6d4" }, // Cyan
          lineStyle: { width: 2.5, color: "#06b6d4" },
        },
      ],
    };
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 상단 헤더 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Activity className="w-7 h-7 text-indigo-400" />
            HorusEyes 2.0 스마트 크롤러 & 백필 대시보드
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            저속 크롤링(TPS ≤ 1.0) DDoS 방지 제어, 과거 누락 데이터 복구(Backfill), 수집 Seed 관리 및 실시간 파싱 테스트
          </p>
        </div>

        {/* 탭 네비게이션 */}
        <div className="flex items-center gap-1.5 bg-slate-900/80 p-1 border border-slate-800 rounded-lg self-start">
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition flex items-center gap-1.5 ${
              activeTab === "dashboard"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            수집 모니터링
          </button>
          <button
            onClick={() => setActiveTab("backfill")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition flex items-center gap-1.5 ${
              activeTab === "backfill"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            누락 일자 백필 (Backfill)
          </button>
          <button
            onClick={() => setActiveTab("seeds")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition flex items-center gap-1.5 ${
              activeTab === "seeds"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            Seed 사이트 관리 & 테스트
          </button>
        </div>
      </div>

      {/* 1급 요구사항 상태 뱃지 배너 */}
      <div className="bg-slate-900 border border-emerald-500/30 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5">
          <span className="flex h-2.5 w-2.5 relative">
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500 shadow-[0_0_6px_rgba(52,211,153,0.8)]"></span>
          </span>
          <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
            <ShieldCheck className="w-4 h-4" />
            1급 요구사항: 저속 크롤링(Slow Rate Limiter) 정상 가동 중
          </div>
          <span className="text-slate-400 hidden sm:inline">
            | {stats?.rate_limit_policy || "TPS ≤ 1.0 (최소 1.5초 딜레이 + Random Jitter)"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-400">
            현재 크롤러 속도: <strong className="text-white font-mono">{stats?.current_tps || 0.0} TPS</strong>
          </span>
          <button
            onClick={() => {
              fetchDashboardStats();
              fetchSources();
            }}
            className="text-slate-400 hover:text-white p-1"
            title="새로고침"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 탭 1: 수집 모니터링 대시보드 */}
      {activeTab === "dashboard" && (
        <div className="space-y-6">
          {/* 상단 듀얼 제어 허브: 2단 배치 (1단: 크롤러 데몬, 2단: GPU 단일 직렬 큐 워커) */}
          <div className="space-y-4">
            {/* 1단 (상단): 🔄 주기적 지속 크롤러 데몬 (Full-Width Responsive Bar) */}
            <div className="bg-slate-900 border border-indigo-500/30 rounded-xl p-4 md:p-5 relative overflow-hidden shadow-lg">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                {/* 좌측: 타이틀 & 상태 뱃지 */}
                <div className="flex items-center gap-3 min-w-[260px]">
                  <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-indigo-400">
                    <Activity className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white flex items-center gap-2">
                      주기적 지속 크롤러 데몬
                      {daemonStatus?.state === "RUNNING" && (
                        <span className="px-2 py-0.5 text-[11px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full font-semibold flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.8)]" />
                          수집 가동 중 ({daemonStatus.interval_seconds}초 주기)
                        </span>
                      )}
                      {daemonStatus?.state === "PAUSED" && (
                        <span className="px-2 py-0.5 text-[11px] bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full font-semibold">
                          일시 중단됨
                        </span>
                      )}
                      {(!daemonStatus || daemonStatus.state === "IDLE" || daemonStatus.state === "STOPPED") && (
                        <span className="px-2 py-0.5 text-[11px] bg-slate-800 text-slate-400 border border-slate-700 rounded-full">
                          정지 상태
                        </span>
                      )}
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      모든 활성 Seed를 주기적으로 폴링하여 신규 글만 탐색 및 고속 적재 (0% GPU)
                    </p>
                  </div>
                </div>

                {/* 중앙: 3개 상태 지표 */}
                <div className="grid grid-cols-3 gap-2 md:gap-3 bg-slate-950/70 border border-slate-800 rounded-lg p-2.5 text-xs flex-1 max-w-xl">
                  <div>
                    <div className="text-slate-500 text-[10px] md:text-[11px]">다음 수집 주기까지</div>
                    <div className="text-base md:text-lg font-bold font-mono text-emerald-400 mt-0.5">
                      {daemonStatus?.state === "RUNNING" ? `${daemonStatus.seconds_to_next_cycle || 0}초` : "-"}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500 text-[10px] md:text-[11px]">누적 수집 회차</div>
                    <div className="text-base md:text-lg font-bold font-mono text-white mt-0.5">
                      {daemonStatus?.cycle_count || 0}
                      <span className="text-xs text-slate-500 font-normal ml-0.5">회</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500 text-[10px] md:text-[11px]">현재 스캔 대상</div>
                    <div className="text-xs md:text-sm font-semibold text-indigo-300 truncate mt-1" title={daemonStatus?.current_running_seed_name || ""}>
                      {daemonStatus?.current_running_seed_name || (daemonStatus?.state === "RUNNING" ? "대기 중" : "정지")}
                    </div>
                  </div>
                </div>

                {/* 우측: 수집 주기 설정 & 제어 버튼 */}
                <div className="flex items-center gap-3 self-end lg:self-center">
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="text-slate-400 text-xs">주기:</span>
                    <input
                      type="number"
                      min={10}
                      max={600}
                      step={10}
                      value={daemonIntervalInput}
                      onChange={(e) => setDaemonIntervalInput(Number(e.target.value))}
                      disabled={controllingDaemon}
                      className="w-14 px-1.5 py-1 bg-slate-950 border border-slate-700 rounded text-center text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
                    />
                    <span className="text-slate-400 text-xs">초</span>
                    {daemonStatus?.state === "RUNNING" && daemonIntervalInput !== daemonStatus.interval_seconds && (
                      <button
                        onClick={() => handleStartDaemon(daemonIntervalInput)}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-indigo-400 text-[11px] font-medium rounded border border-indigo-500/30"
                      >
                        적용
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {daemonStatus?.state !== "RUNNING" ? (
                      <button
                        onClick={() => handleStartDaemon()}
                        disabled={controllingDaemon}
                        className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow transition disabled:opacity-50"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        {daemonStatus?.state === "PAUSED" ? "수집 재개" : "지속 수집 시작"}
                      </button>
                    ) : (
                      <button
                        onClick={handlePauseDaemon}
                        disabled={controllingDaemon}
                        className="px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/40 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-50"
                      >
                        <Pause className="w-3.5 h-3.5" />
                        일시 중단
                      </button>
                    )}

                    <button
                      onClick={handleStopDaemon}
                      disabled={controllingDaemon || (!daemonStatus || daemonStatus.state === "STOPPED" || daemonStatus.state === "IDLE")}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 border border-slate-700 hover:border-rose-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-30"
                    >
                      <Square className="w-3 h-3 fill-current" />
                      완전 정지
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* 2단 (하단): 🧠 단일 직렬 GPU 작업 큐 & 듀얼 서브시스템 (텍스트 NLP & 비전 Image-to-Text) 제어 허브 */}
            <div className="bg-slate-900 border border-purple-500/30 rounded-xl p-4 md:p-5 relative overflow-hidden shadow-lg space-y-4">
              {/* 상단 통합 헤더 & 직렬 큐 상태 */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">
                    <Cpu className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white flex items-center gap-2">
                      GPU 단일 직렬 작업 큐 워커
                      <span className="px-2 py-0.5 text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full font-bold flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_5px_rgba(192,132,252,0.8)]" />
                        단일 GPU 순차 실행 (Ollama 충돌 방지)
                      </span>
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      텍스트 NLP와 비전 이미지 처리를 분리 제어하며, GPU에서는 1건씩 안전하게 Serial FIFO로 처리합니다.
                    </p>
                  </div>
                </div>

                {/* 현재 실행 중인 작업 표시 */}
                <div className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs flex items-center gap-2">
                  <span className="text-slate-500">현재 GPU 처리:</span>
                  {gpuStatus?.current_task ? (
                    <span className="text-purple-300 font-semibold flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_6px_rgba(192,132,252,0.9)]" />
                      [{gpuStatus.current_task.type === "vision" ? "🖼️ 비전" : "📝 텍스트"}] {gpuStatus.current_task.title}
                    </span>
                  ) : (
                    <span className="text-slate-400 font-mono">대기 중 (IDLE)</span>
                  )}
                </div>
              </div>

              {/* 듀얼 서브시스템 2단 분리 제어 영역 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* [서브시스템 1]: 📝 텍스트 NLP 데이터 정제 */}
                <div className="p-3.5 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-purple-300">
                      <FileText className="w-4 h-4 text-purple-400" />
                      1. 텍스트 NLP 정제 (요약/감성/엔티티)
                    </div>
                    {gpuStatus?.text_state === "RUNNING" && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded font-semibold">
                        🟢 NLP 가동
                      </span>
                    )}
                    {gpuStatus?.text_state === "PAUSED" && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded font-semibold">
                        🟡 일시중지
                      </span>
                    )}
                    {(!gpuStatus || gpuStatus.text_state === "IDLE" || gpuStatus.text_state === "STOPPED") && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-slate-800 text-slate-400 rounded">
                        ⚪ 정지
                      </span>
                    )}
                  </div>

                  {/* 텍스트 큐 수치 */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-slate-900/90 p-2 rounded-lg border border-slate-800">
                      <div className="text-[10px] text-slate-500">Text 대기 큐</div>
                      <div className="text-base font-bold font-mono text-amber-400">
                        {gpuStatus?.text_pending_count || 0}건
                      </div>
                    </div>
                    <div className="bg-slate-900/90 p-2 rounded-lg border border-slate-800">
                      <div className="text-[10px] text-slate-500">정제 완료</div>
                      <div className="text-base font-bold font-mono text-purple-400">
                        {gpuStatus?.text_processed_count || 0}건
                      </div>
                    </div>
                  </div>

                  {/* 텍스트 제어 버튼 & 모델 */}
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <select
                      value={textModelName}
                      onChange={(e) => {
                        setTextModelName(e.target.value);
                        if (gpuStatus?.text_state === "RUNNING") handleStartTextWorker(e.target.value);
                      }}
                      className="bg-slate-900 border border-slate-700 text-purple-300 rounded px-2 py-1 text-[11px] focus:outline-none"
                    >
                      {installedModels.map((m) => (
                        <option key={m} value={m}>
                          {m} {m.includes("e4b") ? "(추천)" : ""}
                        </option>
                      ))}
                    </select>

                    <div className="flex items-center gap-1.5">
                      {gpuStatus?.text_state !== "RUNNING" ? (
                        <button
                          onClick={() => handleStartTextWorker()}
                          disabled={controllingText}
                          className="px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1 shadow transition disabled:opacity-50"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          {gpuStatus?.text_state === "PAUSED" ? "재개" : "시작"}
                        </button>
                      ) : (
                        <button
                          onClick={handlePauseTextWorker}
                          disabled={controllingText}
                          className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1 shadow transition disabled:opacity-50"
                          title="텍스트 NLP 작업을 일시 중지합니다"
                        >
                          <Pause className="w-3 h-3" />
                          일시중지
                        </button>
                      )}

                      <button
                        onClick={handleStopTextWorker}
                        disabled={controllingText || (!gpuStatus || gpuStatus.text_state === "STOPPED" || gpuStatus.text_state === "IDLE")}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg text-xs transition disabled:opacity-30"
                      >
                        <Square className="w-2.5 h-2.5 fill-current" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* [서브시스템 2]: 🖼️ 비전 Image-to-Text (캡셔닝 & 본문 주입) */}
                <div className="p-3.5 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-300">
                      <Eye className="w-4 h-4 text-cyan-400" />
                      2. 비전 Image-to-Text (본문 주입)
                    </div>
                    {gpuStatus?.vision_state === "RUNNING" && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 rounded font-semibold">
                        🟢 비전 가동
                      </span>
                    )}
                    {gpuStatus?.vision_state === "PAUSED" && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded font-semibold">
                        🟡 일시중지
                      </span>
                    )}
                    {(!gpuStatus || gpuStatus.vision_state === "IDLE" || gpuStatus.vision_state === "STOPPED") && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-slate-800 text-slate-400 rounded">
                        ⚪ 정지
                      </span>
                    )}
                  </div>

                  {/* 비전 큐 수치 */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-slate-900/90 p-2 rounded-lg border border-slate-800">
                      <div className="text-[10px] text-slate-500">Image 대기 큐</div>
                      <div className="text-base font-bold font-mono text-cyan-400">
                        {gpuStatus?.vision_pending_count || 0}건
                      </div>
                    </div>
                    <div className="bg-slate-900/90 p-2 rounded-lg border border-slate-800">
                      <div className="text-[10px] text-slate-500">캡셔닝 완료</div>
                      <div className="text-base font-bold font-mono text-emerald-400">
                        {gpuStatus?.vision_processed_count || 0}건
                      </div>
                    </div>
                  </div>

                  {/* 비전 제어 버튼 & 모델 */}
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <select
                      value={visionModelName}
                      onChange={(e) => {
                        setVisionModelName(e.target.value);
                        if (gpuStatus?.vision_state === "RUNNING") handleStartVisionWorker(e.target.value);
                      }}
                      className="bg-slate-900 border border-slate-700 text-cyan-300 rounded px-2 py-1 text-[11px] focus:outline-none"
                    >
                      {installedModels.map((m) => (
                        <option key={m} value={m}>
                          {m} {m.includes("2b") || m.includes("4b") ? "(경량 비전)" : ""}
                        </option>
                      ))}
                    </select>

                    <div className="flex items-center gap-1.5">
                      {gpuStatus?.vision_state !== "RUNNING" ? (
                        <button
                          onClick={() => handleStartVisionWorker()}
                          disabled={controllingVision}
                          className="px-2.5 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1 shadow transition disabled:opacity-50"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          {gpuStatus?.vision_state === "PAUSED" ? "재개" : "시작"}
                        </button>
                      ) : (
                        <button
                          onClick={handlePauseVisionWorker}
                          disabled={controllingVision}
                          className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1 shadow transition disabled:opacity-50"
                          title="비전 Image-to-Text 작업을 일시 중지합니다"
                        >
                          <Pause className="w-3 h-3" />
                          일시중지
                        </button>
                      )}

                      <button
                        onClick={handleStopVisionWorker}
                        disabled={controllingVision || (!gpuStatus || gpuStatus.vision_state === "STOPPED" || gpuStatus.vision_state === "IDLE")}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg text-xs transition disabled:opacity-30"
                      >
                        <Square className="w-2.5 h-2.5 fill-current" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* 하단 안내 배지 */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 bg-slate-950/40 p-2 rounded-lg border border-slate-800">
                <span className="flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  이미지 파일은 메모리에서 텍스트 변환 후 즉시 삭제(용량 0MB 부담)되며, 원본 절대 URL은 메타데이터에 보존됩니다.
                </span>
                <span className="font-mono text-slate-400">
                  전체 DB 기사: <strong className="text-white">{gpuStatus?.total_articles || 0}</strong>건
                </span>
              </div>
            </div>
          </div>

          {/* 다차원 실시간 Horizon 스트림 & 실시간 활동 스트림 피드 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 좌측 (2 Cols): 🌊 MultiLane Horizon 실시간 스트림 파형 (Image 2 스타일) */}
            <div className="lg:col-span-2">
              <MultiLaneStreamChart
                initialRange={timeSeriesRange}
                autoRefreshInterval={2000}
                onRangeChange={(r) => {
                  setTimeSeriesRange(r);
                  fetchTimeSeries(r, timeSeriesSourceId);
                }}
              />
            </div>

            {/* 우측 (1 Col): 🔴 실시간 시각화 활동 스트림 (Live Activity Ticker) */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3 flex flex-col">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
                <div className="flex items-center gap-2">
                  <Radio className="w-4 h-4 text-rose-400" />
                  <h2 className="text-sm font-bold text-white">
                    실시간 수집 활동 스트림
                  </h2>
                </div>
                <span className="text-[11px] text-slate-400 flex items-center gap-1.5 font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.8)]" />
                  Live (3초 갱신)
                </span>
              </div>

              {/* 실시간 이벤트 목록 */}
              <div className="flex-1 overflow-y-auto max-h-[310px] space-y-2.5 pr-1 text-xs">
                {recentEvents.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-2.5 bg-slate-950/60 border border-slate-800/80 rounded-lg space-y-1.5 hover:border-slate-700 transition"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        {ev.event_type === "seed_scan" && (
                          <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded text-[10px] font-bold">
                            SEED
                          </span>
                        )}
                        {ev.event_type === "article_ingest" && (
                          <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded text-[10px] font-bold">
                            기사
                          </span>
                        )}
                        {ev.event_type === "image_ingest" && (
                          <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded text-[10px] font-bold">
                            이미지
                          </span>
                        )}
                        {ev.event_type === "llm_enrich" && (
                          <span className="px-1.5 py-0.5 bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 rounded text-[10px] font-bold">
                            LLM 정제
                          </span>
                        )}
                        <span className="text-slate-400 font-medium text-[11px] truncate max-w-[100px]">
                          {ev.source_name || "수집원"}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(ev.created_at).toLocaleTimeString("ko-KR")}
                      </span>
                    </div>

                    <div className="text-slate-200 font-medium line-clamp-1">
                      {ev.url ? (
                        <a href={ev.url} target="_blank" rel="noreferrer" className="hover:text-indigo-400 transition">
                          {ev.title}
                        </a>
                      ) : (
                        ev.title
                      )}
                    </div>

                    {/* 이미지 썸네일 미리보기 */}
                    {ev.image_url && (
                      <div className="pt-1">
                        <img
                          src={ev.image_url}
                          alt="미디어 썸네일"
                          className="h-14 w-auto rounded border border-slate-700 object-cover max-w-full"
                          onError={(e: any) => { e.currentTarget.style.display = "none"; }}
                        />
                      </div>
                    )}

                    {/* LLM 요약 미리보기 */}
                    {ev.event_type === "llm_enrich" && ev.details?.summary_preview && (
                      <div className="text-[11px] text-slate-400 bg-slate-900/80 p-1.5 rounded border border-slate-800">
                        {ev.details.summary_preview}...
                      </div>
                    )}
                  </div>
                ))}

                {recentEvents.length === 0 && (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    아직 기록된 실시간 수집 이벤트가 없습니다. 지속 수집을 가동해보세요.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* KPI 카드 4종 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                <span>누적 수집 기사</span>
                <Database className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="text-2xl font-extrabold text-white font-mono">
                {stats?.total_articles.toLocaleString() || 0}
                <span className="text-xs font-normal text-slate-500 ml-1">건</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">PostgreSQL 파티션 테이블 저장</p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                <span>오늘 수집된 기사</span>
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-extrabold text-white font-mono">
                {stats?.today_articles.toLocaleString() || 0}
                <span className="text-xs font-normal text-slate-500 ml-1">건</span>
              </div>
              <p className="text-[11px] text-emerald-500/80 mt-1">실시간 파이프라인 수집분</p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                <span>활성 Seed 수집처</span>
                <Globe className="w-4 h-4 text-sky-400" />
              </div>
              <div className="text-2xl font-extrabold text-white font-mono">
                {stats?.active_sources_count || 0}
                <span className="text-xs font-normal text-slate-500 ml-1">개</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">네이버 뉴스 및 주요 소스</p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                <span>실시간 안전 TPS</span>
                <Zap className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-2xl font-extrabold text-amber-400 font-mono">
                {stats?.current_tps || 0.0}
                <span className="text-xs font-normal text-slate-500 ml-1">req/sec</span>
              </div>
              <p className="text-[11px] text-amber-500/80 mt-1">DDoS 방지 한계치(1.0) 이하 준수</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 최근 수집된 기사 실시간 Live Feed */}
            <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  실시간 수집 피드 (Live Article Feed)
                </h2>
                <span className="text-xs text-slate-500">최신 10건</span>
              </div>

              <div className="divide-y divide-slate-800/60">
                {stats?.recent_articles.map((art) => (
                  <div key={art.id} className="py-3 flex items-start justify-between gap-4">
                    <div className="space-y-1 min-w-0">
                      <a
                        href={art.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-medium text-slate-200 hover:text-indigo-400 transition line-clamp-1"
                      >
                        {art.title}
                      </a>
                      <div className="flex items-center gap-2 text-[11px] text-slate-500">
                        <span className="text-slate-400 font-medium">{art.author}</span>
                        <span>•</span>
                        <span className="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-[10px]">
                          {art.category}
                        </span>
                        <span>•</span>
                        <span>발행: {new Date(art.published_at).toLocaleString("ko-KR")}</span>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-mono ${
                          art.sentiment_score > 0.1
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : art.sentiment_score < -0.1
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {art.sentiment_score > 0 ? `+${art.sentiment_score.toFixed(2)}` : art.sentiment_score.toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))}

                {(!stats || stats.recent_articles.length === 0) && (
                  <div className="py-8 text-center text-slate-500 text-xs">
                    아직 수집된 기사가 없습니다. Seed 수집을 시작하거나 백필을 가동하세요.
                  </div>
                )}
              </div>
            </div>

            {/* 수집 소스 요약 현황 */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Globe className="w-4 h-4 text-indigo-400" />
                등록된 수집 Seed 상태 ({sources.length}개)
              </h2>
              <div className="space-y-3">
                {sources.map((src) => (
                  <div
                    key={src.id}
                    className="p-3 bg-slate-800/40 border border-slate-800/80 rounded-lg flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-white truncate">{src.name}</div>
                      <div className="text-[11px] text-slate-400 truncate">{src.base_url}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        주기: {src.crawl_interval_minutes}분 | {src.category}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => handleRunTest(src.base_url, src.ai_parsing_hints?.link_selector, src.ai_parsing_hints?.content_selector, src.ai_parsing_hints)}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded text-[11px] font-medium transition"
                        title="파싱 테스트"
                      >
                        <Eye className="w-3 h-3 inline mr-1" />
                        테스트
                      </button>
                      <button
                        onClick={() => handleTriggerCrawl(src.id)}
                        disabled={triggering === src.id}
                        className="px-2 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-400 border border-indigo-500/30 rounded text-[11px] font-medium transition"
                      >
                        {triggering === src.id ? "수집 중..." : "즉시수집"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 탭 2: 누락 일자 백필 (Backfill) 컨트롤러 */}
      {activeTab === "backfill" && (
        <div className="space-y-6">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-6">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Calendar className="w-5 h-5 text-indigo-400" />
                네이버 뉴스 과거 누락 일자 복구 (Backfill Engine)
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                시스템이 중단되었던 과거 날짜 범위를 지정하면, 네이버 날짜별 아카이브를 저속(TPS ≤ 1.0)으로 안전하게 순회하며 기수집 기사는 건너뛰고 누락분만 수집합니다.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1.5 font-medium">복구 시작일 (Start Date)</label>
                <input
                  type="date"
                  value={backfillStart}
                  onChange={(e) => setBackfillStart(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1.5 font-medium">복구 종료일 (End Date)</label>
                <input
                  type="date"
                  value={backfillEnd}
                  onChange={(e) => setBackfillEnd(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1.5 font-medium">대상 섹션</label>
                <select
                  value={backfillSection}
                  onChange={(e) => setBackfillSection(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="economy">네이버 경제 (sid1=101)</option>
                  <option value="tech">네이버 IT/과학 (sid1=105)</option>
                  <option value="society">네이버 사회 (sid1=102)</option>
                  <option value="politics">네이버 정치 (sid1=100)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1.5 font-medium">일별 최대 수집 건수</label>
                <input
                  type="number"
                  value={backfillMaxArticles}
                  onChange={(e) => setBackfillMaxArticles(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleStartBackfill}
                disabled={backfillStatus?.status === "running"}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition disabled:opacity-50 flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                백필 작업 시작 (TPS &lt; 1.0 저속 안전 모드)
              </button>

              {backfillStatus?.status === "running" && (
                <button
                  onClick={handleStopBackfill}
                  className="px-4 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg transition flex items-center gap-2"
                >
                  <Pause className="w-4 h-4" />
                  백필 중단
                </button>
              )}
            </div>

            {/* 백필 실시간 진행 상태 모니터 */}
            {backfillStatus && (
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        backfillStatus.status === "running"
                          ? "bg-amber-400 animate-pulse"
                          : backfillStatus.status === "completed"
                          ? "bg-emerald-400"
                          : "bg-slate-500"
                      }`}
                    />
                    <span className="font-semibold text-white uppercase tracking-wider">
                      상태: {backfillStatus.status}
                    </span>
                  </div>
                  <span className="text-slate-400 font-mono">
                    진행률: {backfillStatus.processed_days} / {backfillStatus.total_days} 일
                  </span>
                </div>

                {/* 프로그레스 바 */}
                <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-indigo-500 h-2.5 rounded-full transition-all duration-500"
                    style={{
                      width: `${
                        backfillStatus.total_days > 0
                          ? Math.min(100, Math.round((backfillStatus.processed_days / backfillStatus.total_days) * 100))
                          : 0
                      }%`,
                    }}
                  />
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">현재 처리 일자</div>
                    <div className="text-base font-bold text-white font-mono mt-1">
                      {backfillStatus.current_date || "-"}
                    </div>
                  </div>
                  <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">신규 저장 완료</div>
                    <div className="text-base font-bold text-emerald-400 font-mono mt-1">
                      {backfillStatus.saved_count} 건
                    </div>
                  </div>
                  <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">기등록 스킵</div>
                    <div className="text-base font-bold text-slate-400 font-mono mt-1">
                      {backfillStatus.skipped_count} 건
                    </div>
                  </div>
                  <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">현재 수집 속도</div>
                    <div className="text-base font-bold text-amber-400 font-mono mt-1">
                      {backfillStatus.current_tps} TPS
                    </div>
                  </div>
                </div>

                <div className="text-xs text-slate-400 bg-slate-900/60 p-2.5 rounded border border-slate-800 font-mono">
                  메시지: {backfillStatus.last_message}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 탭 3: 수집 Seed 사이트 관리자 & 실시간 테스트 */}
      {activeTab === "seeds" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 등록된 Seed 목록 */}
          <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Globe className="w-4 h-4 text-indigo-400" />
                등록된 수집 대상 사이트 (Seed 목록 - {sources.length}개)
              </h2>
              <button
                onClick={fetchSources}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" /> 새로고침
              </button>
            </div>

            <div className="space-y-3">
              {sources.map((src) => (
                <div
                  key={src.id}
                  className="p-4 bg-slate-800/40 border border-slate-800 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white text-sm">{src.name}</span>
                      <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded uppercase font-semibold">
                        {src.category}
                      </span>
                      <span className="text-xs text-slate-500">주기: {src.crawl_interval_minutes}분</span>
                    </div>
                    <a
                      href={src.base_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-mono text-indigo-400 hover:underline block truncate"
                    >
                      {src.base_url}
                    </a>
                    <div className="text-[11px] text-slate-400 font-mono flex flex-wrap gap-x-4 bg-slate-950/60 p-2 rounded border border-slate-800/60">
                      <div>
                        <span className="text-slate-500">링크 셀렉터:</span>{" "}
                        <span className="text-indigo-300">{src.ai_parsing_hints?.link_selector || "자동 감지"}</span>
                      </div>
                      <div>
                        <span className="text-slate-500">본문 셀렉터:</span>{" "}
                        <span className="text-emerald-300">{src.ai_parsing_hints?.content_selector || "자동 추출"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 self-end sm:self-center flex-wrap">
                    <button
                      onClick={() => handleOpenWrapperModal(src)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 rounded-md text-xs font-semibold transition"
                      title="AI 래퍼 생성 및 추출 규칙 편집 (Edit Wrapper)"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                      Edit Wrapper
                    </button>
                    <button
                      onClick={() => handleRunTest(src.base_url, src.ai_parsing_hints?.link_selector, src.ai_parsing_hints?.content_selector, src.ai_parsing_hints)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-md text-xs font-semibold transition"
                      title="실제 사이트 접속 파싱 테스트"
                    >
                      <Eye className="w-3.5 h-3.5 text-sky-400" />
                      파싱 테스트
                    </button>
                    <button
                      onClick={() => handleTriggerCrawl(src.id)}
                      disabled={triggering === src.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 rounded-md text-xs font-semibold transition disabled:opacity-50"
                    >
                      <Play className="w-3.5 h-3.5" />
                      {triggering === src.id ? "수집 중..." : "즉시 수집"}
                    </button>
                    <button
                      onClick={() => handleDeleteSource(src.id)}
                      className="p-1.5 text-slate-500 hover:text-rose-400 transition"
                      title="삭제"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 신규 Seed 등록 폼 & 실시간 테스트 패널 */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Plus className="w-4 h-4 text-indigo-400" />
              신규 Seed 사이트 등록 & 테스트
            </h2>

            <form onSubmit={handleCreateSource} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1 font-medium">사이트 이름</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="예: 네이버 증권 주요 뉴스"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">목록 URL (Base URL)</label>
                <input
                  type="url"
                  required
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://news.naver.com/..."
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1 font-medium">카테고리</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="news">뉴스 (news)</option>
                    <option value="community">커뮤니티 (community)</option>
                    <option value="stock">주식/증권 (stock)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 font-medium">수집 주기 (분)</label>
                  <input
                    type="number"
                    value={newInterval}
                    onChange={(e) => setNewInterval(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">
                  기사 링크 영역 (CSS Selector)
                </label>
                <input
                  type="text"
                  value={newLinkSelector}
                  onChange={(e) => setNewLinkSelector(e.target.value)}
                  placeholder=".sa_text a, ul.type06_headline a"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
                />
                <span className="text-[10px] text-slate-500 mt-0.5 block">
                  목록 페이지에서 기사 링크들만 위치하는 특정 CSS 선택자
                </span>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">
                  본문 추출 영역 (CSS Selector)
                </label>
                <input
                  type="text"
                  value={newContentSelector}
                  onChange={(e) => setNewContentSelector(e.target.value)}
                  placeholder="#dic_area, #articeBody"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="pt-2 flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => handleRunTest(newUrl, newLinkSelector, newContentSelector)}
                  className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-indigo-500/30 font-semibold rounded-lg transition flex items-center justify-center gap-1.5"
                >
                  <Eye className="w-3.5 h-3.5" />
                  입력한 설정으로 파싱 테스트 실행 (Dry-run)
                </button>

                <button
                  type="submit"
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition shadow"
                >
                  Seed 사이트 저장하기
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 파싱 테스트 결과 모달 (Enhanced Dry-run Preview & Interactive Article Inspector) */}
      {isTestModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-2 sm:p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-6xl h-[92vh] flex flex-col overflow-hidden shadow-xl">
            {/* 모달 헤더 */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60 shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-indigo-400">
                  <Eye className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    Seed 실시간 파싱 테스트 & 기사 인스펙터
                  </h3>
                  <p className="text-xs text-slate-400">
                    탐색된 링크의 메타정보 확인 및 개별 기사 On-demand 본문/메타데이터 정밀 파싱
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsTestModalOpen(false)}
                className="text-slate-400 hover:text-white p-1.5 hover:bg-slate-800 rounded-lg transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 모달 본문 */}
            <div className="flex-1 overflow-hidden flex flex-col p-4 space-y-4 text-xs">
              {testing && (
                <div className="my-auto py-16 text-center space-y-3">
                  <RefreshCw className="w-9 h-9 text-indigo-400 animate-spin mx-auto" />
                  <p className="text-slate-200 text-sm font-semibold">대상 사이트에 접속하여 목록 및 메타데이터를 수집하고 있습니다...</p>
                  <p className="text-slate-400 text-xs">TPS ≤ 1.0 저속 크롤링 정책 준수 중</p>
                </div>
              )}

              {!testing && testResult && (
                <>
                  {/* 상단 상태 배너 */}
                  <div
                    className={`p-3 rounded-xl border shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                      testResult.status === "success"
                        ? "bg-emerald-950/30 border-emerald-500/30 text-emerald-300"
                        : "bg-rose-950/30 border-rose-500/30 text-rose-300"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{testResult.message}</span>
                    </div>
                    <div className="text-[11px] opacity-80 truncate font-mono text-slate-400">
                      수집 URL: {testResult.list_url}
                    </div>
                  </div>

                  {/* 2단 분할 레이아웃 */}
                  <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-4">
                    {/* 좌측/상단: 탐색된 기사 링크 목록 (4.5 컬럼) */}
                    <div className="lg:col-span-5 flex flex-col bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden min-h-0">
                      {/* 목록 헤더 & 검색 */}
                      <div className="p-3 border-b border-slate-800 bg-slate-900/60 space-y-2 shrink-0">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-white flex items-center gap-1.5">
                            <Layers className="w-4 h-4 text-indigo-400" />
                            탐색된 기사 목록 ({testResult.extracted_links_count}건)
                          </span>
                          <span className="text-[11px] text-indigo-300 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-500/30">
                            클릭 시 실시간 파싱
                          </span>
                        </div>
                        <div className="relative">
                          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
                          <input
                            type="text"
                            value={linkSearchKeyword}
                            onChange={(e) => setLinkSearchKeyword(e.target.value)}
                            placeholder="제목, 앵커 텍스트, 언론사 검색..."
                            className="w-full pl-8 pr-3 py-1.5 bg-slate-900 border border-slate-700/80 rounded-lg text-slate-200 placeholder-slate-500 text-xs focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                      </div>

                      {/* 링크 리스트 스크롤 영역 */}
                      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
                        {testResult.items && testResult.items.length > 0 ? (
                          testResult.items
                            .filter((item) => {
                              if (!linkSearchKeyword.trim()) return true;
                              const kw = linkSearchKeyword.toLowerCase();
                              return (
                                (item.title && item.title.toLowerCase().includes(kw)) ||
                                (item.anchor_text && item.anchor_text.toLowerCase().includes(kw)) ||
                                (item.press && item.press.toLowerCase().includes(kw)) ||
                                item.url.toLowerCase().includes(kw)
                              );
                            })
                            .map((item, idx) => {
                              const isSelected = selectedArticleUrl === item.url;
                              return (
                                <div
                                  key={idx}
                                  onClick={() => handleSelectArticle(item.url)}
                                  className={`p-2.5 rounded-lg border transition cursor-pointer text-left flex gap-2.5 ${
                                    isSelected
                                      ? "bg-indigo-950/50 border-indigo-500/70 shadow-sm"
                                      : "bg-slate-900/60 border-slate-800/80 hover:bg-slate-800/60 hover:border-slate-700"
                                  }`}
                                >
                                  {/* 썸네일 (있는 경우) */}
                                  {item.thumbnail ? (
                                    <div className="w-14 h-14 shrink-0 rounded-md overflow-hidden bg-slate-800 border border-slate-700/60">
                                      <img
                                        src={item.thumbnail}
                                        alt=""
                                        className="w-full h-full object-cover"
                                        onError={(e) => {
                                          (e.target as HTMLElement).style.display = "none";
                                        }}
                                      />
                                    </div>
                                  ) : (
                                    <div className="w-6 h-6 shrink-0 rounded bg-slate-800 text-slate-500 flex items-center justify-center font-mono text-[10px] font-bold">
                                      {idx + 1}
                                    </div>
                                  )}

                                  {/* 메타 콘텐츠 */}
                                  <div className="flex-1 min-w-0 space-y-1">
                                    <div className="flex items-start justify-between gap-1">
                                      <div
                                        className={`font-semibold text-xs line-clamp-2 leading-snug ${
                                          isSelected ? "text-indigo-300 font-bold" : "text-slate-200"
                                        }`}
                                      >
                                        {item.title || item.anchor_text || "제목 없음"}
                                      </div>
                                      <a
                                        href={item.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-slate-500 hover:text-indigo-400 p-0.5 shrink-0"
                                        title="새 탭에서 원본 열기"
                                      >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                      </a>
                                    </div>

                                    {item.snippet && (
                                      <p className="text-[11px] text-slate-400 line-clamp-1">
                                        {item.snippet}
                                      </p>
                                    )}

                                    <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                                      {item.press && (
                                        <span className="bg-slate-800 text-slate-300 px-1.5 py-0.2 rounded font-sans font-medium">
                                          {item.press}
                                        </span>
                                      )}
                                      {item.time_text && <span>{item.time_text}</span>}
                                      {isSelected && (
                                        <span className="text-emerald-400 font-semibold flex items-center gap-0.5 ml-auto">
                                          <Check className="w-3 h-3" /> 선택됨
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              );
                            })
                        ) : (
                          <div className="text-slate-500 text-center py-8">
                            추출된 링크가 없습니다.
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 우측/하단: 선택된 기사 상세 파싱 인스펙터 (7.5 컬럼) */}
                    <div className="lg:col-span-7 flex flex-col bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden min-h-0">
                      {/* 인스펙터 헤더 & 탭 */}
                      <div className="p-3 border-b border-slate-800 bg-slate-900/60 flex flex-wrap items-center justify-between gap-2 shrink-0">
                        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                          <button
                            onClick={() => setActiveDetailTab("parsed")}
                            className={`px-3 py-1 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                              activeDetailTab === "parsed"
                                ? "bg-indigo-600 text-white"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            <FileText className="w-3.5 h-3.5" />
                            정제 본문
                          </button>
                          <button
                            onClick={() => setActiveDetailTab("metadata")}
                            className={`px-3 py-1 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                              activeDetailTab === "metadata"
                                ? "bg-indigo-600 text-white"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            <Tag className="w-3.5 h-3.5" />
                            메타데이터 & OpenGraph
                          </button>
                        </div>

                        {selectedArticle && (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={handleCopyContent}
                              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-md text-xs font-medium transition flex items-center gap-1.5"
                            >
                              {copiedContent ? (
                                <>
                                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                                  <span className="text-emerald-400">복사됨!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3.5 h-3.5" />
                                  <span>본문 복사</span>
                                </>
                              )}
                            </button>
                            <a
                              href={selectedArticle.url}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1 text-slate-400 hover:text-white bg-slate-800 border border-slate-700 rounded-md"
                              title="새 창에서 원본 보기"
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        )}
                      </div>

                      {/* 인스펙터 본문 스크롤 영역 */}
                      <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {articleLoading && (
                          <div className="py-20 text-center space-y-3">
                            <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin mx-auto" />
                            <p className="text-slate-300 font-medium">선택된 기사의 본문 및 메타데이터를 파싱하고 있습니다...</p>
                          </div>
                        )}

                        {articleError && (
                          <div className="p-4 bg-rose-950/40 border border-rose-500/30 rounded-lg text-rose-300 space-y-1">
                            <div className="font-semibold">기사 파싱 실패</div>
                            <div className="text-xs text-rose-400">{articleError}</div>
                          </div>
                        )}

                        {!articleLoading && !articleError && selectedArticle && (
                          <>
                            {/* 기사 헤더 요약 정보 */}
                            <div className="space-y-2 pb-3 border-b border-slate-800">
                              <h4 className="text-base sm:text-lg font-bold text-white leading-snug">
                                {selectedArticle.title}
                              </h4>

                              {/* 메타데이터 뱃지 바 */}
                              <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400 font-mono">
                                {(selectedArticle.publisher || selectedArticle.author) && (
                                  <span className="flex items-center gap-1 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-slate-300">
                                    <User className="w-3 h-3 text-indigo-400" />
                                    {selectedArticle.publisher || selectedArticle.author}
                                  </span>
                                )}
                                {selectedArticle.published_at && (
                                  <span className="flex items-center gap-1 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-slate-400">
                                    <Clock className="w-3 h-3 text-sky-400" />
                                    {selectedArticle.published_at}
                                  </span>
                                )}
                                <span className="flex items-center gap-1 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-emerald-400">
                                  <FileText className="w-3 h-3" />
                                  {selectedArticle.char_count.toLocaleString()} 자
                                </span>
                                <span className="flex items-center gap-1 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-amber-400">
                                  <Clock className="w-3 h-3" />
                                  약 {selectedArticle.reading_time_minutes}분 소요
                                </span>
                                <span className="bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-slate-500">
                                  HTML: {selectedArticle.raw_html_size_kb} KB
                                </span>
                              </div>
                            </div>

                            {/* 탭 1: 정제된 본문 */}
                            {activeDetailTab === "parsed" && (
                              <div className="space-y-4">
                                {/* 대표 이미지 (있는 경우) */}
                                {selectedArticle.image_url && (
                                  <div className="rounded-lg overflow-hidden border border-slate-800 max-h-56 bg-slate-900 flex items-center justify-center">
                                    <img
                                      src={selectedArticle.image_url}
                                      alt="대표 이미지"
                                      className="max-h-56 w-full object-contain"
                                      onError={(e) => {
                                        (e.target as HTMLElement).style.display = "none";
                                      }}
                                    />
                                  </div>
                                )}

                                {/* 요약문 (있는 경우) */}
                                {selectedArticle.summary && (
                                  <div className="p-3 bg-indigo-950/20 border-l-2 border-indigo-500 rounded-r-lg text-slate-300 text-xs italic leading-relaxed">
                                    {selectedArticle.summary}
                                  </div>
                                )}

                                {/* 정제된 본문 텍스트 */}
                                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800 text-slate-200 text-xs leading-relaxed whitespace-pre-wrap font-sans selection:bg-indigo-600 selection:text-white">
                                  {selectedArticle.content || selectedArticle.content_preview || (
                                    <span className="text-slate-500">추출된 본문 텍스트가 없습니다.</span>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* 탭 2: 메타데이터 & OpenGraph */}
                            {activeDetailTab === "metadata" && (
                              <div className="space-y-3 font-mono text-[11px]">
                                <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden divide-y divide-slate-800/80">
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">URL</span>
                                    <span className="sm:col-span-2 text-indigo-300 break-all">{selectedArticle.url}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">표준 URL (Canonical)</span>
                                    <span className="sm:col-span-2 text-slate-300 break-all">{selectedArticle.canonical_url || "-"}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">og:title</span>
                                    <span className="sm:col-span-2 text-slate-200">{selectedArticle.title}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">og:site_name / 언론사</span>
                                    <span className="sm:col-span-2 text-slate-300">{selectedArticle.og_site_name || selectedArticle.publisher || "-"}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">og:description</span>
                                    <span className="sm:col-span-2 text-slate-300 font-sans">{selectedArticle.og_description || "-"}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">og:image</span>
                                    <span className="sm:col-span-2 text-sky-400 break-all">{selectedArticle.image_url || "-"}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">발행일시</span>
                                    <span className="sm:col-span-2 text-slate-300">{selectedArticle.published_at || "-"}</span>
                                  </div>
                                  <div className="p-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <span className="text-slate-500">본문 이미지 수</span>
                                    <span className="sm:col-span-2 text-emerald-400">{selectedArticle.images?.length || 0} 개 탐색됨</span>
                                  </div>
                                </div>
                              </div>
                            )}
                          </>
                        )}

                        {!articleLoading && !selectedArticle && !articleError && (
                          <div className="py-20 text-center text-slate-500">
                            좌측 목록에서 기사를 선택해 주세요.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* 모달 하단 푸터 */}
            <div className="p-3 border-t border-slate-800 flex items-center justify-between bg-slate-950/60 shrink-0">
              <span className="text-[11px] text-slate-500 font-mono">
                HorusEyes 2.0 AI Parsing Engine • Slow Rate Limiter Active
              </span>
              <button
                onClick={() => setIsTestModalOpen(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI Wrapper Builder (Edit Wrapper Modal) */}
      {isWrapperModalOpen && selectedSourceForWrapper && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-2 sm:p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-6xl h-[92vh] flex flex-col overflow-hidden shadow-xl">
            {/* 모달 헤더 */}
            <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-950/60 shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg text-purple-400">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    AI 래퍼 빌더 (Edit Wrapper)
                    <span className="text-xs bg-slate-800 text-purple-300 px-2 py-0.5 rounded font-normal">
                      {selectedSourceForWrapper.name}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400 font-mono truncate max-w-md">
                    {selectedSourceForWrapper.base_url}
                  </p>
                </div>
              </div>

              {/* 모델 선택 & 자동 생성 액션 */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700 px-2.5 py-1 rounded-lg text-xs">
                  <Sliders className="w-3.5 h-3.5 text-purple-400" />
                  <span className="text-slate-400">모델:</span>
                  <select
                    value={customModelInput ? "custom" : wrapperModelName}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === "custom") {
                        setCustomModelInput(true);
                      } else {
                        setCustomModelInput(false);
                        setWrapperModelName(val);
                      }
                    }}
                    className="bg-transparent text-white font-mono text-xs focus:outline-none cursor-pointer"
                  >
                    <optgroup label="Local Ollama 설치 모델">
                      {installedModels.map((m) => (
                        <option key={m} value={m} className="bg-slate-900 text-white font-mono">
                          {m} {m.includes("12b") ? "🌟 (기본·고성능)" : (m.includes("e4b") ? "⚡ (초고속)" : "")}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="기타 옵션">
                      <option value="gemini-2.0-flash" className="bg-slate-900 text-white font-mono">
                        Gemini 2.0 Flash (Cloud)
                      </option>
                      <option value="custom" className="bg-slate-900 text-white font-mono">
                        직접 모델명 입력...
                      </option>
                    </optgroup>
                  </select>

                  {customModelInput && (
                    <input
                      type="text"
                      value={wrapperModelName}
                      onChange={(e) => setWrapperModelName(e.target.value)}
                      placeholder="모델명 직접 입력"
                      className="bg-slate-800 text-white font-mono px-2 py-0.5 rounded text-xs w-32 border border-slate-700 focus:outline-none focus:border-purple-500 ml-1"
                    />
                  )}
                </div>

                <button
                  onClick={() => setIsWrapperModalOpen(false)}
                  className="text-slate-400 hover:text-white p-1.5 hover:bg-slate-800 rounded-lg transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* 모달 본문 */}
            <div className="flex-1 overflow-hidden p-4 flex flex-col gap-3 text-xs">
              {/* 에러 안내 배너 (있는 경우) */}
              {wrapperError && (
                <div className="bg-rose-950/60 border border-rose-500/40 rounded-xl p-3 flex items-start justify-between gap-3 text-rose-200 text-xs shrink-0">
                  <div className="space-y-1">
                    <span className="font-bold flex items-center gap-1.5 text-rose-300">
                      <X className="w-4 h-4 text-rose-400" />
                      규칙 처리/테스트 중 안내 사항:
                    </span>
                    <p className="font-mono text-[11px] leading-relaxed text-rose-100 whitespace-pre-wrap">
                      {wrapperError}
                    </p>
                  </div>
                  <button
                    onClick={() => setWrapperError(null)}
                    className="text-rose-400 hover:text-white p-1"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* 🌟 2단계(2-Step) 상단 스텝 전환 탭 */}
              <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/90 p-2.5 rounded-xl border border-slate-800 shrink-0">
                <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
                  <button
                    type="button"
                    onClick={() => setWrapperStep("step1_list")}
                    className={`px-3.5 py-1.5 rounded-md text-xs font-bold transition flex items-center gap-2 ${
                      wrapperStep === "step1_list"
                        ? "bg-purple-600 text-white shadow-lg shadow-purple-900/40"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <ListFilter className="w-3.5 h-3.5" />
                    <span>Step 1. (A) 게시글 목록(List) 추출 영역</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setWrapperStep("step2_article")}
                    className={`px-3.5 py-1.5 rounded-md text-xs font-bold transition flex items-center gap-2 ${
                      wrapperStep === "step2_article"
                        ? "bg-purple-600 text-white shadow-lg shadow-purple-900/40"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Step 2. (B) 본문 & 메타데이터(Meta) 정밀 추출 영역</span>
                  </button>
                </div>

                <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                  {wrapperStep === "step1_list" ? (
                    <span className="text-slate-300">
                      탐색된 링크: <strong className="text-purple-300">{wrapperResult?.sample_links_count || inspectedDomLinks.length}</strong>건
                    </span>
                  ) : (
                    <span className="text-slate-300">
                      추출 메타 필드: <strong className="text-emerald-300">제목·작성자·작성일·조회수·본문·이미지</strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Step 1: (A) 게시글 목록(List) 추출 영역 */}
              {wrapperStep === "step1_list" && (
                <div className="flex-1 overflow-hidden flex flex-col gap-3">
                  {/* 🎯 스마트 타겟 앵커 검색 & 동일 패턴 그룹 1-클릭 자동 추출 (공지/광고/사이드바 원천 배제) */}
                  <div className="bg-gradient-to-r from-red-950/40 via-purple-950/40 to-slate-900 p-3.5 rounded-xl border border-red-500/40 flex flex-col gap-2.5 shrink-0 shadow-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="p-1.5 rounded-lg bg-red-500/20 text-red-400">
                          <Target className="w-4 h-4" />
                        </span>
                        <div>
                          <span className="font-bold text-white text-xs flex items-center gap-1.5">
                            수집대상 앵커 검색 & 동일 패턴 그룹 자동 추출
                            <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 text-[10px] font-mono">공지/광고/사이드바 배제</span>
                          </span>
                          <p className="text-[11px] text-slate-300">
                            수집하려는 일반 본문 글 제목(예: <code className="text-red-300 bg-red-950/60 px-1 py-0.5 rounded">질문안받습니다</code>, <code className="text-red-300 bg-red-950/60 px-1 py-0.5 rounded">에이스 힘 좃노</code>)을 입력하면, 상단 공지와 사이드바를 제외한 <strong>동일 패턴 본문 기사들만 1-Click 자동 묶기</strong>를 실행합니다.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-2">
                      <div className="relative flex-1">
                        <input
                          type="text"
                          value={targetAnchorSearch}
                          onChange={(e) => setTargetAnchorSearch(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              handleGroupByAnchor();
                            }
                          }}
                          placeholder="예: 질문안받습니다, 금융위기발 비트코인, 에이스 힘 좃노 등 글제목 입력..."
                          className="w-full pl-8 pr-3 py-2 bg-slate-950 border border-red-500/30 rounded-lg text-white text-xs focus:outline-none focus:border-red-400 placeholder:text-slate-500 font-medium"
                        />
                        <Search className="w-3.5 h-3.5 text-red-400 absolute left-2.5 top-2.5" />
                      </div>

                      <button
                        type="button"
                        onClick={() => handleGroupByAnchor()}
                        disabled={groupingByAnchor || !targetAnchorSearch.trim()}
                        className="px-4 py-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white text-xs font-bold rounded-lg transition shadow-md shadow-red-950/50 flex items-center justify-center gap-1.5 shrink-0 disabled:opacity-50"
                      >
                        {groupingByAnchor ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>동일 패턴 그룹 분석 중...</span>
                          </>
                        ) : (
                          <>
                            <Layers className="w-3.5 h-3.5" />
                            <span>🎯 동일 패턴 그룹 불러오기</span>
                          </>
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={handleSynthesizeWrapper}
                        disabled={synthesizingWrapper || testingRules}
                        className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-purple-500/40 text-purple-300 hover:text-white text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 shrink-0 disabled:opacity-50"
                      >
                        {synthesizingWrapper ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>AI 자동 탐색 중...</span>
                          </>
                        ) : (
                          <>
                            <Wand2 className="w-3.5 h-3.5" />
                            <span>AI 전체 탐색</span>
                          </>
                        )}
                      </button>
                    </div>

                    {/* 빠른 샘플 칩 (DOM 스캔된 링크 중 4개 자동 추천) */}
                    {inspectedDomLinks.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                        <span className="text-[11px] text-slate-400 flex items-center gap-1 shrink-0">
                          <Sparkles className="w-3 h-3 text-amber-400" />
                          빠른 선택:
                        </span>
                        {inspectedDomLinks
                          .filter(it => !it.is_notice && it.anchor_text.length >= 4 && !it.anchor_text.includes("공지") && !it.anchor_text.includes("AD"))
                          .slice(0, 4)
                          .map((it, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => {
                                setTargetAnchorSearch(it.anchor_text);
                                handleGroupByAnchor(it.anchor_text);
                              }}
                              className="px-2 py-0.5 bg-slate-900/90 hover:bg-red-950/80 border border-slate-700 hover:border-red-500/50 text-slate-300 hover:text-white rounded text-[11px] truncate max-w-[220px] transition text-left"
                            >
                              {it.anchor_text}
                            </button>
                          ))}
                      </div>
                    )}

                    {groupedAnchorResult && (
                      <div className="p-2 bg-emerald-950/50 border border-emerald-500/40 rounded-lg flex flex-wrap items-center justify-between gap-2 text-xs text-emerald-300">
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                          <span>
                            <strong>'{groupedAnchorResult.target_anchor}'</strong>와 동일 패턴 본문 기사 <strong>{groupedAnchorResult.matched_count}건</strong> 추출 완료!
                            <span className="text-[11px] text-emerald-400/80 ml-2 font-mono">({groupedAnchorResult.suggested_link_selector})</span>
                          </span>
                        </div>
                        {groupedAnchorResult.excluded_notices_count > 0 && (
                          <span className="text-[11px] bg-amber-950/60 border border-amber-500/40 text-amber-300 px-2 py-0.5 rounded shrink-0">
                            공지/광고 {groupedAnchorResult.excluded_notices_count}건 자동 배제됨
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-12 gap-4">
                    {/* 좌측 6 컬럼: DOM 컨테이너 그룹 선택기 & 링크 규칙 */}
                    <div className="lg:col-span-6 flex flex-col bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden min-h-0">
                    <div className="p-3 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between shrink-0">
                      <span className="font-semibold text-white flex items-center gap-1.5 text-xs">
                        <FolderTree className="w-3.5 h-3.5 text-purple-400" />
                        탐색된 DOM 컨테이너 그룹 ({inspectedGroups.length}개)
                      </span>
                      <button
                        type="button"
                        onClick={() => fetchInspectDom(selectedSourceForWrapper.base_url)}
                        disabled={inspectingDom}
                        className="text-[11px] text-purple-300 hover:text-white flex items-center gap-1 transition"
                      >
                        <RefreshCw className={`w-3 h-3 ${inspectingDom ? "animate-spin" : ""}`} />
                        다시 스캔
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5">
                      {/* 제외할 텍스트 키워드 */}
                      <div className="space-y-2 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <label className="block font-semibold text-amber-400 flex items-center justify-between text-xs">
                          <span className="flex items-center gap-1">
                            <MinusCircle className="w-3.5 h-3.5" />
                            제외할 텍스트 키워드 (공지·운영자 등)
                          </span>
                          <span className="text-[10px] text-slate-400 font-normal">선택 사항</span>
                        </label>

                        <div className="flex flex-wrap gap-1.5 min-h-[28px] p-1.5 bg-slate-950/80 rounded-lg border border-slate-800">
                          {negativeAnchors.map((tag, idx) => (
                            <span
                              key={idx}
                              className="bg-amber-950/80 border border-amber-500/40 text-amber-200 px-2 py-0.5 rounded text-xs flex items-center gap-1 font-medium"
                            >
                              <span>{tag}</span>
                              <button
                                type="button"
                                onClick={() => handleRemoveNegativeAnchor(idx)}
                                className="text-amber-400 hover:text-amber-100"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </span>
                          ))}
                        </div>

                        <div className="flex gap-1.5">
                          <input
                            type="text"
                            value={newNegativeInput}
                            onChange={(e) => setNewNegativeInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                handleAddNegativeAnchor(newNegativeInput);
                              }
                            }}
                            placeholder="예: [공지], [안내], [베타]..."
                            className="flex-1 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs focus:outline-none focus:border-amber-500"
                          />
                          <button
                            type="button"
                            onClick={() => handleAddNegativeAnchor(newNegativeInput)}
                            className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shrink-0"
                          >
                            추가
                          </button>
                        </div>
                      </div>

                      {/* 검색 필터 */}
                      <input
                        type="text"
                        value={domSearchQuery}
                        onChange={(e) => setDomSearchQuery(e.target.value)}
                        placeholder="컨테이너명 또는 글 제목으로 검색..."
                        className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-purple-500"
                      />

                      {/* DOM 컨테이너 그룹 리스트 */}
                      <div className="space-y-2">
                        {inspectingDom ? (
                          <div className="py-12 text-center text-slate-400 flex flex-col items-center justify-center gap-2">
                            <RefreshCw className="w-6 h-6 animate-spin text-purple-400" />
                            <span className="text-xs">페이지의 전체 DOM 앵커 링크 및 컨테이너 노드를 분석하고 있습니다...</span>
                          </div>
                        ) : inspectedGroups.length > 0 ? (
                          inspectedGroups
                            .filter((g) => {
                              if (!domSearchQuery) return true;
                              const query = domSearchQuery.toLowerCase();
                              return (
                                g.container_tag.toLowerCase().includes(query) ||
                                g.selector.toLowerCase().includes(query) ||
                                g.items.some((it) => it.anchor_text.toLowerCase().includes(query))
                              );
                            })
                            .map((group) => {
                              const isExpanded = expandedGroupIds.includes(group.group_id);
                              const isSelected = selectedGroupId === group.group_id || editedRules.link_selector === group.selector;

                              return (
                                <div
                                  key={group.group_id}
                                  className={`rounded-xl border transition overflow-hidden ${
                                    isSelected
                                      ? "bg-purple-950/40 border-purple-500/60 shadow-md shadow-purple-950/50"
                                      : group.is_probable_article_list
                                      ? "bg-slate-900/90 border-purple-500/30 hover:border-purple-500/50"
                                      : "bg-slate-900/40 border-slate-800 hover:border-slate-700"
                                  }`}
                                >
                                  <div className="p-3 flex items-start justify-between gap-2.5">
                                    <div className="space-y-1 min-w-0 flex-1">
                                      <div className="flex items-center gap-2">
                                        <span className="font-bold text-white text-xs truncate">
                                          {group.display_name}
                                        </span>
                                        <span className="bg-purple-950 text-purple-300 text-[10px] px-1.5 py-0.2 rounded border border-purple-500/30 shrink-0 font-mono">
                                          링크 {group.link_count}개
                                        </span>
                                      </div>
                                      <div className="text-[10px] text-slate-400 font-mono truncate">
                                        Selector: <span className="text-purple-300">{group.selector}</span>
                                      </div>
                                    </div>

                                    <div className="flex items-center gap-1.5 shrink-0">
                                      <button
                                        type="button"
                                        onClick={() => toggleGroupExpand(group.group_id)}
                                        className="p-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 text-xs transition flex items-center gap-1"
                                        title={isExpanded ? "목록 접기" : "하위 앵커 텍스트 전체 보기"}
                                      >
                                        <span className="text-[10px]">목록</span>
                                        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                                      </button>

                                      <button
                                        type="button"
                                        onClick={() => handleSelectGroup(group)}
                                        disabled={testingRules}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                                          isSelected
                                            ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/40"
                                            : "bg-purple-600 hover:bg-purple-500 text-white shadow-md shadow-purple-900/30"
                                        }`}
                                      >
                                        {isSelected ? (
                                          <>
                                            <Check className="w-3.5 h-3.5" />
                                            <span>선택됨</span>
                                          </>
                                        ) : (
                                          <>
                                            <MousePointerClick className="w-3.5 h-3.5" />
                                            <span>🎯 이 영역 선택</span>
                                          </>
                                        )}
                                      </button>
                                    </div>
                                  </div>

                                  {isExpanded && (
                                    <div className="border-t border-slate-800/80 bg-slate-950/90 p-2.5 space-y-1.5">
                                      <div className="text-[11px] text-slate-400 font-semibold flex items-center justify-between pb-1">
                                        <span>하위 앵커 텍스트 목록 (총 {group.items.length}건):</span>
                                        <span className="text-[10px] text-slate-500">클릭 시 즉시 본문 파싱</span>
                                      </div>

                                      <div className="max-h-48 overflow-y-auto space-y-1 pr-1 font-sans">
                                        {group.items.map((item, idx) => {
                                          const isSelectedArticle = selectedArticleUrl === item.url;
                                          return (
                                            <div
                                              key={idx}
                                              onClick={() => handleSelectArticleForWrapper(item.url)}
                                              className={`p-1.5 rounded border flex items-start justify-between gap-2 text-xs cursor-pointer transition ${
                                                isSelectedArticle
                                                  ? "bg-purple-950/60 border-purple-500/80 shadow"
                                                  : "bg-slate-900/80 hover:bg-slate-900 border-slate-800/60 hover:border-purple-500/40"
                                              }`}
                                            >
                                              <div className="min-w-0 flex-1">
                                                <div className="text-slate-200 text-[11px] leading-snug flex items-center gap-1">
                                                  {item.is_notice && (
                                                    <span className="bg-amber-950 text-amber-300 text-[9px] px-1 py-0.2 rounded border border-amber-500/30 shrink-0">
                                                      공지
                                                    </span>
                                                  )}
                                                  <span className={`truncate font-medium ${isSelectedArticle ? "text-purple-300" : ""}`}>
                                                    {item.anchor_text}
                                                  </span>
                                                </div>
                                                <div className="text-[9px] text-slate-500 font-mono truncate">{item.url}</div>
                                              </div>
                                              <div className="flex items-center gap-1 shrink-0">
                                                <button
                                                  type="button"
                                                  title="이 기사와 동일한 패턴 그룹 자동 묶기"
                                                  onClick={(e) => {
                                                    e.stopPropagation();
                                                    setTargetAnchorSearch(item.anchor_text);
                                                    handleGroupByAnchor(item.anchor_text);
                                                  }}
                                                  className="px-1.5 py-0.5 rounded bg-red-950/80 hover:bg-red-800 border border-red-500/40 text-red-300 hover:text-white text-[10px] flex items-center gap-1 font-medium transition"
                                                >
                                                  <Layers className="w-2.5 h-2.5" />
                                                  <span>동일패턴</span>
                                                </button>
                                                <a
                                                  href={item.url}
                                                  target="_blank"
                                                  rel="noreferrer"
                                                  onClick={(e) => e.stopPropagation()}
                                                  className="text-slate-500 hover:text-white p-0.5"
                                                >
                                                  <ExternalLink className="w-3 h-3" />
                                                </a>
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })
                        ) : (
                          <div className="py-8 text-center text-slate-500 space-y-2">
                            <ListFilter className="w-8 h-8 mx-auto text-slate-600 opacity-60" />
                            <p className="text-xs">상단의 [다시 스캔] 버튼을 눌러 페이지 링크 구조를 탐색하세요.</p>
                          </div>
                        )}
                      </div>

                      {/* 링크 셀렉터 수동 조정 */}
                      <div className="pt-2 border-t border-slate-800 space-y-2">
                        <label className="block text-slate-400 text-xs font-semibold">
                          적용된 게시글 목록 셀렉터 (link_selector)
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={editedRules.link_selector || ""}
                            onChange={(e) => setEditedRules({ ...editedRules, link_selector: e.target.value })}
                            placeholder=".board_list a, .sa_text_title"
                            className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                          />
                          <button
                            type="button"
                            onClick={handleTestWrapperRules}
                            disabled={testingRules}
                            className="px-3.5 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1 shrink-0"
                          >
                            <Play className="w-3.5 h-3.5" />
                            <span>검증</span>
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Step 1 하단 다음 단계 이동 액션 바 */}
                    <div className="p-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
                      <span className="text-[11px] text-slate-400">
                        목록 규칙 선택 완료 시 본문 & 메타 규칙 설정으로 이동합니다.
                      </span>
                      <button
                        type="button"
                        onClick={() => setWrapperStep("step2_article")}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition flex items-center gap-1.5 shadow-lg shadow-indigo-900/40"
                      >
                        <span>다음: 본문 & 메타데이터 추출 (Step 2) ➔</span>
                      </button>
                    </div>
                  </div>

                  {/* 우측 6 컬럼: 탐색된 기사 링크 실시간 확인 영역 */}
                  <div className="lg:col-span-6 flex flex-col bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden min-h-0">
                    <div className="p-3 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between shrink-0">
                      <span className="font-semibold text-white flex items-center gap-1.5 text-xs">
                        <Layers className="w-3.5 h-3.5 text-purple-400" />
                        탐색된 기사 링크 목록 ({wrapperResult?.sample_links_count || 0}건)
                      </span>
                      {wrapperResult && (
                        <span className="text-[11px] text-slate-400 font-mono">
                          {wrapperResult.message}
                        </span>
                      )}
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-3">
                      <div className="bg-indigo-950/20 border border-indigo-500/20 p-2.5 rounded-lg text-slate-300 text-xs flex items-center justify-between">
                        <span className="flex items-center gap-1.5 font-semibold text-indigo-200">
                          <MousePointerClick className="w-3.5 h-3.5 text-purple-400" />
                          기사 링크를 클릭하시면 해당 글의 본문 및 메타 파싱 결과를 즉시 확인하실 수 있습니다.
                        </span>
                      </div>

                      <div className="space-y-1.5">
                        {wrapperResult?.sample_items && wrapperResult.sample_items.length > 0 ? (
                          wrapperResult.sample_items.map((item, i) => {
                            const isSelected = selectedArticleUrl === item.url;
                            return (
                              <div
                                key={i}
                                onClick={() => handleSelectArticleForWrapper(item.url)}
                                className={`p-2.5 rounded-lg border flex items-center justify-between gap-3 cursor-pointer transition ${
                                  isSelected
                                    ? "bg-purple-950/60 border-purple-500/80 shadow-md shadow-purple-950/40"
                                    : "bg-slate-900/90 hover:bg-slate-900 border-slate-800 hover:border-purple-500/50"
                                }`}
                              >
                                <div className="space-y-0.5 min-w-0 flex-1">
                                  <div className={`font-semibold text-xs truncate ${isSelected ? "text-purple-300 font-bold" : "text-slate-200"}`}>
                                    {item.title || item.anchor_text || `기사 #${i + 1}`}
                                  </div>
                                  <div className="text-[10px] text-slate-500 font-mono truncate">{item.url}</div>
                                </div>

                                <div className="flex items-center gap-2 shrink-0">
                                  <span className="text-[10px] text-purple-400 bg-purple-950/80 px-2 py-0.5 rounded border border-purple-500/30 font-medium">
                                    본문 보기 ➔
                                  </span>
                                  <a
                                    href={item.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    onClick={(e) => e.stopPropagation()}
                                    className="text-slate-500 hover:text-white p-1"
                                    title="새 창에서 원본 열기"
                                  >
                                    <ExternalLink className="w-3.5 h-3.5" />
                                  </a>
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="py-20 text-center text-slate-500 space-y-2">
                            <Layers className="w-8 h-8 mx-auto text-slate-600 opacity-60" />
                            <p className="text-xs">좌측에서 [🎯 이 영역 선택]을 누르면 탐색된 기사 링크가 이곳에 표시됩니다.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              )}

              {/* Step 2: (B) 본문 & 메타데이터(Meta) 정밀 추출 영역 */}
              {wrapperStep === "step2_article" && (
                <div className="flex-1 overflow-hidden flex flex-col gap-3">
                  {/* 상단 메가 AI 액션 카드: 다수 페이지(5건 무작위) 교차 분석 버튼 */}
                  <div className="bg-gradient-to-r from-purple-950/60 via-indigo-950/50 to-slate-900 p-3 rounded-xl border border-purple-500/40 flex flex-wrap items-center justify-between gap-3 shrink-0 shadow-lg shadow-purple-950/30">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 font-bold text-white text-xs">
                        <Sparkles className="w-4 h-4 text-purple-400" />
                        <span>다수 페이지(5건 무작위) DOM 교차 분석 & 본문/메타데이터 자동 합성</span>
                      </div>
                      <p className="text-[11px] text-slate-300">
                        탐색된 기사 중 <strong className="text-white">무작위 5개 페이지</strong>를 실시간으로 가져와 DOM 템플릿을 교차 대조하여 <strong className="text-purple-300">제목·작성자·작성일·조회수·본문·이미지</strong> 셀렉터를 스스로 도출합니다.
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleSynthesizeArticleMeta}
                        disabled={synthesizingArticleMeta || testingRules}
                        className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-lg transition shadow-lg shadow-purple-900/50 flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {synthesizingArticleMeta ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>무작위 5개 페이지 교차 분석 중...</span>
                          </>
                        ) : (
                          <>
                            <Wand2 className="w-3.5 h-3.5" />
                            <span>✨ 본문 & 메타데이터 규칙 자동 도출 실행 (5개 샘플)</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-12 gap-4">
                    {/* 좌측 5 컬럼: 상세 메타데이터 셀렉터 정밀 편집 폼 */}
                    <div className="lg:col-span-5 flex flex-col bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden min-h-0">
                      <div className="p-3 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between shrink-0">
                        <span className="font-semibold text-white flex items-center gap-1.5 text-xs">
                          <Code className="w-3.5 h-3.5 text-purple-400" />
                          본문 & 메타데이터 CSS Selector 규칙
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">정밀 미세조정</span>
                      </div>

                      <div className="flex-1 overflow-y-auto p-3.5 space-y-3">
                        {/* 🎯 스마트 도구: 텍스트 복사-붙여넣기 기반 셀렉터 1초 역추적 카드 */}
                        <div className="p-3 bg-gradient-to-r from-purple-950/40 via-indigo-950/30 to-slate-900 border border-purple-500/30 rounded-xl space-y-2">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-bold text-purple-300 flex items-center gap-1.5">
                              <Target className="w-3.5 h-3.5 text-purple-400" />
                              <span>텍스트 복사-붙여넣기로 셀렉터 자동 역추적</span>
                            </span>
                            <span className="text-[9px] text-slate-400 font-mono">1-Click Match</span>
                          </div>
                          <p className="text-[10px] text-slate-400 leading-tight">
                            실제 페이지에서 본문/작성자 글자 몇 자를 복사해 붙여넣으면 DOM을 역추적하여 최적의 셀렉터를 자동 완성합니다.
                          </p>
                          <div className="flex items-center gap-1.5">
                            <select
                              value={reverseTargetField}
                              onChange={(e: any) => setReverseTargetField(e.target.value)}
                              className="bg-slate-900 border border-slate-700 text-purple-300 text-[11px] px-2 py-1.5 rounded-lg font-semibold focus:outline-none focus:border-purple-500 shrink-0"
                            >
                              <option value="content_selector">📄 본문</option>
                              <option value="author_selector">👤 작성자</option>
                              <option value="title_selector">📝 제목</option>
                              <option value="date_selector">🕒 작성일</option>
                            </select>
                            <input
                              type="text"
                              value={reverseSnippetInput}
                              onChange={(e) => setReverseSnippetInput(e.target.value)}
                              placeholder="복사한 텍스트 붙여넣기 (예: '김민석 평소 행실이...')"
                              className="flex-1 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-sans text-[11px] focus:outline-none focus:border-purple-500 min-w-0"
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  e.preventDefault();
                                  handleReverseLookupSelector();
                                }
                              }}
                            />
                            <button
                              type="button"
                              onClick={handleReverseLookupSelector}
                              disabled={runningReverse}
                              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-[11px] font-bold transition shrink-0 flex items-center gap-1 shadow-md shadow-purple-900/30"
                            >
                              {runningReverse ? (
                                <RefreshCw className="w-3 h-3 animate-spin" />
                              ) : (
                                <Crosshair className="w-3 h-3" />
                              )}
                              <span>역추적</span>
                            </button>
                          </div>
                          {reverseResultMsg && (
                            <div className="text-[10px] font-mono px-2 py-1 rounded bg-slate-900 border border-slate-800 text-purple-200">
                              {reverseResultMsg}
                            </div>
                          )}
                        </div>
                        {/* 1. 제목 셀렉터 */}
                        <div>
                          <label className="block text-slate-300 mb-1 font-semibold text-[11px] flex items-center justify-between">
                            <span>📝 글 제목 (title_selector)</span>
                            <span className="text-[10px] text-slate-500">예: .post_title, h1.title</span>
                          </label>
                          <input
                            type="text"
                            value={editedRules.title_selector || ""}
                            onChange={(e) => setEditedRules({ ...editedRules, title_selector: e.target.value })}
                            placeholder=".post_title .break, h1.article_title"
                            className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                          />
                        </div>

                        {/* 2. 본문 셀렉터 */}
                        <div>
                          <label className="block text-slate-300 mb-1 font-semibold text-[11px] flex items-center justify-between">
                            <span>📄 본문 컨테이너 (content_selector)</span>
                            <span className="text-[10px] text-slate-500">예: .post_article, article</span>
                          </label>
                          <input
                            type="text"
                            value={editedRules.content_selector || ""}
                            onChange={(e) => setEditedRules({ ...editedRules, content_selector: e.target.value })}
                            placeholder=".post_article, .post_content, article"
                            className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                          />
                        </div>

                        {/* 3. 작성자 & 작성일시 */}
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-slate-300 mb-1 font-semibold text-[11px]">
                              👤 작성자 (author_selector)
                            </label>
                            <input
                              type="text"
                              value={editedRules.author_selector || ""}
                              onChange={(e) => setEditedRules({ ...editedRules, author_selector: e.target.value })}
                              placeholder=".post_contact, .nickname"
                              className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                            />
                          </div>
                          <div>
                            <label className="block text-slate-300 mb-1 font-semibold text-[11px]">
                              🕒 작성일시 (date_selector)
                            </label>
                            <input
                              type="text"
                              value={editedRules.date_selector || ""}
                              onChange={(e) => setEditedRules({ ...editedRules, date_selector: e.target.value })}
                              placeholder=".post_date, time"
                              className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                            />
                          </div>
                        </div>

                        {/* 4. 조회수 & 카테고리 */}
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-slate-300 mb-1 font-semibold text-[11px]">
                              👁️ 조회수 (views_selector)
                            </label>
                            <input
                              type="text"
                              value={editedRules.views_selector || ""}
                              onChange={(e) => setEditedRules({ ...editedRules, views_selector: e.target.value })}
                              placeholder=".view_count, .post_view"
                              className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                            />
                          </div>
                          <div>
                            <label className="block text-slate-300 mb-1 font-semibold text-[11px]">
                              🏷️ 게시판명 (category_selector)
                            </label>
                            <input
                              type="text"
                              value={editedRules.category_selector || ""}
                              onChange={(e) => setEditedRules({ ...editedRules, category_selector: e.target.value })}
                              placeholder=".board_name, .category"
                              className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                            />
                          </div>
                        </div>

                        {/* 5. 본문 첨부 이미지 셀렉터 */}
                        <div>
                          <label className="block text-slate-300 mb-1 font-semibold text-[11px] flex items-center justify-between">
                            <span>🖼️ 본문 첨부 이미지 (image_selector)</span>
                            <span className="text-[10px] text-slate-500">기본값: 본문 내 전체 img</span>
                          </label>
                          <input
                            type="text"
                            value={editedRules.image_selector || ""}
                            onChange={(e) => setEditedRules({ ...editedRules, image_selector: e.target.value })}
                            placeholder=".post_article img, .post_content img"
                            className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-purple-500"
                          />
                        </div>

                        {/* 6. 🌟 Vision LLM 이미지 텍스트 변환 및 본문 주입 옵션 */}
                        <div className="bg-purple-950/30 border border-purple-500/30 rounded-xl p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-purple-200 flex items-center gap-1.5">
                              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                              Vision LLM 이미지 텍스트 주입
                            </span>
                            <label className="relative inline-flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                checked={enableVision}
                                onChange={(e) => {
                                  setEnableVision(e.target.checked);
                                  setEditedRules({ ...editedRules, enable_vision: e.target.checked });
                                }}
                                className="sr-only peer"
                              />
                              <div className="w-8 h-4 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-purple-600"></div>
                            </label>
                          </div>
                          <p className="text-[10px] text-slate-400 leading-tight">
                            본문 내 이미지를 AI로 분석하여 텍스트 설명(OCR, 캡션)을 본문 내용에 자동 주입합니다.
                          </p>
                          {enableVision && (
                            <div className="pt-1 flex items-center gap-2">
                              <span className="text-[10px] text-slate-400 shrink-0">Vision 모델:</span>
                              <select
                                value={visionModel}
                                onChange={(e) => {
                                  setVisionModel(e.target.value);
                                  setEditedRules({ ...editedRules, vision_model: e.target.value });
                                }}
                                className="bg-slate-900 border border-purple-500/40 text-white font-mono text-[10px] px-2 py-1 rounded w-full focus:outline-none"
                              >
                                <option value="llama3.2-vision">Ollama: llama3.2-vision (권장)</option>
                                <option value="llava">Ollama: llava (멀티모달)</option>
                                <option value="minicpm-v">Ollama: minicpm-v</option>
                                <option value="qwen2.5:27b">Ollama: qwen2.5:27b</option>
                                <option value="gemini-2.0-flash">Gemini 2.0 Flash (Cloud Vision)</option>
                              </select>
                            </div>
                          )}
                        </div>

                        {/* 실시간 검증 버튼 */}
                        <button
                          type="button"
                          onClick={handleTestWrapperRules}
                          disabled={testingRules}
                          className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold text-xs transition flex items-center justify-center gap-1.5 shadow-lg shadow-purple-900/30"
                        >
                          {testingRules ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              <span>지정된 규칙으로 테스트 중...</span>
                            </>
                          ) : (
                            <>
                              <Play className="w-3.5 h-3.5 text-purple-200" />
                              <span>입력된 규칙으로 상세 파싱 실시간 검증</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>

                    {/* 우측 7 컬럼: 풍부한 상세 문서 & 메타데이터 실시간 뷰어 (Document & Meta Viewer) */}
                    <div className="lg:col-span-7 flex flex-col bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden min-h-0">
                      {/* 샘플 기사 전환 탭 바 */}
                      <div className="p-2.5 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-1.5">
                          {articleMetaPreviews.length > 0 ? (
                            articleMetaPreviews.map((sample, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  setActiveArticlePreviewIndex(idx);
                                  setSelectedArticle(sample);
                                  setSelectedArticleUrl(sample.url);
                                }}
                                className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                                  activeArticlePreviewIndex === idx
                                    ? "bg-purple-600 text-white shadow"
                                    : "bg-slate-900 text-slate-400 hover:text-slate-200"
                                }`}
                              >
                                샘플 #{idx + 1}
                              </button>
                            ))
                          ) : (
                            <span className="text-xs text-slate-300 font-semibold flex items-center gap-1.5">
                              <FileText className="w-3.5 h-3.5 text-purple-400" />
                              상세 문서 & 메타데이터 파싱 뷰어
                            </span>
                          )}
                        </div>

                        {selectedArticle && (
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={handleCopyContent}
                              className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded text-[11px] text-slate-300 flex items-center gap-1 transition shrink-0"
                            >
                              {copiedContent ? (
                                <>
                                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                                  <span className="text-emerald-400">본문 복사됨</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3.5 h-3.5" />
                                  <span>본문 복사</span>
                                </>
                              )}
                            </button>
                          </div>
                        )}
                      </div>

                      {/* 뷰어 바디 */}
                      <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {(synthesizingArticleMeta || testingRules || articleLoading) && (
                          <div className="py-20 text-center space-y-3 bg-slate-900/60 rounded-xl border border-slate-800">
                            <RefreshCw className="w-8 h-8 text-purple-400 animate-spin mx-auto" />
                            <p className="text-slate-200 text-sm font-semibold">
                              {synthesizingArticleMeta
                                ? "다수 상세 페이지 DOM을 교차 분석하여 메타데이터 규칙을 도출하고 있습니다..."
                                : "선택한 기사의 본문 및 메타데이터를 파싱하고 있습니다..."}
                            </p>
                            <p className="text-slate-500 font-mono text-[11px] truncate max-w-md mx-auto">
                              {selectedArticleUrl || "Ollama Model: " + wrapperModelName}
                            </p>
                          </div>
                        )}

                        {!synthesizingArticleMeta && !testingRules && !articleLoading && (
                          (() => {
                            const currentArticle = selectedArticle || (articleMetaPreviews.length > 0 ? articleMetaPreviews[activeArticlePreviewIndex] : null) || wrapperResult?.sample_article_preview;
                            if (!currentArticle) {
                              return (
                                <div className="py-24 text-center text-slate-500 space-y-3">
                                  <FileText className="w-10 h-10 mx-auto text-slate-600 opacity-60" />
                                  <p className="text-sm font-medium">상단의 [✨ 본문 & 메타데이터 규칙 자동 도출 실행] 버튼을 눌러보세요.</p>
                                  <p className="text-xs text-slate-600">Local Ollama가 실제 문서 페이지들을 분석하여 제목, 작성자, 작성일, 조회수, 본문 규칙을 완성합니다.</p>
                                </div>
                              );
                            }

                            return (
                              <div className="space-y-4">
                                {/* 메타데이터 카드 헤더 */}
                                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800 space-y-2.5">
                                  <div className="flex items-center gap-2">
                                    {currentArticle.category && (
                                      <span className="bg-indigo-950 text-indigo-300 text-[10px] font-bold px-2 py-0.5 rounded border border-indigo-500/30">
                                        🏷️ {currentArticle.category}
                                      </span>
                                    )}
                                    {currentArticle.url && (
                                      <a
                                        href={currentArticle.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="text-slate-400 hover:text-white font-mono text-[10px] truncate max-w-md flex items-center gap-1"
                                      >
                                        <span>{currentArticle.url}</span>
                                        <ExternalLink className="w-3 h-3 shrink-0" />
                                      </a>
                                    )}
                                  </div>

                                  <h4 className="text-base font-bold text-white leading-snug">
                                    {currentArticle.title}
                                  </h4>

                                  <div className="flex flex-wrap items-center gap-2 text-xs font-mono pt-1">
                                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-slate-200">
                                      👤 작성자: <strong className="text-purple-300">{currentArticle.author || "미지정"}</strong>
                                    </span>
                                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-slate-300">
                                      🕒 작성일: <strong className="text-slate-100">{currentArticle.published_at || "-"}</strong>
                                    </span>
                                    {currentArticle.views && (
                                      <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-cyan-300">
                                        👁️ 조회수: <strong>{currentArticle.views}</strong>
                                      </span>
                                    )}
                                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-emerald-400">
                                      📊 글자수: <strong>{currentArticle.char_count.toLocaleString()}</strong> 자
                                    </span>
                                  </div>
                                </div>

                                {/* 본문 내 첨부 이미지 갤러리 & Vision AI 설명 */}
                                {currentArticle.images && currentArticle.images.length > 0 && (
                                  <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800 space-y-3">
                                    <div className="font-semibold text-slate-300 text-xs flex flex-wrap items-center justify-between gap-2">
                                      <span className="flex items-center gap-1.5">
                                        <ImageIcon className="w-3.5 h-3.5 text-purple-400" />
                                        본문 첨부 이미지 ({currentArticle.images.length}장 탐색됨)
                                      </span>
                                      
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <select
                                          value={visionModel}
                                          onChange={(e) => setVisionModel(e.target.value)}
                                          className="bg-slate-950 border border-slate-700 text-slate-200 font-mono text-[10px] px-2 py-1 rounded-lg focus:outline-none focus:border-purple-500"
                                        >
                                          <optgroup label="Vision 특화 모델">
                                            <option value="llama3.2-vision">llama3.2-vision (Ollama)</option>
                                            <option value="llava">llava (Ollama)</option>
                                            <option value="minicpm-v">minicpm-v (Ollama)</option>
                                            <option value="gemini-2.0-flash">Gemini 2.0 Flash (Cloud)</option>
                                          </optgroup>
                                          <optgroup label="현재 로컬 LLM">
                                            <option value={wrapperModelName}>{wrapperModelName} (선택된 모델)</option>
                                          </optgroup>
                                        </select>

                                        <button
                                          type="button"
                                          onClick={handleRunVisionForArticle}
                                          disabled={runningVision}
                                          className="flex items-center gap-1.5 px-3 py-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-lg text-[11px] font-semibold transition shadow-md"
                                        >
                                          <Sparkles className={`w-3 h-3 ${runningVision ? "animate-spin" : ""}`} />
                                          <span>{runningVision ? "Vision 분석 진행 중..." : "✨ Vision 이미지 텍스트 변환 실행"}</span>
                                        </button>
                                      </div>
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                                      {currentArticle.images.map((imgSrc, imgIdx) => {
                                        const desc = currentArticle.image_descriptions?.[imgSrc];
                                        return (
                                          <div key={imgIdx} className="bg-slate-950/80 rounded-xl border border-slate-800 overflow-hidden flex flex-col group">
                                            <a
                                              href={imgSrc}
                                              target="_blank"
                                              rel="noreferrer"
                                              className="relative aspect-video flex items-center justify-center bg-black/40 overflow-hidden"
                                            >
                                              {/* eslint-disable-next-line @next/next/no-img-element */}
                                              <img
                                                src={imgSrc}
                                                alt={`본문 첨부 이미지 #${imgIdx + 1}`}
                                                className="w-full h-full object-cover group-hover:scale-105 transition"
                                              />
                                              <div className="absolute top-1.5 right-1.5 bg-black/70 text-slate-300 px-1.5 py-0.5 rounded text-[9px] flex items-center gap-1">
                                                <span>#{imgIdx + 1}</span>
                                                <ExternalLink className="w-2.5 h-2.5" />
                                              </div>
                                            </a>

                                            {/* Vision LLM이 추출한 텍스트 설명 배너 */}
                                            {desc ? (
                                              <div className="p-2.5 bg-purple-950/40 border-t border-purple-500/20 text-[10px] space-y-1">
                                                <div className="text-purple-300 font-bold flex items-center gap-1">
                                                  <Sparkles className="w-2.5 h-2.5" />
                                                  <span>AI 시각 분석 & OCR</span>
                                                </div>
                                                <p className="text-slate-200 leading-relaxed line-clamp-3">
                                                  {desc}
                                                </p>
                                              </div>
                                            ) : (
                                              <div className="p-2 bg-slate-900/40 border-t border-slate-800 text-[10px] text-slate-500 flex items-center justify-between">
                                                <span>Vision 미분석</span>
                                                <span className="text-[9px] text-purple-400 font-mono">대기중</span>
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                )}

                                {/* 정제된 본문 내용 및 위치 표식 */}
                                <div className="space-y-1.5">
                                  <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                                    <span className="flex items-center gap-1.5">
                                      <span>정제된 본문 텍스트 내용:</span>
                                      {currentArticle.content?.includes("{{HORUS_IMG:") && (
                                        <span className="bg-purple-950/80 border border-purple-500/40 text-purple-300 text-[10px] px-2 py-0.5 rounded-full font-mono">
                                          📌 이미지 위치 표식 삽입됨
                                        </span>
                                      )}
                                    </span>
                                    <span className="text-[10px] text-slate-500 font-mono">{currentArticle.char_count} chars</span>
                                  </div>
                                  <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800 text-slate-200 text-xs leading-relaxed whitespace-pre-wrap font-sans max-h-96 overflow-y-auto">
                                    {currentArticle.content || (
                                      <span className="text-slate-500">본문 텍스트가 비어있습니다. 본문 셀렉터(content_selector)를 확인해주세요.</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })()
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 모달 푸터 */}
            <div className="p-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-950/60 shrink-0">
              <div className="text-[11px] text-slate-400 font-mono">
                저장 시 <span className="text-purple-300 font-bold">{selectedSourceForWrapper.name}</span>의 수집 파이프라인에 즉시 반영됩니다.
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsWrapperModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition"
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={handleSaveWrapperRules}
                  disabled={savingWrapper}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition shadow-lg shadow-indigo-900/30 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {savingWrapper ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>저장 중...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>이 규칙을 Seed에 적용 및 저장</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
