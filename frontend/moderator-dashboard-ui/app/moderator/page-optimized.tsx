"use client"

import { useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PageShell } from "@/components/ui/PageShell"
import { LoadingState } from "@/components/ui/LoadingState"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { handleStartParsing } from "../actions/parsing"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { ParsingProgressBar } from "@/components/dashboard/parsing-progress-bar"
import CurrentTaskBlock from "@/components/current-task-block"
import { RunStatusBadge } from "@/components/run-status-badge"
import { 
  useModeratorStats,
  useParsingRuns,
  useParsingRun,
  useDomainsQueue,
  useStartParsing,
} from "@/hooks/queries/parsing"
import { extractRootDomain } from "@/lib/utils-domain"
import { toast } from "sonner"
import { ArrowRight, Play, TrendingUp, AlertCircle, Ban, Activity, Globe, Users, Flame, Sparkles, LayoutDashboard } from "lucide-react"
import type { ParsingRunDTO } from "@/lib/types"

function DashboardPage() {
  const router = useRouter()
  const [keyword, setKeyword] = useState("")
  const [depth, setDepth] = useState(5)
  const [source, setSource] = useState<"google" | "yandex" | "both">("both")
  
  // React Query hooks
  const { data: stats, isLoading: statsLoading } = useModeratorStats()
  const { data: runsData, isLoading: runsLoading } = useParsingRuns({ limit: 10 })
  const startParsingMutation = useStartParsing()
  
  // Current active run state
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  
  // Get active run data
  const { data: activeRun, isLoading: activeRunLoading } = useParsingRun(
    activeRunId || ""
  )
  
  // Get domains queue for active run
  const { data: domainsData, isLoading: domainsLoading } = useDomainsQueue(
    activeRunId ? { parsingRunId: activeRunId, limit: 100 } : undefined
  )

  // Кэш для доменов (используем useRef для сохранения между рендерами)
  const domainsCacheRef = useRef<Array<{ domain: string; source: string | null; createdAt: string }>>([])

  // Фильтр для доменов по источнику
  const [domainSourceFilter, setDomainSourceFilter] = useState<"all" | "google" | "yandex" | "both">("all")

  // Find active run from runs data
  const activeRunFromList = runsData?.runs?.find(run => 
    ["running", "starting"].includes(run.status)
  )

  // Update active run ID when runs data changes
  if (activeRunFromList?.run_id !== activeRunId && activeRunFromList) {
    setActiveRunId(activeRunFromList.run_id || null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!keyword.trim()) {
      toast.error("Введите ключевое слово")
      return
    }

    try {
      await startParsingMutation.mutateAsync({
        keyword,
        depth,
        source,
      })
      
      // Reset form
      setKeyword("")
      setDepth(5)
      setSource("both")
    } catch (error) {
      console.error("Start parsing error:", error)
    }
  }

  // Calculate parsing progress
  const parsingProgress = {
    isRunning: !!activeRun && ["running", "starting"].includes(activeRun.status),
    runId: activeRun?.run_id || null,
    status: activeRun?.status || "",
    resultsCount: domainsData?.entries?.length || null,
    source: activeRun?.source || null,
    sourceStats: domainsData ? {
      google: domainsData.entries.filter(e => e.source === "google").length,
      yandex: domainsData.entries.filter(e => e.source === "yandex").length,
      both: domainsData.entries.filter(e => e.source === "both").length,
    } : undefined,
    captchaDetected: activeRun?.error_message?.toLowerCase().includes("captcha") || 
                   activeRun?.error?.toLowerCase().includes("captcha") || false,
    recentDomains: domainsData?.entries
      ?.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 10)
      .map(e => ({
        domain: e.domain,
        source: e.source || null,
        createdAt: e.createdAt,
      })) || [],
    progressPercent: activeRun?.status === "completed" ? 100 : 
                    activeRun?.status === "running" ? 
                      Math.min((domainsData?.entries?.length || 0) * 10, 95) : undefined,
    parsingLogs: null, // Could be fetched from useParsingLogs if needed
  }

  // Filter recent domains by source
  const filteredRecentDomains = parsingProgress.recentDomains?.filter(domain => 
    domainSourceFilter === "all" || domain.source === domainSourceFilter
  ) || []

  const isLoading = statsLoading || runsLoading || activeRunLoading

  if (isLoading) {
    return (
      <AuthGuard allowedRoles={["moderator"]}>
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-indigo-50/20">
          <Navigation />
          <PageShell
            title="Панель модератора"
            description="Управление парсингом и мониторинг системы"
            icon={LayoutDashboard}
            gradientFrom="from-blue-600"
            gradientTo="to-purple-600"
          >
            <LoadingState message="Загрузка данных панели..." size="lg" />
          </PageShell>
        </div>
      </AuthGuard>
    )
  }

  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-indigo-50/20">
      <Navigation />
      <PageShell
        title="Панель модератора"
        description="Управление парсингом и мониторинг системы"
        icon={LayoutDashboard}
        gradientFrom="from-blue-600"
        gradientTo="to-purple-600"
        actions={
          <Badge variant="outline" className="text-sm">
            {stats?.active_runs || 0} активных запусков
          </Badge>
        }
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
        </motion.div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.1 }}
          >
            <Card
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => router.push("/domains?status=pending")}
            >
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Доменов в очереди</CardTitle>
                <Globe className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.domains_in_queue || 0}</div>
                <p className="text-xs text-muted-foreground">
                  Ожидают извлечения данных
                </p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.2 }}
          >
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Новые поставщики</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.new_suppliers || 0}</div>
                <p className="text-xs text-muted-foreground">
                  За последние 24 часа
                </p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.3 }}
          >
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Черный список</CardTitle>
                <Ban className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.blacklist_count || 0}</div>
                <p className="text-xs text-muted-foreground">
                  Заблокированных доменов
                </p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.4 }}
          >
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Задачи модерации</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.open_tasks || 0}</div>
                <p className="text-xs text-muted-foreground">
                  Ожидают проверки
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Start Parsing Form */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Flame className="h-5 w-5" />
                Запуск парсинга
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor="keyword">Ключевое слово</Label>
                    <Input
                      id="keyword"
                      type="text"
                      placeholder="Введите ключевое слово..."
                      value={keyword}
                      onChange={(e) => setKeyword(e.target.value)}
                      disabled={startParsingMutation.isPending}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="depth">Глубина парсинга</Label>
                    <Input
                      id="depth"
                      type="number"
                      min="1"
                      max="10"
                      value={depth}
                      onChange={(e) => setDepth(Number(e.target.value))}
                      disabled={startParsingMutation.isPending}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="source">Источник</Label>
                    <select
                      id="source"
                      value={source}
                      onChange={(e) => setSource(e.target.value as "google" | "yandex" | "both")}
                      disabled={startParsingMutation.isPending}
                      className="w-full p-2 border rounded-md"
                    >
                      <option value="both">Google + Яндекс</option>
                      <option value="google">Только Google</option>
                      <option value="yandex">Только Яндекс</option>
                    </select>
                  </div>
                </div>
                <Button
                  type="submit"
                  disabled={startParsingMutation.isPending || !keyword.trim()}
                  className="w-full md:w-auto"
                >
                  {startParsingMutation.isPending ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                      Запуск...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Запустить парсинг
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        {/* Parsing Progress */}
        {parsingProgress.isRunning && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <ParsingProgressBar
              isRunning={parsingProgress.isRunning}
              status={parsingProgress.status}
              resultsCount={parsingProgress.resultsCount}
              source={parsingProgress.source}
              sourceStats={parsingProgress.sourceStats}
              captchaDetected={parsingProgress.captchaDetected}
              recentDomains={parsingProgress.recentDomains}
              progressPercent={parsingProgress.progressPercent}
              parsingLogs={parsingProgress.parsingLogs}
            />
          </motion.div>
        )}

        {/* Current Task Block — AC-01: between "Запуск парсинга" and "Последние запуски" */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
        >
          <CurrentTaskBlock />
        </motion.div>

        {/* Recent Runs — compact summary */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Последние запуски
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push("/parsing-runs")}
                >
                  Все запуски
                  <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {runsLoading ? (
                <div className="text-center py-4">Загрузка...</div>
              ) : runsData?.runs?.length ? (
                <div className="space-y-2">
                  {runsData.runs.slice(0, 3).map((run: ParsingRunDTO) => (
                    <div
                      key={run.run_id}
                      className="flex items-center justify-between p-2 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => router.push(`/parsing-runs/${run.run_id}`)}
                    >
                      <div className="flex items-center gap-3">
                        <RunStatusBadge status={run.status} />
                        <span className="font-medium text-sm">{run.keyword}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-muted-foreground">
                          {run.resultsCount || 0} доменов
                        </span>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-3 text-muted-foreground text-sm">
                  Запусков пока нет
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </PageShell>
      </div>
    </AuthGuard>
  )
}

export default DashboardPage
