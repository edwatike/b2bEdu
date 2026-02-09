"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Mail,
  Globe,
  ChevronRight,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { getRiskColor } from "@/lib/design-system"
import type { SupplierDTO } from "@/lib/types"

interface SuppliersTableVirtualizedProps {
  suppliers: SupplierDTO[]
  onRefresh: () => void
}

type SortField = "name" | "inn" | "type" | "email" | "domain"
type SortOrder = "asc" | "desc"

export function SuppliersTableVirtualized({ suppliers, onRefresh }: SuppliersTableVirtualizedProps) {
  const router = useRouter()
  const [sortField, setSortField] = useState<SortField>("name")
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc")

  const sorted = useMemo(() => {
    return [...suppliers].sort((a, b) => {
      let aValue: string | number = a[sortField] || ""
      let bValue: string | number = b[sortField] || ""
      if (typeof aValue === "string") aValue = aValue.toLowerCase()
      if (typeof bValue === "string") bValue = bValue.toLowerCase()
      if (sortOrder === "asc") return aValue > bValue ? 1 : aValue < bValue ? -1 : 0
      return aValue < bValue ? 1 : aValue > bValue ? -1 : 0
    })
  }, [suppliers, sortField, sortOrder])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortOrder("asc")
    }
  }

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
    return sortOrder === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />
  }

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="bg-muted/40 border-b px-4 py-3 grid grid-cols-12 gap-3 items-center text-sm font-medium text-muted-foreground">
        <button onClick={() => handleSort("name")} className="col-span-4 flex items-center gap-1.5 hover:text-foreground transition-colors text-left">
          Название / ИНН {getSortIcon("name")}
        </button>
        <button onClick={() => handleSort("type")} className="col-span-2 flex items-center gap-1.5 hover:text-foreground transition-colors text-left">
          Тип {getSortIcon("type")}
        </button>
        <div className="col-span-2">Email</div>
        <div className="col-span-2">Домен</div>
        <div className="col-span-1">Данные</div>
        <div className="col-span-1"></div>
      </div>

      {/* Rows — no scroll, full page */}
      {sorted.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {suppliers.length === 0 ? "Нет поставщиков" : "Ничего не найдено"}
        </div>
      ) : (
        sorted.map((supplier) => (
          <div
            key={supplier.id}
            onClick={() => router.push(`/suppliers/${supplier.id}`)}
            className="grid grid-cols-12 gap-3 items-center px-4 py-3 border-b last:border-b-0 hover:bg-muted/50 cursor-pointer transition-colors group"
          >
            <div className="col-span-4">
              <div className="font-medium text-sm truncate group-hover:text-primary transition-colors">{supplier.name}</div>
              <div className="text-xs text-muted-foreground">{supplier.inn || "—"}</div>
            </div>
            <div className="col-span-2">
              <Badge variant={supplier.type === "supplier" ? "default" : "secondary"} className="text-xs">
                {supplier.type === "supplier" ? "Поставщик" : "Реселлер"}
              </Badge>
            </div>
            <div className="col-span-2">
              <div className="flex items-center gap-1.5 text-sm truncate">
                {supplier.email && <Mail className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />}
                <span className="truncate">{supplier.email || "—"}</span>
              </div>
            </div>
            <div className="col-span-2">
              <div className="flex items-center gap-1.5 text-sm truncate">
                {supplier.domain && <Globe className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />}
                <span className="truncate">{supplier.domain || "—"}</span>
              </div>
            </div>
            <div className="col-span-1">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: getRiskColor(supplier.checkoData ? 30 : 70) }} />
                <span className="text-xs text-muted-foreground">{supplier.checkoData ? "Есть" : "Нет"}</span>
              </div>
            </div>
            <div className="col-span-1 flex justify-end">
              <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
        ))
      )}
    </Card>
  )
}
