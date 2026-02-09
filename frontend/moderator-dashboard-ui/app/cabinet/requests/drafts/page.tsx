"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getCabinetRequests } from "@/lib/api"
import type { CabinetParsingRequestDTO } from "@/lib/types"

function RequestsDraftsPage() {
  const [requests, setRequests] = useState<CabinetParsingRequestDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const pageSize = 50

  const loadRequests = async (signal?: { aborted: boolean }, mode: "replace" | "append" = "replace") => {
    try {
      setIsLoading(true)
      setHasError(false)
      const nextOffset = mode === "append" ? offset : 0
      const response = await getCabinetRequests({ limit: pageSize, offset: nextOffset, submitted: false })
      if (signal?.aborted) return
      const list = Array.isArray(response) ? response : []
      if (mode === "append") {
        setRequests((prev) => [...prev, ...list])
        setOffset(nextOffset + list.length)
      } else {
        setRequests(list)
        setOffset(list.length)
      }
      setHasMore(list.length === pageSize)
    } catch {
      if (signal?.aborted) return
      setHasError(true)
    } finally {
      if (signal?.aborted) return
      setIsLoading(false)
    }
  }

  useEffect(() => {
    let isMounted = true
    void loadRequests({ aborted: !isMounted }, "replace")
    return () => {
      isMounted = false
    }
  }, [])

  const requestCards = useMemo(() => {
    return requests.map((req) => {
      const statusLabel = "Черновик"
      const badgeClass = "bg-amber-500/20 text-amber-200 border-amber-500/30"
      let keysPreview: string[] = []
      try {
        if (req.raw_keys_json) {
          const parsed = JSON.parse(req.raw_keys_json)
          if (Array.isArray(parsed)) {
            keysPreview = parsed.slice(0, 3).map(String)
          }
        }
      } catch {}
      return {
        id: req.id,
        title: req.title || "Без названия",
        updated: req.updated_at || req.created_at || "—",
        statusLabel,
        badgeClass,
        raw: req,
        keysPreview,
      }
    })
  }, [requests])

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
          <h1 className="text-3xl font-semibold">Черновики</h1>
          <p className="text-slate-300">Не отправленные в работу заявки.</p>
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => (window.location.href = "/cabinet")}>Создать заявку</Button>
        </div>

        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white">Черновики</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {hasError && <p className="text-sm text-rose-200">Не удалось загрузить черновики. Попробуйте позже.</p>}
            {isLoading && <p className="text-sm text-slate-300">Загрузка черновиков...</p>}
            {!isLoading && requestCards.length === 0 && <p className="text-sm text-slate-400">Пока нет черновиков.</p>}

            {requestCards.map((request) => (
              <div key={request.id} className="flex flex-col gap-3 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-lg font-semibold text-white">#{request.id}</p>
                    <p className="text-sm text-slate-300">{request.title}</p>
                  </div>
                  <Badge className={request.badgeClass}>{request.statusLabel}</Badge>
                </div>
                <div className="flex items-center justify-between text-sm text-slate-300">
                  <span>Позиции: {request.keysPreview.join(", ") || "—"}</span>
                  <span>Обновлено: {request.updated}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      window.location.href = `/cabinet?draft=${encodeURIComponent(String(request.id))}`
                    }}
                  >
                    Открыть в рабочем экране
                  </Button>
                </div>
              </div>
            ))}

            {!isLoading && hasMore && (
              <div className="pt-2">
                <Button variant="outline" className="w-full" onClick={() => void loadRequests(undefined, "append")}>
                  Показать ещё
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.main>
    </div>
  )
}

export default function RequestsDraftsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <RequestsDraftsPage />
    </AuthGuard>
  )
}
