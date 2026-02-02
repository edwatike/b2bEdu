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

import { useState, useMemo, Fragment } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ChevronDown,
  ChevronRight,
  Eye,
  Edit,
  MoreHorizontal,
  Search,
  Filter,
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
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
  supplierType?: "supplier" | "reseller" | null | undefined
  supplierId?: number | null
  sources?: string[]
  isBlacklisted?: boolean
  lastUpdate?: string
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
}

// Density settings
type Density = "compact" | "comfortable" | "spacious"

const densityConfig = {
  compact: "py-1 px-2",
  comfortable: "py-2 px-3",
  spacious: "py-3 px-4",
}

// Status Badge Component (24px высотой)
function StatusBadge({ type }: { type: "supplier" | "reseller" | null | undefined }) {
  if (!type) return null

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
  }

  const cfg = config[type]

  return (
    <Badge variant="outline" className={`${cfg.bg} ${cfg.text} ${cfg.border} border text-xs font-medium h-6 px-2`}>
      <span className="mr-1">{cfg.icon}</span>
      {cfg.label}
    </Badge>
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
  supplierType?: "supplier" | "reseller" | null
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

      {supplierId && supplierType && (
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
          {supplierId ? (
            <DropdownMenuItem onClick={() => onEdit?.(domain, supplierId, supplierType!)}>
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
function ExpandableRowContent({ urls }: { urls: Array<{ url: string; source?: string | null }> }) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="bg-neutral-50 border-l-4 border-neutral-300"
    >
      <div className="px-8 py-3 space-y-1">
        {urls.map((urlEntry, idx) => (
          <div key={idx} className="flex items-center gap-2 text-sm">
            <ChevronRight className="h-3 w-3 text-neutral-400" />
            <span className="text-neutral-600">{urlEntry.url}</span>
            {urlEntry.source && (
              <Badge variant="outline" className="text-xs">
                {urlEntry.source}
              </Badge>
            )}
            <a href={urlEntry.url} target="_blank" rel="noopener noreferrer" className="ml-auto">
              <ExternalLink className="h-3 w-3 text-neutral-400 hover:text-neutral-600" />
            </a>
          </div>
        ))}
      </div>
    </motion.div>
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
}: ParsingResultsTableProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [internalSelectedDomains, setInternalSelectedDomains] = useState<Set<string>>(new Set())
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [density, setDensity] = useState<Density>("comfortable")
  const selectedDomains = controlledSelectedDomains ?? internalSelectedDomains

  // Filter groups by search
  const filteredGroups = useMemo(() => {
    if (!searchQuery) return groups
    const query = searchQuery.toLowerCase()
    return groups.filter((group) => group.domain.toLowerCase().includes(query))
  }, [groups, searchQuery])

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
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-neutral-400" />
            <Input
              placeholder="Поиск доменов..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button variant="outline" size="sm">
            <Filter className="h-4 w-4 mr-2" />
            Фильтры
          </Button>
        </div>
        <DensityControl density={density} onDensityChange={setDensity} />
      </div>

      {/* Bulk Actions Toolbar */}
      <BulkActionsToolbar
        selectedCount={selectedDomains.size}
        onBulkAction={handleBulkAction}
        onClearSelection={clearSelection}
      />

      {/* Table */}
      <div className="border border-neutral-200 rounded-lg overflow-hidden bg-white">
        <Table>
          <TableHeader className="bg-neutral-50 border-b border-neutral-200">
            <TableRow>
              <TableHead className="w-8">
                <Checkbox
                  checked={selectedDomains.size === filteredGroups.length && filteredGroups.length > 0}
                  onCheckedChange={toggleAllSelection}
                />
              </TableHead>
              <TableHead className="w-8"></TableHead>
              <TableHead className="font-medium text-neutral-900">Домен</TableHead>
              <TableHead className="font-medium text-neutral-900 w-20">URLs</TableHead>
              <TableHead className="font-medium text-neutral-900 w-32">Статус</TableHead>
              <TableHead className="font-medium text-neutral-900 w-40">Последнее обновление</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredGroups.map((group) => {
              const isExpanded = expandedRows.has(group.domain)
              const isSelected = selectedDomains.has(group.domain)

              return (
                <Fragment key={group.domain}>
                  <TableRow
                    className={`group transition-colors ${densityConfig[density]} ${
                      isSelected ? "bg-blue-50" : "hover:bg-neutral-50"
                    }`}
                  >
                    <TableCell className="w-8">
                      <div className="flex items-center gap-2">
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
                    </TableCell>
                    <TableCell className="w-8">
                      <BlacklistIndicator isBlacklisted={group.isBlacklisted || false} />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span
                          className="font-mono font-semibold text-sm text-neutral-900 cursor-pointer hover:text-blue-600"
                          onClick={() => onView?.(group.domain)}
                        >
                          {group.domain}
                        </span>
                        {group.sources?.includes("google") && (
                          <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                            G
                          </Badge>
                        )}
                        {group.sources?.includes("yandex") && (
                          <Badge variant="outline" className="text-xs bg-yellow-50 text-yellow-700 border-yellow-200">
                            Y
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-mono text-sm text-neutral-600">{group.totalUrls}</span>
                    </TableCell>
                    <TableCell>
                      <StatusBadge type={group.supplierType} />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-xs text-neutral-500">
                        <Clock className="h-3 w-3" />
                        {formatDate(group.lastUpdate)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <HoverActions
                        domain={group.domain}
                        supplierId={group.supplierId}
                        supplierType={group.supplierType}
                        onView={onView}
                        onEdit={onEdit}
                        onMenu={handleMenuAction}
                      />
                    </TableCell>
                  </TableRow>
                  {isExpanded && (
                    <TableRow className="bg-neutral-50">
                      <TableCell colSpan={7} className="p-0">
                        <ExpandableRowContent urls={group.urls} />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}

            {/* Empty state inside TableBody using proper TableRow/TableCell */}
            {filteredGroups.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-neutral-500">
                  <Search className="h-8 w-8 mx-auto mb-2 text-neutral-300" />
                  <p className="text-sm">Домены не найдены</p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

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
