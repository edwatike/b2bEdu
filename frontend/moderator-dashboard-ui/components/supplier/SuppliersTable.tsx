"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  Eye,
  Edit,
  Ban,
  Trash2,
  Search,
  Filter,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Building2,
  Mail,
  Phone,
  Globe,
  MoreVertical,
  CheckSquare,
  ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Card } from "@/components/ui/card"
import { DataTable, DataTableHeader, DataTableRow, DataTableCell, DataTableEmpty } from "@/components/ui/data-table"
import { toast } from "sonner"
import { deleteSupplier, addToBlacklist } from "@/lib/api"
import { getRiskColor } from "@/lib/design-system"
import type { SupplierDTO } from "@/lib/types"

interface SuppliersTableProps {
  suppliers: SupplierDTO[]
  onRefresh: () => void
}

type SortField = "name" | "inn" | "type" | "email" | "domain"
type SortOrder = "asc" | "desc"

export function SuppliersTable({ suppliers, onRefresh }: SuppliersTableProps) {
  const router = useRouter()

  const [searchQuery, setSearchQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState<"all" | "supplier" | "reseller">("all")
  const [sortField, setSortField] = useState<SortField>("name")
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc")
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [isDeleting, setIsDeleting] = useState(false)

  const filteredAndSortedSuppliers = useMemo(() => {
    let result = [...suppliers]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (s) =>
          s.name?.toLowerCase().includes(query) ||
          s.inn?.toLowerCase().includes(query) ||
          s.email?.toLowerCase().includes(query) ||
          s.domain?.toLowerCase().includes(query),
      )
    }

    if (typeFilter !== "all") {
      result = result.filter((s) => s.type === typeFilter)
    }

    result.sort((a, b) => {
      let aVal = a[sortField] || ""
      let bVal = b[sortField] || ""

      if (typeof aVal === "string") aVal = aVal.toLowerCase()
      if (typeof bVal === "string") bVal = bVal.toLowerCase()

      if (aVal < bVal) return sortOrder === "asc" ? -1 : 1
      if (aVal > bVal) return sortOrder === "asc" ? 1 : -1
      return 0
    })

    return result
  }, [suppliers, searchQuery, typeFilter, sortField, sortOrder])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortOrder("asc")
    }
  }

  const handleSelectAll = () => {
    if (selectedIds.size === filteredAndSortedSuppliers.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredAndSortedSuppliers.map((s) => s.id)))
    }
  }

  const handleSelectOne = (id: number) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedIds(newSelected)
  }

  const handleView = (id: number) => {
    router.push(`/suppliers/${id}`)
  }

  const handleEdit = (id: number) => {
    router.push(`/suppliers/${id}/edit`)
  }

  const handleAddToBlacklist = async (supplier: SupplierDTO) => {
    if (!supplier.domain) {
      toast.error("Домен не указан")
      return
    }

    try {
      await addToBlacklist({
        domain: supplier.domain,
        reason: "Добавлен модератором из списка поставщиков",
        addedBy: "moderator",
      })
      toast.success(`${supplier.domain} добавлен в blacklist`)
      onRefresh()
    } catch (error) {
      toast.error("Ошибка добавления в blacklist")
      console.error(error)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Вы уверены, что хотите удалить этого поставщика?")) {
      return
    }

    try {
      await deleteSupplier(id)
      toast.success("Поставщик удален")
      onRefresh()
    } catch (error) {
      toast.error("Ошибка удаления поставщика")
      console.error(error)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return

    if (!confirm(`Вы уверены, что хотите удалить ${selectedIds.size} поставщиков?`)) {
      return
    }

    setIsDeleting(true)
    try {
      await Promise.all(Array.from(selectedIds).map((id) => deleteSupplier(id)))
      toast.success(`Удалено ${selectedIds.size} поставщиков`)
      setSelectedIds(new Set())
      onRefresh()
    } catch (error) {
      toast.error("Ошибка массового удаления")
      console.error(error)
    } finally {
      setIsDeleting(false)
    }
  }

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />
    }
    return sortOrder === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5 text-primary" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5 text-primary" />
    )
  }

  const calculateRiskScore = (supplier: SupplierDTO): number => {
    let score = 50
    if (supplier.revenue && supplier.revenue > 10000000) score -= 10
    if (supplier.profit && supplier.profit > 0) score -= 10
    if (supplier.legalCasesCount === 0) score -= 15
    if (supplier.legalCasesCount && supplier.legalCasesCount > 5) score += 20
    if (supplier.profit && supplier.profit < 0) score += 15
    return Math.max(0, Math.min(100, score))
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="p-4 bg-white/80 backdrop-blur-sm border-neutral-200 shadow-sm">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-neutral-400" />
            <Input
              id="suppliers-search"
              name="suppliers-search"
              autoComplete="off"
              placeholder="Поиск по названию, ИНН, email, домену..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          <Select value={typeFilter} onValueChange={(value: any) => setTypeFilter(value)}>
            <SelectTrigger className="w-full lg:w-[180px]">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все типы</SelectItem>
              <SelectItem value="supplier">Поставщики</SelectItem>
              <SelectItem value="reseller">Реселлеры</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Bulk actions */}
        <AnimatePresence>
          {selectedIds.size > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-4 pt-4 border-t border-neutral-100"
            >
              <div className="flex items-center justify-between bg-gradient-to-r from-primary-50 to-blue-50 p-3 rounded-xl border border-primary-200">
                <div className="flex items-center gap-2">
                  <CheckSquare className="h-5 w-5 text-primary-600" />
                  <span className="font-medium text-primary-900">Выбрано: {selectedIds.size}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => setSelectedIds(new Set())}>
                    Снять выбор
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleBulkDelete}
                    disabled={isDeleting}
                    className="gap-2"
                  >
                    <Trash2 className="h-4 w-4" />
                    {isDeleting ? "Удаление..." : "Удалить"}
                  </Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats */}
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Показано: {filteredAndSortedSuppliers.length} из {suppliers.length}
          </span>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-blue-500" />
              Поставщики: {suppliers.filter((s) => s.type === "supplier").length}
            </span>
            <span className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-purple-500" />
              Реселлеры: {suppliers.filter((s) => s.type === "reseller").length}
            </span>
          </div>
        </div>
      </Card>

      {/* Table */}
      <DataTable>
        <DataTableHeader className="grid-cols-[40px_1fr_120px_120px_160px_100px_80px]">
          <div className="flex items-center justify-center">
            <Checkbox
              checked={selectedIds.size === filteredAndSortedSuppliers.length && filteredAndSortedSuppliers.length > 0}
              onCheckedChange={handleSelectAll}
            />
          </div>
          <button
            onClick={() => handleSort("name")}
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            Название {getSortIcon("name")}
          </button>
          <button
            onClick={() => handleSort("inn")}
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            ИНН {getSortIcon("inn")}
          </button>
          <button
            onClick={() => handleSort("type")}
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            Тип {getSortIcon("type")}
          </button>
          <div>Контакты</div>
          <div>Риск</div>
          <div></div>
        </DataTableHeader>

        {filteredAndSortedSuppliers.length === 0 ? (
          <DataTableEmpty
            icon={<Building2 className="h-8 w-8 text-neutral-300" />}
            title="Поставщики не найдены"
            description="Попробуйте изменить параметры поиска или фильтры"
          />
        ) : (
          <AnimatePresence mode="popLayout">
            {filteredAndSortedSuppliers.map((supplier, index) => {
              const riskScore = calculateRiskScore(supplier)
              const riskColor = getRiskColor(riskScore)

              return (
                <DataTableRow
                  key={supplier.id}
                  index={index}
                  isSelected={selectedIds.has(supplier.id)}
                  onClick={() => handleView(supplier.id)}
                  className="grid-cols-[40px_1fr_120px_120px_160px_100px_80px] group"
                >
                  <DataTableCell className="flex items-center justify-center">
                    <Checkbox
                      checked={selectedIds.has(supplier.id)}
                      onCheckedChange={() => handleSelectOne(supplier.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </DataTableCell>

                  <DataTableCell>
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary-100 to-primary-200 flex items-center justify-center flex-shrink-0">
                        <Building2 className="h-5 w-5 text-primary-700" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-foreground truncate">{supplier.name}</p>
                        {supplier.domain && (
                          <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                            <Globe className="h-3 w-3 flex-shrink-0" />
                            {supplier.domain}
                          </p>
                        )}
                      </div>
                    </div>
                  </DataTableCell>

                  <DataTableCell>
                    <span className="font-mono text-sm">{supplier.inn || "—"}</span>
                  </DataTableCell>

                  <DataTableCell>
                    <Badge
                      variant="outline"
                      className={
                        supplier.type === "supplier"
                          ? "bg-blue-50 text-blue-700 border-blue-200"
                          : "bg-purple-50 text-purple-700 border-purple-200"
                      }
                    >
                      {supplier.type === "supplier" ? "Поставщик" : "Реселлер"}
                    </Badge>
                  </DataTableCell>

                  <DataTableCell>
                    <div className="space-y-1">
                      {supplier.email && (
                        <p className="text-xs flex items-center gap-1.5 text-muted-foreground truncate">
                          <Mail className="h-3 w-3 flex-shrink-0" />
                          {supplier.email}
                        </p>
                      )}
                      {supplier.phone && (
                        <p className="text-xs flex items-center gap-1.5 text-muted-foreground">
                          <Phone className="h-3 w-3 flex-shrink-0" />
                          {supplier.phone}
                        </p>
                      )}
                      {!supplier.email && !supplier.phone && <span className="text-xs text-muted-foreground">—</span>}
                    </div>
                  </DataTableCell>

                  <DataTableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-12 rounded-full bg-muted overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${riskScore}%` }}
                          transition={{ duration: 0.5, delay: index * 0.02 }}
                          className="h-full rounded-full"
                          style={{ backgroundColor: riskColor }}
                        />
                      </div>
                      <span className="text-xs font-medium tabular-nums" style={{ color: riskColor }}>
                        {riskScore}
                      </span>
                    </div>
                  </DataTableCell>

                  <DataTableCell className="flex items-center justify-end gap-1">
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleView(supplier.id)
                        }}
                        className="h-8 w-8 p-0"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleEdit(supplier.id)
                        }}
                        className="h-8 w-8 p-0"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleAddToBlacklist(supplier)}>
                            <Ban className="h-4 w-4 mr-2" />В Blacklist
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleDelete(supplier.id)} className="text-red-600">
                            <Trash2 className="h-4 w-4 mr-2" />
                            Удалить
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                  </DataTableCell>
                </DataTableRow>
              )
            })}
          </AnimatePresence>
        )}
      </DataTable>
    </div>
  )
}
