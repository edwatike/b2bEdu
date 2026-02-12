"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { motion } from "framer-motion"
import { getSuppliers } from "@/lib/api"
import { SupplierDTO } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Navigation } from "@/components/navigation"
import { PageShell } from "@/components/ui/PageShell"
import { LoadingState } from "@/components/ui/LoadingState"
import { EmptyState } from "@/components/ui/EmptyState"
import { SuppliersTableVirtualized } from "@/components/supplier/SuppliersTableVirtualized"
import { toast } from "sonner"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Plus, Building2, AlertTriangle, Search } from "lucide-react"

export function SuppliersClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const [suppliers, setSuppliers] = useState<SupplierDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const recentDays = Number(searchParams.get("recentDays") || "0")
  const recentDaysLabel = recentDays > 0 ? `Новые поставщики за ${recentDays} дней` : null
  const PAGE_SIZE = 50
  const pageParam = Number(searchParams.get("page") || "1")
  const [page, setPage] = useState(Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setPage(1)
    }, 400)
    return () => clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    setPage(1)
  }, [recentDays])

  useEffect(() => {
    loadSuppliers()
  }, [recentDays, page, debouncedSearch])

  async function loadSuppliers() {
    try {
      setLoading(true)
      const data = await getSuppliers({
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        recentDays: recentDays > 0 ? recentDays : undefined,
        search: debouncedSearch || undefined,
      })
      setTotal(Number(data.total || 0))
      setSuppliers(data.suppliers)
      setError(null)
    } catch (err) {
      toast.error("Ошибка загрузки поставщиков")
      setError("Ошибка загрузки поставщиков")
      console.error("Error loading suppliers:", err)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil((total || 0) / PAGE_SIZE))

  const goToPage = (nextPage: number) => {
    const safe = Math.min(Math.max(1, nextPage), totalPages)
    setPage(safe)
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", String(safe))
    router.replace(`${pathname}?${params.toString()}`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
        <Navigation />
        <PageShell title="Поставщики">
          <LoadingState message="Загрузка поставщиков..." size="lg" />
        </PageShell>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-red-50/30">
        <Navigation />
        <PageShell title="Поставщики">
          <EmptyState
            title="Ошибка загрузки"
            description={error}
            icon={<AlertTriangle className="h-12 w-12" />}
            action={<Button onClick={loadSuppliers}>Попробовать снова</Button>}
          />
        </PageShell>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
      <Navigation />
      <motion.main 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-6 max-w-7xl"
      >
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex items-center justify-between mb-6"
        >
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-primary-600 to-primary-700 flex items-center justify-center shadow-lg">
              <Building2 className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-primary-600 to-primary-800 bg-clip-text text-transparent">
                Поставщики
              </h1>
              <p className="text-neutral-600 mt-1">Управление поставщиками и реселлерами</p>
              {recentDaysLabel && (
                <p className="text-sm text-emerald-700 mt-1">{recentDaysLabel}</p>
              )}
            </div>
          </div>
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Button 
              onClick={() => router.push("/suppliers/new")} 
              className="bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 text-white shadow-lg"
            >
              <Plus className="mr-2 h-4 w-4" />
              Добавить поставщика
            </Button>
          </motion.div>
        </motion.div>

        {/* Search */}
        <div className="mb-4 max-w-md">
          <GlowSearchInput
            placeholder="Поиск по имени, ИНН, домену..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            containerClassName="w-full"
          />
        </div>

        {/* Таблица с новым компонентом */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
        >
          <SuppliersTableVirtualized suppliers={suppliers} onRefresh={() => loadSuppliers()} />
          <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-muted-foreground">
              Показано: {(page - 1) * PAGE_SIZE + suppliers.length} из {total || suppliers.length}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => goToPage(page - 1)} disabled={page <= 1}>
                Назад
              </Button>
              <div className="text-sm text-muted-foreground">
                Страница {page} из {totalPages}
              </div>
              <Button variant="outline" onClick={() => goToPage(page + 1)} disabled={page >= totalPages}>
                Вперёд
              </Button>
            </div>
          </div>
        </motion.div>
      </motion.main>
    </div>
  )
}
