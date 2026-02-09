/**
 * ParsingResultsTable Component - MODERN REDESIGN 2026
 *
 * Современная таблица по best practices:
 * - Hover actions вместо кнопок в строках
 * - Subtle status badges (24px высотой)
 * - Compact density control
 * - Expandable rows
 * - Bulk selection toolbar
 * - Blacklist indicator (красная точка)
 *
 * Референсы: Linear.app, Notion, Airtable, GitHub Issues, Vercel Dashboard
 */

"use client"

import { useState, useRef, Fragment } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ChevronDown,
  ChevronRight,
  Eye,
  Edit,
  MoreHorizontal,
  Search,
  Settings,
  Download,
  AlertTriangle,
  Building2,
  Users,
  Clock,
  ExternalLink,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { useVirtualizer } from "@tanstack/react-virtual"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

// Types
interface ParsingDomainGroup {
  domain: string
  urls: Array<{
    url: string
    source?: string | null
    createdAt?: string
  }>
  totalUrls: number
  supplierType?: "supplier" | "reseller" | "needs_moderation" | null | undefined
  supplierId?: number | null
  hasChecko?: boolean
  sources?: string[]
  isBlacklisted?: boolean
  lastUpdate?: string
  reason?: string | null
  attemptedUrls?: string[]
  innSourceUrl?: string | null
  emailSourceUrl?: string | null
  runDomainId?: number | null
  extractionLog?: Array<{ url?: string; inn_found?: string; emails_found?: string[]; error?: string }>
  inn?: string | null
  emails?: string[]
  sourceUrls?: string[]
}

interface ParsingResultsTableProps {
  groups: ParsingDomainGroup[]
  selectedDomains?: Set<string>
  onSelectionChange?: (selectedDomains: Set<string>) => void
  onView?: (domain: string) => void
  onEdit?: (domain: string, supplierId: number, type: "supplier" | "reseller") => void
  onBlacklist?: (domain: string) => void
  onSupplier?: (domain: string, type: "supplier" | "reseller") => void
  onBulkAction?: (action: string, selectedDomains: Set<string>) => void
  onStatusClick?: (domain: string, supplierId: number | null | undefined, type: "supplier" | "reseller" | "needs_moderation") => void
}

// Density settings
type Density = "compact" | "comfortable" | "spacious"

const densityConfig = {
  compact: "py-1 px-2",
  comfortable: "py-2 px-3",
  spacious: "py-3 px-4",
}

// Status Badge Component (24px высотой) with tooltip
function StatusBadge({
  type,
  hasChecko,
  onClick,
  reason,
  attemptedUrls,
  innSourceUrl,
  emailSourceUrl,
}: {
  type: "supplier" | "reseller" | "needs_moderation" | null | undefined
  hasChecko?: boolean
  onClick?: () => void
  reason?: string | null
  attemptedUrls?: string[]
  innSourceUrl?: string | null
  emailSourceUrl?: string | null
}) {
  if (!type) return null
  const normalizedType = (type as any) === "requires_moderation" ? "needs_moderation" : type
  const config = {
    supplier: {
      bg: "bg-emerald-50",
      text: "text-emerald-700",
      border: "border-emerald-200",
      icon: "🏢",
      label: "Поставщик",
    },
    reseller: {
      bg: "bg-purple-50",
      text: "text-purple-700",
      border: "border-purple-200",
      icon: "🔄",
      label: "Реселлер",
    },
    needs_moderation: {
      bg: "bg-amber-50",
      text: "text-amber-700",
      border: "border-amber-200",
      icon: "⚠️",
      label: "Треб. модерация",
    },
  }
  const cfg = (config as any)[normalizedType]
  if (!cfg) return null

  // Build tooltip text
  let tooltipText = ""
  if (normalizedType === "needs_moderation") {
    if (reason) {
      const shortReason = reason.length > 120 ? reason.substring(0, 120) + "..." : reason
      tooltipText = `Причина: ${shortReason}`
    }
    if (attemptedUrls && attemptedUrls.length > 0) {
      const urlsStr = attemptedUrls.slice(0, 3).join(", ")
      tooltipText += tooltipText ? `\nПроверено: ${urlsStr}` : `Проверено: ${urlsStr}`
      if (attemptedUrls.length > 3) tooltipText += ` (+${attemptedUrls.length - 3})`
    }
  } else if (normalizedType === "supplier" || normalizedType === "reseller") {
    const parts: string[] = []
    if (innSourceUrl) parts.push(`INN: ${innSourceUrl}`)
    if (emailSourceUrl) parts.push(`Email: ${emailSourceUrl}`)
    if (parts.length > 0) tooltipText = parts.join("\n")
    if (hasChecko) tooltipText += (tooltipText ? "\n" : "") + "✓ Checko подтверждён"
  }

  return (
    <div className="relative group/badge inline-flex">
      <Badge
        variant="outline"
        role={onClick ? "button" : undefined}
        onClick={onClick}
        title={tooltipText || undefined}
        className={`${cfg.bg} ${cfg.text} ${cfg.border} border text-xs font-medium h-6 px-2 ${
          onClick ? "cursor-pointer hover:opacity-80" : ""
        }`}
      >
        <span className="mr-1">{cfg.icon}</span>
        {cfg.label}
        {(normalizedType === "supplier" || normalizedType === "reseller") && hasChecko ? <span className="ml-1">🛡 CHECKO</span> : null}
      </Badge>
      {tooltipText && (
        <div className="absolute left-0 top-full mt-1 bg-neutral-900 text-white text-xs px-3 py-2 rounded-lg shadow-lg opacity-0 group-hover/badge:opacity-100 transition-opacity pointer-events-none whitespace-pre-line z-50 max-w-xs">
          {tooltipText}
        </div>
      )}
    </div>
  )
}

// Blacklist Indicator
function BlacklistIndicator({ isBlacklisted }: { isBlacklisted: boolean }) {
  if (!isBlacklisted) return null

  return (
    <div className="relative group">
      <div className="w-2 h-2 bg-red-500 rounded-full"></div>
      <div className="absolute left-4 top-1/2 transform -translate-y-1/2 bg-neutral-900 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
        В черном списке
        <div className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-1">
          <div className="w-0 h-0 border-t-4 border-t-transparent border-b-4 border-b-transparent border-r-4 border-r-neutral-900"></div>
        </div>
      </div>
    </div>
  )
}

// Hover Actions Component
function HoverActions({
  onEdit,
  onView,
  onMenu,
  domain,
  supplierId,
  supplierType,
}: {
  onEdit?: (domain: string, supplierId: number, type: "supplier" | "reseller") => void
  onView?: (domain: string) => void
  onMenu?: (action: string, domain: string) => void
  domain: string
  supplierId?: number | null
  supplierType?: "supplier" | "reseller" | "needs_moderation" | null
}) {
  return (
    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 hover:bg-neutral-100"
        onClick={() => onView?.(domain)}
        title="Посмотреть детали"
      >
        <Eye className="h-3.5 w-3.5" />
      </Button>

      {supplierId && supplierType && supplierType !== "needs_moderation" && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 hover:bg-neutral-100"
          onClick={() => onEdit?.(domain, supplierId, supplierType)}
          title="Редактировать"
        >
          <Edit className="h-3.5 w-3.5" />
        </Button>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 hover:bg-neutral-100" title="Действия">
            <MoreHorizontal className="h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onClick={() => onMenu?.("blacklist", domain)}>
            <AlertTriangle className="h-4 w-4 mr-2 text-red-600" />В Blacklist
          </DropdownMenuItem>
          {supplierId && supplierType && supplierType !== "needs_moderation" ? (
            <DropdownMenuItem onClick={() => onEdit?.(domain, supplierId, supplierType)}>
              <Edit className="h-4 w-4 mr-2" />
              Изменить тип
            </DropdownMenuItem>
          ) : (
            <>
              <DropdownMenuItem onClick={() => onMenu?.("supplier", domain)}>
                <Building2 className="h-4 w-4 mr-2 text-emerald-600" />
                Сделать поставщиком
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onMenu?.("reseller", domain)}>
                <Users className="h-4 w-4 mr-2 text-purple-600" />
                Сделать реселлером
              </DropdownMenuItem>
            </>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => onMenu?.("parsing", domain)}>
            <Search className="h-4 w-4 mr-2" />
            Запустить парсинг
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

// Bulk Actions Toolbar
function BulkActionsToolbar({
  selectedCount,
  onBulkAction,
  onClearSelection,
}: {
  selectedCount: number
  onBulkAction: (action: string) => void
  onClearSelection: () => void
}) {
  if (selectedCount === 0) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between bg-neutral-50 border border-neutral-200 rounded-lg px-4 py-2 mb-3"
    >
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-neutral-900">Выбрано: {selectedCount}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onBulkAction("blacklist")}
          className="text-red-600 border-red-200 hover:bg-red-50"
        >
          <AlertTriangle className="h-4 w-4 mr-1" />В Blacklist
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              Изменить тип
              <ChevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => onBulkAction("supplier")}>
              <Building2 className="h-4 w-4 mr-2 text-emerald-600" />
              Поставщик
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onBulkAction("reseller")}>
              <Users className="h-4 w-4 mr-2 text-purple-600" />
              Реселлер
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button variant="outline" size="sm" onClick={() => onBulkAction("export")}>
          <Download className="h-4 w-4 mr-1" />
          Экспорт
        </Button>
      </div>
      <Button variant="ghost" size="sm" onClick={onClearSelection} className="text-neutral-500 hover:text-neutral-700">
        Очистить
      </Button>
    </motion.div>
  )
}

// Density Control
function DensityControl({
  density,
  onDensityChange,
}: {
  density: Density
  onDensityChange: (density: Density) => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <Settings className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <DropdownMenuItem
          onClick={() => onDensityChange("compact")}
          className={density === "compact" ? "bg-neutral-100" : ""}
        >
          Compact
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => onDensityChange("comfortable")}
          className={density === "comfortable" ? "bg-neutral-100" : ""}
        >
          Comfortable
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => onDensityChange("spacious")}
          className={density === "spacious" ? "bg-neutral-100" : ""}
        >
          Spacious
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// Expandable Row Content
function ExpandableRowContent({
  urls,
  extractionLog,
  inn,
  emails,
  sourceUrls,
  innSourceUrl,
  emailSourceUrl,
}: {
  urls: Array<{ url: string; source?: string | null }>
  extractionLog?: Array<{ url?: string; inn_found?: string; emails_found?: string[]; error?: string }>
  inn?: string | null
  emails?: string[]
  sourceUrls?: string[]
  innSourceUrl?: string | null
  emailSourceUrl?: string | null
}) {
  const resolvedInnUrl = innSourceUrl || extractionLog?.find((entry) => entry.inn_found)?.url
  const resolvedEmailUrl = emailSourceUrl || extractionLog?.find((entry) => entry.emails_found && entry.emails_found.length > 0)?.url
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="bg-neutral-50 border-l-4 border-neutral-300"
    >
      <div className="px-8 py-3 space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="rounded-lg border border-neutral-200 bg-white/70 px-3 py-2">
            <div className="text-xs font-semibold text-neutral-600 mb-2">Извлеченные данные</div>
            <div className="space-y-1 text-xs text-neutral-600">
              <div className="flex items-center gap-2">
                <span className="text-neutral-400">ИНН:</span>
                {inn ? (
                  <span className="font-medium text-blue-700">{inn}</span>
                ) : (
                  <span className="text-neutral-400">—</span>
                )}
                {resolvedInnUrl && (
                  <a
                    href={resolvedInnUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:text-blue-700"
                    title={resolvedInnUrl}
                  >
                    🔗
                  </a>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-neutral-400">Email:</span>
                {emails && emails.length > 0 ? (
                  <span className="font-medium text-emerald-700">{emails.join(", ")}</span>
                ) : (
                  <span className="text-neutral-400">—</span>
                )}
                {resolvedEmailUrl && (
                  <a
                    href={resolvedEmailUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-emerald-600 hover:text-emerald-700"
                    title={resolvedEmailUrl}
                  >
                    🔗
                  </a>
                )}
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-neutral-200 bg-white/70 px-3 py-2">
            <div className="text-xs font-semibold text-neutral-600 mb-2">Проверенные URL</div>
            <div className="space-y-1 text-xs text-neutral-600 max-h-[120px] overflow-y-auto">
              {(sourceUrls && sourceUrls.length > 0 ? sourceUrls : urls.map((entry) => entry.url)).map((url, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <ChevronRight className="h-3 w-3 text-neutral-400" />
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-700 truncate"
                    title={url}
                  >
                    {url}
                  </a>
                  <ExternalLink className="h-3 w-3 text-neutral-400 ml-auto" />
                </div>
              ))}
              {(!sourceUrls || sourceUrls.length === 0) && urls.length === 0 && (
                <span className="text-neutral-400">Нет URL</span>
              )}
            </div>
          </div>
        </div>
        {extractionLog && extractionLog.length > 0 && (
          <div className="rounded-lg border border-neutral-200 bg-white/70 px-3 py-2">
            <div className="text-xs font-semibold text-neutral-600 mb-2">Лог извлечения</div>
            <div className="space-y-1 text-[11px] text-neutral-600 max-h-[160px] overflow-y-auto">
              {extractionLog.map((entry, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="text-neutral-400">{idx + 1}.</span>
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {entry.url ? (
                        <a
                          href={entry.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-700 truncate max-w-[280px]"
                          title={entry.url}
                        >
                          {entry.url}
                        </a>
                      ) : (
                        <span className="text-neutral-400">URL неизвестен</span>
                      )}
                      {entry.inn_found && <Badge variant="outline" className="text-[10px]">ИНН</Badge>}
                      {entry.emails_found && entry.emails_found.length > 0 && (
                        <Badge variant="outline" className="text-[10px]">Email</Badge>
                      )}
                      {entry.error && <Badge variant="destructive" className="text-[10px]">Ошибка</Badge>}
                    </div>
                    {entry.error && <div className="text-[10px] text-red-600 mt-0.5">{entry.error}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// Virtualized Domain List
function VirtualizedDomainList({
  filteredGroups,
  selectedDomains,
  expandedRows,
  density,
  densityConfig,
  toggleAllSelection,
  toggleSelection,
  toggleExpand,
  onView,
  onEdit,
  onStatusClick,
  handleMenuAction,
  formatDate,
}: {
  filteredGroups: ParsingDomainGroup[]
  selectedDomains: Set<string>
  expandedRows: Set<string>
  density: Density
  densityConfig: Record<Density, string>
  toggleAllSelection: () => void
  toggleSelection: (domain: string) => void
  toggleExpand: (domain: string) => void
  onView?: (domain: string) => void
  onEdit?: (domain: string, supplierId: number, type: "supplier" | "reseller") => void
  onStatusClick?: (domain: string, supplierId: number | null | undefined, type: "supplier" | "reseller" | "needs_moderation") => void
  handleMenuAction: (action: string, domain: string) => void
  formatDate: (dateString?: string) => string
}) {
  const parentRef = useRef<HTMLDivElement>(null)

  if (filteredGroups.length === 0) {
    return (
      <div className="border border-neutral-200 rounded-lg overflow-hidden bg-white">
        <div className="text-center py-12 text-neutral-500">
          <Search className="h-8 w-8 mx-auto mb-2 text-neutral-300" />
          <p className="text-sm">Домены не найдены</p>
        </div>
      </div>
    )
  }

  return (
    <div className="border border-neutral-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center bg-neutral-50 border-b border-neutral-200 px-3 py-2 text-xs font-medium text-neutral-900">
        <div className="w-16 flex-shrink-0">
          <Checkbox
            checked={selectedDomains.size === filteredGroups.length && filteredGroups.length > 0}
            onCheckedChange={toggleAllSelection}
          />
        </div>
        <div className="w-8 flex-shrink-0"></div>
        <div className="flex-1">Домен</div>
        <div className="w-20 text-center">URLs</div>
        <div className="w-32 text-center">Статус</div>
        <div className="w-40 text-center">Последнее обновление</div>
        <div className="w-24"></div>
      </div>

      {/* Domain rows — full height, no scrollbar */}
      <div ref={parentRef}>
        {filteredGroups.map((group) => {
            const isExpanded = expandedRows.has(group.domain)
            const isSelected = selectedDomains.has(group.domain)

            return (
              <div key={group.domain}>
                <div
                  className={`group flex items-center px-3 ${densityConfig[density]} transition-colors border-b border-neutral-100 ${
                    isSelected ? "bg-blue-50" : "hover:bg-neutral-50"
                  }`}
                >
                  <div className="w-16 flex-shrink-0 flex items-center gap-2">
                    {group.urls.length > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => toggleExpand(group.domain)}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    )}
                    <Checkbox checked={isSelected} onCheckedChange={() => toggleSelection(group.domain)} />
                  </div>
                  <div className="w-8 flex-shrink-0">
                    <BlacklistIndicator isBlacklisted={group.isBlacklisted || false} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className="font-mono font-semibold text-sm text-neutral-900 cursor-pointer hover:text-blue-600 truncate"
                        onClick={() => onView?.(group.domain)}
                      >
                        {group.domain}
                      </span>
                      {group.sources?.includes("google") && (
                        <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">G</Badge>
                      )}
                      {group.sources?.includes("yandex") && (
                        <Badge variant="outline" className="text-xs bg-yellow-50 text-yellow-700 border-yellow-200">Y</Badge>
                      )}
                    </div>
                  </div>
                  <div className="w-20 text-center">
                    <span className="font-mono text-sm text-neutral-600">{group.totalUrls}</span>
                  </div>
                  <div className="w-32 text-center">
                    <StatusBadge
                      type={group.supplierType}
                      hasChecko={group.hasChecko}
                      reason={group.reason}
                      attemptedUrls={group.attemptedUrls}
                      innSourceUrl={group.innSourceUrl}
                      emailSourceUrl={group.emailSourceUrl}
                      onClick={
                        group.supplierType
                          ? () =>
                              onStatusClick?.(
                                group.domain,
                                group.supplierId,
                                group.supplierType as "supplier" | "reseller" | "needs_moderation",
                              )
                          : undefined
                      }
                    />
                  </div>
                  <div className="w-40 text-center">
                    <div className="flex items-center justify-center gap-1 text-xs text-neutral-500">
                      <Clock className="h-3 w-3" />
                      {formatDate(group.lastUpdate)}
                    </div>
                  </div>
                  <div className="w-24">
                    <HoverActions
                      domain={group.domain}
                      supplierId={group.supplierId}
                      supplierType={group.supplierType}
                      onView={onView}
                      onEdit={onEdit}
                      onMenu={handleMenuAction}
                    />
                  </div>
                </div>

                {isExpanded && (
                  <ExpandableRowContent
                    urls={group.urls}
                    extractionLog={group.extractionLog}
                    inn={group.inn}
                    emails={group.emails}
                    sourceUrls={group.sourceUrls}
                    innSourceUrl={group.innSourceUrl}
                    emailSourceUrl={group.emailSourceUrl}
                  />
                )}
              </div>
            )
          })}
      </div>
    </div>
  )
}

// Main Component
export function ParsingResultsTable({
  groups,
  selectedDomains: controlledSelectedDomains,
  onSelectionChange,
  onView,
  onEdit,
  onBlacklist,
  onSupplier,
  onBulkAction,
  onStatusClick,
}: ParsingResultsTableProps) {
  const [internalSelectedDomains, setInternalSelectedDomains] = useState<Set<string>>(new Set())
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [density, setDensity] = useState<Density>("comfortable")
  const selectedDomains = controlledSelectedDomains ?? internalSelectedDomains

  const filteredGroups = groups

  // Selection handlers
  const toggleSelection = (domain: string) => {
    const newSelection = new Set(selectedDomains)
    if (newSelection.has(domain)) {
      newSelection.delete(domain)
    } else {
      newSelection.add(domain)
    }
    if (!controlledSelectedDomains) {
      setInternalSelectedDomains(newSelection)
    }
    onSelectionChange?.(newSelection)
  }

  const toggleAllSelection = () => {
    if (selectedDomains.size === filteredGroups.length) {
      const cleared = new Set<string>()
      if (!controlledSelectedDomains) {
        setInternalSelectedDomains(cleared)
      }
      onSelectionChange?.(cleared)
    } else {
      const next = new Set(filteredGroups.map((g) => g.domain))
      if (!controlledSelectedDomains) {
        setInternalSelectedDomains(next)
      }
      onSelectionChange?.(next)
    }
  }

  const clearSelection = () => {
    const cleared = new Set<string>()
    if (!controlledSelectedDomains) {
      setInternalSelectedDomains(cleared)
    }
    onSelectionChange?.(cleared)
  }

  // Expandable rows
  const toggleExpand = (domain: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(domain)) {
      newExpanded.delete(domain)
    } else {
      newExpanded.add(domain)
    }
    setExpandedRows(newExpanded)
  }

  // Action handlers
  const handleMenuAction = (action: string, domain: string) => {
    switch (action) {
      case "blacklist":
        onBlacklist?.(domain)
        break
      case "supplier":
        onSupplier?.(domain, "supplier")
        break
      case "reseller":
        onSupplier?.(domain, "reseller")
        break
      case "parsing":
        // Handle parsing action
        break
    }
  }

  const handleBulkAction = (action: string) => {
    onBulkAction?.(action, selectedDomains)
  }

  // Format date
  const formatDate = (dateString?: string) => {
    if (!dateString) return "—"
    try {
      const trimmed = dateString.trim()
      if (!trimmed) return "—"
      const normalized = trimmed.includes("T") ? trimmed : trimmed.replace(" ", "T")
      const date = new Date(normalized)
      if (Number.isNaN(date.getTime())) return "—"
      return date.toLocaleString("ru-RU", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return "—"
    }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-end">
        <DensityControl density={density} onDensityChange={setDensity} />
      </div>

      {/* Bulk Actions Toolbar */}
      <BulkActionsToolbar
        selectedCount={selectedDomains.size}
        onBulkAction={handleBulkAction}
        onClearSelection={clearSelection}
      />

      {/* Virtualized Table */}
      <VirtualizedDomainList
        filteredGroups={filteredGroups}
        selectedDomains={selectedDomains}
        expandedRows={expandedRows}
        density={density}
        densityConfig={densityConfig}
        toggleAllSelection={toggleAllSelection}
        toggleSelection={toggleSelection}
        toggleExpand={toggleExpand}
        onView={onView}
        onEdit={onEdit}
        onStatusClick={onStatusClick}
        handleMenuAction={handleMenuAction}
        formatDate={formatDate}
      />

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-neutral-500 px-1">
        <span>
          Показано {filteredGroups.length} из {groups.length}
        </span>
        <span>Плотность: {density}</span>
      </div>
    </div>
  )
}
