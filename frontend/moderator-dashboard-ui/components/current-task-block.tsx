"use client"

import React, { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  useCurrentTask,
  useManualResolveDomain,
  useStartDomainParser,
  useUnprocessedRuns,
  useResumeAllProcessing,
} from "@/hooks/queries/current-task"
import { useLearningStatistics } from "@/hooks/queries/learning"
import { useDomainsQueue } from "@/hooks/queries/parsing"
import { LearningStatsBar } from "@/components/learning-stats-bar"
import type { RunDomainDTO, ManualResolveRequest } from "@/lib/types"
import type { UnprocessedRun } from "@/lib/api"
import {
  Loader2,
  Play,
  ExternalLink,
  Activity,
  Pause,
  Globe,
  Brain,
  Zap,
  Plug,
  Monitor,
  ArrowRight,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RotateCcw,
  Inbox,
} from "lucide-react"

/* ── Circle colors ─────────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-300 text-gray-700",
  processing: "bg-blue-500 text-white animate-pulse ring-4 ring-blue-300",
  supplier: "bg-green-500 text-white",
  reseller: "bg-purple-500 text-white",
  requires_moderation: "bg-yellow-400 text-yellow-900",
}

const STATUS_RING: Record<string, string> = {
  pending: "ring-gray-400",
  processing: "ring-blue-400",
  supplier: "ring-green-600",
  reseller: "ring-purple-600",
  requires_moderation: "ring-yellow-500",
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает",
  processing: "В обработке",
  supplier: "Поставщик",
  reseller: "Перекупщик",
  requires_moderation: "Модерация",
}

/* ── DomainCircle ──────────────────────────────────────────────────────────── */

function DomainCircle({
  domain,
  onClickSupplier,
  onClickModeration,
}: {
  domain: RunDomainDTO
  onClickSupplier: (supplierId: number) => void
  onClickModeration: (domain: RunDomainDTO) => void
}) {
  const colorClass = STATUS_COLORS[domain.status] || STATUS_COLORS.pending
  const ringClass = domain.status === "processing" ? "" : `ring-2 ${STATUS_RING[domain.status] || STATUS_RING.pending}`

  const isInherited = domain.global_requires_moderation && domain.status in { supplier: 1, reseller: 1 }
  const showChecko = (domain.status === "supplier" || domain.status === "reseller") && domain.checko_ok
  const showGlobal = domain.status === "requires_moderation" && domain.global_requires_moderation

  let label: string
  if (domain.status === "processing") {
    label = "\u25B6"
  } else if (showChecko) {
    label = "C"
  } else if (showGlobal || isInherited) {
    label = "G"
  } else {
    label = domain.domain.charAt(0).toUpperCase()
  }

  const handleClick = () => {
    if ((domain.status === "supplier" || domain.status === "reseller") && domain.supplier_id) {
      onClickSupplier(domain.supplier_id)
    } else if (domain.status === "requires_moderation") {
      onClickModeration(domain)
    }
  }

  const isClickable =
    ((domain.status === "supplier" || domain.status === "reseller") && domain.supplier_id) ||
    domain.status === "requires_moderation"

  const tooltipContent = () => {
    const statusLabel = STATUS_LABELS[domain.status] || domain.status
    if (domain.status === "processing") {
      return (
        <div className="space-y-1 max-w-xs">
          <p className="font-medium">{domain.domain}</p>
          <p className="text-xs text-blue-300">Сейчас обрабатывается парсером</p>
        </div>
      )
    }
    if (domain.status === "supplier" || domain.status === "reseller") {
      return (
        <div className="space-y-1 max-w-xs">
          <p className="font-medium">{domain.domain}</p>
          <p className="text-xs">Статус: {statusLabel}{isInherited ? " (унаследован)" : ""}</p>
          {domain.inn_source_url && <p className="text-xs truncate">INN URL: {domain.inn_source_url}</p>}
          {domain.email_source_url && <p className="text-xs truncate">Email URL: {domain.email_source_url}</p>}
          {domain.checko_ok && <p className="text-xs text-green-300">Checko \u2713</p>}
        </div>
      )
    }
    if (domain.status === "requires_moderation") {
      return (
        <div className="space-y-1 max-w-xs">
          <p className="font-medium">{domain.domain}</p>
          {domain.reason && <p className="text-xs">Причина: {domain.reason}</p>}
          {domain.attempted_urls && domain.attempted_urls.length > 0 && (
            <div className="text-xs">
              <p>Проверенные URL:</p>
              {domain.attempted_urls.slice(0, 5).map((url, i) => (
                <p key={i} className="truncate ml-1">{url}</p>
              ))}
              {domain.attempted_urls.length > 5 && (
                <p className="ml-1">...и ещё {domain.attempted_urls.length - 5}</p>
              )}
            </div>
          )}
          {domain.global_requires_moderation && (
            <p className="text-xs text-yellow-300">Глобальная модерация</p>
          )}
          <p className="text-xs text-muted-foreground">Нажмите для ручной модерации</p>
        </div>
      )
    }
    return (
      <div>
        <p className="font-medium">{domain.domain}</p>
        <p className="text-xs">Статус: {statusLabel}</p>
      </div>
    )
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={handleClick}
          disabled={!isClickable}
          className={`
            w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold
            ${ringClass} ${colorClass}
            ${isClickable ? "cursor-pointer hover:scale-110 hover:shadow-lg" : "cursor-default"}
            transition-all duration-200 flex-shrink-0
          `}
          title={domain.domain}
        >
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-sm">
        {tooltipContent()}
      </TooltipContent>
    </Tooltip>
  )
}

/* ── ModerationModal ───────────────────────────────────────────────────────── */

function ModerationModal({
  domain,
  open,
  onClose,
}: {
  domain: RunDomainDTO | null
  open: boolean
  onClose: () => void
}) {
  const [inn, setInn] = useState("")
  const [email, setEmail] = useState("")
  const [innSourceUrl, setInnSourceUrl] = useState("")
  const [emailSourceUrl, setEmailSourceUrl] = useState("")
  const [supplierType, setSupplierType] = useState<"supplier" | "reseller">("supplier")

  const mutation = useManualResolveDomain()

  React.useEffect(() => {
    if (domain && open) {
      setInn("")
      setEmail("")
      setInnSourceUrl("")
      setEmailSourceUrl("")
      setSupplierType("supplier")
    }
  }, [domain, open])

  const handleSave = () => {
    if (!domain) return
    const data: ManualResolveRequest = {
      inn: inn.trim(),
      email: email.trim(),
      inn_source_url: innSourceUrl.trim(),
      email_source_url: emailSourceUrl.trim(),
      supplier_type: supplierType,
    }
    mutation.mutate(
      { runDomainId: domain.id, data },
      { onSuccess: () => onClose() },
    )
  }

  const isValid = inn.trim().length > 0 && email.trim().length > 0

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Ручная модерация: {domain?.domain}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {domain?.reason && (
            <div className="text-sm text-muted-foreground bg-muted p-2 rounded">
              Причина: {domain.reason}
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="mod-inn">ИНН</Label>
            <Input id="mod-inn" value={inn} onChange={(e) => setInn(e.target.value)} placeholder="Введите ИНН" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mod-email">Email</Label>
            <Input id="mod-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Введите email" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mod-inn-url">URL где ИНН</Label>
            <Input id="mod-inn-url" value={innSourceUrl} onChange={(e) => setInnSourceUrl(e.target.value)} placeholder="https://..." />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mod-email-url">URL где Email</Label>
            <Input id="mod-email-url" value={emailSourceUrl} onChange={(e) => setEmailSourceUrl(e.target.value)} placeholder="https://..." />
          </div>
          <div className="space-y-2">
            <Label>Тип</Label>
            <Select value={supplierType} onValueChange={(v) => setSupplierType(v as "supplier" | "reseller")}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="supplier">Поставщик</SelectItem>
                <SelectItem value="reseller">Перекупщик</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>Отмена</Button>
          <Button onClick={handleSave} disabled={!isValid || mutation.isPending}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── UnprocessedRunRow ─────────────────────────────────────────────────────── */

function UnprocessedRunRow({
  run,
  isFirst,
  onNavigate,
}: {
  run: UnprocessedRun
  isFirst: boolean
  onNavigate: (runId: string) => void
}) {
  const total = run.total_domains
  const done = run.supplier_count + run.reseller_count + run.moderation_count
  const progressPct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-lg border transition-all cursor-pointer hover:shadow-sm ${
        isFirst
          ? "bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800"
          : "bg-white border-slate-200 hover:bg-slate-50 dark:bg-slate-900 dark:border-slate-700"
      }`}
      onClick={() => onNavigate(run.run_id)}
    >
      {/* Status indicator */}
      <div className="flex-shrink-0">
        {run.parser_active ? (
          <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center animate-pulse">
            <Activity className="h-4 w-4 text-white" />
          </div>
        ) : run.processing_count > 0 ? (
          <div className="w-8 h-8 rounded-full bg-amber-500 flex items-center justify-center">
            <Clock className="h-4 w-4 text-white" />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-slate-300 flex items-center justify-center">
            <Pause className="h-4 w-4 text-slate-600" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">
            {run.keyword || run.run_id.slice(0, 12)}
          </span>
          {isFirst && !run.parser_active && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-blue-300 text-blue-600">
              Следующий
            </Badge>
          )}
          {run.parser_active && (
            <Badge className="bg-blue-500 text-white text-[10px] px-1.5 py-0 animate-pulse">
              Обработка
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
          <span className="text-amber-600 font-medium">{run.pending_count} ожидает</span>
          {run.supplier_count > 0 && (
            <span className="text-green-600">{run.supplier_count} пост.</span>
          )}
          {run.reseller_count > 0 && (
            <span className="text-purple-600">{run.reseller_count} перек.</span>
          )}
          {run.moderation_count > 0 && (
            <span className="text-yellow-600">{run.moderation_count} модер.</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="flex-shrink-0 w-20">
        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
          <span>{done}/{total}</span>
          <span>{progressPct}%</span>
        </div>
        <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
    </div>
  )
}

/* ── Main block ────────────────────────────────────────────────────────────── */

export default function CurrentTaskBlock() {
  const router = useRouter()
  const { data, isLoading, isError } = useCurrentTask()
  const { data: unprocessedData, isLoading: unprocessedLoading } = useUnprocessedRuns()
  const { data: learningStats } = useLearningStatistics()
  const startParser = useStartDomainParser()
  const resumeAll = useResumeAllProcessing()
  const [moderationDomain, setModerationDomain] = useState<RunDomainDTO | null>(null)

  const handleSupplierClick = (supplierId: number) => {
    router.push(`/moderator/suppliers/${supplierId}`)
  }

  const handleModerationClick = (domain: RunDomainDTO) => {
    setModerationDomain(domain)
  }

  const handleNavigateToRun = (runId: string) => {
    router.push(`/parsing-runs/${runId}`)
  }

  const unprocessedRuns = unprocessedData?.runs || []
  const totalPendingDomains = unprocessedRuns.reduce((sum, r) => sum + r.pending_count, 0)
  const anyParserActive = unprocessedRuns.some(r => r.parser_active)

  // When no unprocessed runs, show global pending domains queue
  const showGlobalQueue = !unprocessedLoading && unprocessedRuns.length === 0
  const { data: domainsQueueData, isLoading: queueLoading } = useDomainsQueue(
    showGlobalQueue ? { status: "pending", limit: 20 } : undefined
  )
  const pendingQueueDomains = domainsQueueData?.entries || []
  const pendingQueueTotal = domainsQueueData?.total || 0

  // Current task data
  const currentRun = data?.current_run
  const domains = currentRun?.domains || []
  const summary = currentRun?.summary
  const processingDomain = currentRun?.processing_domain
  const parserActive = currentRun?.parser_active ?? false
  const hasPending = (summary?.pending_count ?? 0) > 0
  const hasProcessing = (summary?.processing_count ?? 0) > 0
  const canStart = hasPending && !parserActive && !hasProcessing
  const moderationDomains = domains.filter(d => d.status === "requires_moderation")

  return (
    <TooltipProvider delayDuration={200}>
      <Card className="border-2 border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="h-5 w-5 text-amber-500" />
              Очередь обработки
              {unprocessedRuns.length > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {unprocessedRuns.length} {unprocessedRuns.length === 1 ? "запуск" : "запусков"}
                </Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              {totalPendingDomains > 0 && (
                <Badge variant="outline" className="text-amber-600 border-amber-300">
                  <Clock className="h-3 w-3 mr-1" />
                  {totalPendingDomains} доменов ожидает
                </Badge>
              )}
              {anyParserActive && (
                <Badge className="bg-blue-500 text-white animate-pulse">
                  <Activity className="h-3 w-3 mr-1" />
                  Парсер работает
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Resume All button */}
          {unprocessedRuns.length > 0 && (
            <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 rounded-lg border border-blue-200 dark:border-blue-800">
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  {anyParserActive
                    ? "Парсер обрабатывает домены..."
                    : `${totalPendingDomains} доменов в ${unprocessedRuns.length} запусках ожидают обработки`
                  }
                </p>
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
                  {anyParserActive
                    ? "После завершения текущего запуска парсер перейдёт к следующему"
                    : "Нажмите «Возобновить» чтобы парсер начал обработку по очереди"
                  }
                </p>
              </div>
              <Button
                onClick={() => resumeAll.mutate()}
                disabled={resumeAll.isPending || anyParserActive}
                className={anyParserActive
                  ? "bg-slate-400"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                }
                size="sm"
              >
                {resumeAll.isPending ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Запуск...</>
                ) : anyParserActive ? (
                  <><Activity className="h-4 w-4 mr-2 animate-pulse" />Работает</>
                ) : (
                  <><RotateCcw className="h-4 w-4 mr-2" />Возобновить</>
                )}
              </Button>
            </div>
          )}

          {/* Unprocessed runs list */}
          {unprocessedLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-4 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" /><span className="text-sm">Загрузка очереди...</span>
            </div>
          ) : unprocessedRuns.length > 0 ? (
            <div className="space-y-2">
              {unprocessedRuns.map((run, idx) => (
                <UnprocessedRunRow
                  key={run.run_id}
                  run={run}
                  isFirst={idx === 0 && !anyParserActive}
                  onNavigate={handleNavigateToRun}
                />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg">
                <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-green-700 dark:text-green-300">
                    Все запуски обработаны
                  </p>
                  <p className="text-xs text-green-600 dark:text-green-400">
                    Нет доменов, ожидающих извлечения ИНН/Email
                  </p>
                </div>
              </div>

              {/* Global pending domains queue */}
              {queueLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground py-2 justify-center">
                  <Loader2 className="h-4 w-4 animate-spin" /><span className="text-sm">Загрузка очереди доменов...</span>
                </div>
              ) : pendingQueueDomains.length > 0 ? (
                <div className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Inbox className="h-4 w-4 text-amber-500" />
                      <span className="text-sm font-medium">Очередь доменов</span>
                      <Badge variant="outline" className="text-amber-600 border-amber-300 text-xs">
                        {pendingQueueTotal} в ожидании
                      </Badge>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => router.push("/domains?status=pending")}
                    >
                      Смотреть все
                      <ArrowRight className="h-3 w-3 ml-1" />
                    </Button>
                  </div>
                  <div className="space-y-1">
                    {pendingQueueDomains.slice(0, 10).map((entry, idx) => (
                      <div
                        key={`${entry.domain}-${idx}`}
                        className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-muted/50 cursor-pointer transition-colors"
                        onClick={() => window.open(`https://${entry.domain}`, "_blank")}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Globe className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                          <span className="truncate font-mono text-xs">{entry.domain}</span>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {entry.keyword && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                              {entry.keyword}
                            </Badge>
                          )}
                          <ExternalLink className="h-3 w-3 text-muted-foreground" />
                        </div>
                      </div>
                    ))}
                    {pendingQueueTotal > 10 && (
                      <p className="text-xs text-muted-foreground text-center pt-1">
                        и ещё {pendingQueueTotal - 10} доменов...
                      </p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* Active task domain circles (compact) */}
          {currentRun && domains.length > 0 && (hasPending || hasProcessing) && (
            <div className="border-t pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-muted-foreground">
                  Текущий запуск: {currentRun.keyword || currentRun.run_id.slice(0, 12)}
                </span>
                {processingDomain && (
                  <span className="text-xs text-blue-600 font-mono animate-pulse">
                    {processingDomain}
                  </span>
                )}
              </div>
              <div className="overflow-x-auto pb-1">
                <div className="flex gap-1.5 min-w-0">
                  {domains.slice(0, 30).map((d) => (
                    <DomainCircle
                      key={d.id}
                      domain={d}
                      onClickSupplier={handleSupplierClick}
                      onClickModeration={handleModerationClick}
                    />
                  ))}
                  {domains.length > 30 && (
                    <span className="text-xs text-muted-foreground self-center ml-1">
                      +{domains.length - 30}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Learning Statistics */}
          {learningStats && <LearningStatsBar stats={learningStats} variant="card" />}
        </CardContent>
      </Card>

      <ModerationModal
        domain={moderationDomain}
        open={!!moderationDomain}
        onClose={() => setModerationDomain(null)}
      />
    </TooltipProvider>
  )
}
