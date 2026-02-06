"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getCabinetRequestSuppliers, getCabinetRequests } from "@/lib/api"
import type { CabinetParsingRequestDTO, CabinetRequestSupplierDTO } from "@/lib/types"
import { Building2 } from "lucide-react"

function ResultsPage() {
  const [requests, setRequests] = useState<CabinetParsingRequestDTO[]>([])
  const [selectedRequestId, setSelectedRequestId] = useState<number | null>(null)
  const [suppliers, setSuppliers] = useState<CabinetRequestSupplierDTO[]>([])
  const [isLoadingRequests, setIsLoadingRequests] = useState(true)
  const [isLoadingSuppliers, setIsLoadingSuppliers] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedRequest = useMemo(
    () => requests.find((r) => r.id === selectedRequestId) || null,
    [requests, selectedRequestId],
  )

  useEffect(() => {
    let isMounted = true
    const loadRequests = async () => {
      setIsLoadingRequests(true)
      setError(null)
      try {
        const data = await getCabinetRequests({ submitted: true, limit: 50 })
        if (!isMounted) return
        setRequests(data || [])
        if (data && data.length > 0) {
          setSelectedRequestId(data[0].id)
        }
      } catch (fetchError) {
        if (!isMounted) return
        const message = fetchError instanceof Error ? fetchError.message : "Не удалось загрузить заявки"
        setError(message)
      } finally {
        if (!isMounted) return
        setIsLoadingRequests(false)
      }
    }

    loadRequests()
    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    const loadSuppliers = async () => {
      if (!selectedRequestId) {
        setSuppliers([])
        return
      }
      try {
        setIsLoadingSuppliers(true)
        setError(null)
        const response = await getCabinetRequestSuppliers(selectedRequestId)
        if (!isMounted) return
        setSuppliers(response || [])
      } catch (fetchError) {
        if (!isMounted) return
        const message = fetchError instanceof Error ? fetchError.message : "Не удалось загрузить поставщиков"
        setError(message)
        setSuppliers([])
      } finally {
        if (!isMounted) return
        setIsLoadingSuppliers(false)
      }
    }

    loadSuppliers()
    return () => {
      isMounted = false
    }
  }, [selectedRequestId])

  const statusMeta = (status: CabinetRequestSupplierDTO["status"]) => {
    if (status === "sent") {
      return { label: "Отправлено", className: "bg-blue-500/20 text-blue-200 border-blue-500/30" }
    }
    if (status === "replied") {
      return { label: "Ответ", className: "bg-emerald-500/20 text-emerald-200 border-emerald-500/30" }
    }
    return { label: "Ожидает", className: "bg-amber-500/20 text-amber-200 border-amber-500/30" }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      <UserNavigation />
      <motion.main
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="container mx-auto px-6 py-10"
      >
        <div className="flex flex-col gap-2 mb-8">
          <h1 className="text-3xl font-semibold">Результаты</h1>
          <p className="text-slate-300">Список найденных поставщиков и статусы коммуникаций.</p>
        </div>

        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="text-white">Поставщики</CardTitle>
              <p className="text-sm text-slate-400">
                {selectedRequest ? `Заявка: ${selectedRequest.title || "без названия"}` : "Выберите заявку"}
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Select
                value={selectedRequestId ? String(selectedRequestId) : ""}
                onValueChange={(value) => setSelectedRequestId(Number(value))}
                disabled={isLoadingRequests || requests.length === 0}
              >
                <SelectTrigger className="w-full sm:w-72 bg-slate-900 border-slate-700 text-white">
                  <SelectValue placeholder="Выберите заявку" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  {requests.map((request) => (
                    <SelectItem key={request.id} value={String(request.id)}>
                      #{request.id} · {request.title || "Без названия"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  if (selectedRequestId) {
                    window.location.href = `/cabinet/requests/${encodeURIComponent(String(selectedRequestId))}`
                  }
                }}
                disabled={!selectedRequestId}
              >
                Открыть заявку
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && <p className="text-sm text-rose-200">{error}</p>}
            {isLoadingRequests && <p className="text-sm text-slate-300">Загрузка заявок...</p>}
            {!isLoadingRequests && requests.length === 0 && (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-4 text-slate-300">
                Отправленных заявок пока нет. Создайте заявку и отправьте её в работу.
              </div>
            )}
            {isLoadingSuppliers && <p className="text-sm text-slate-300">Загрузка поставщиков...</p>}
            {!isLoadingSuppliers && selectedRequestId && suppliers.length === 0 && (
              <p className="text-sm text-slate-400">Пока нет найденных поставщиков для выбранной заявки.</p>
            )}
            {suppliers.map((supplier) => {
              const meta = statusMeta(supplier.status)
              return (
              <div
                key={supplier.supplier_id}
                className="flex flex-col gap-3 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Building2 className="h-5 w-5 text-slate-300" />
                    <div>
                      <p className="text-lg font-semibold text-white">{supplier.name}</p>
                      <p className="text-sm text-slate-400">{supplier.domain || "Домен не указан"}</p>
                    </div>
                  </div>
                  <Badge className={meta.className}>{meta.label}</Badge>
                </div>
                <div className="text-sm text-slate-300">{supplier.email || supplier.emails?.[0] || "email не указан"}</div>
                {supplier.last_error && <div className="text-xs text-rose-200">{supplier.last_error}</div>}
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary">
                    Открыть карточку
                  </Button>
                  <Button size="sm" variant="outline">
                    История писем
                  </Button>
                </div>
              </div>
              )
            })}
          </CardContent>
        </Card>
      </motion.main>
    </div>
  )
}

export default function ResultsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <ResultsPage />
    </AuthGuard>
  )
}
