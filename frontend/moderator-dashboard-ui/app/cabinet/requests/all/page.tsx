"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getCabinetRequests, submitCabinetRequest, updateCabinetRequest } from "@/lib/api"
import type { CabinetParsingRequestDTO } from "@/lib/types"

function RequestsAllPage() {
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
      const response = await getCabinetRequests({ limit: pageSize, offset: nextOffset })
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

  const handleEditRequest = async (req: CabinetParsingRequestDTO) => {
    if (req.submitted_to_moderator) return
    const title = window.prompt("Название заявки", req.title || "")?.trim()
    if (!title) return

    let keys: string[] | undefined = undefined
    try {
      const parsed = req.raw_keys_json ? JSON.parse(req.raw_keys_json) : []
      keys = Array.isArray(parsed) ? parsed.map((x) => String(x)) : undefined
    } catch {
      keys = undefined
    }
    const keysRaw = window.prompt("Ключи (через запятую)", (keys || []).join(", "))
    const nextKeys = (keysRaw || "")
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean)

    const depthRaw = window.prompt("Глубина парсинга (число)", String(req.depth || 10))?.trim()
    const depthParsed = Number(depthRaw)
    const depth = Number.isFinite(depthParsed) && depthParsed > 0 ? depthParsed : (req.depth || 10)

    const sourceRaw = window
      .prompt("Источник (google | yandex | both)", String(req.source || "google"))
      ?.trim()
      .toLowerCase()
    const source = sourceRaw === "yandex" || sourceRaw === "both" ? sourceRaw : "google"

    try {
      await updateCabinetRequest(req.id, { title, keys: nextKeys, depth, source })
      await loadRequests(undefined, "replace")
    } catch {
      setHasError(true)
    }
  }

  const handleSubmitRequest = async (req: CabinetParsingRequestDTO) => {
    if (req.submitted_to_moderator) return
    try {
      await submitCabinetRequest(req.id)
      await loadRequests(undefined, "replace")
    } catch {
      setHasError(true)
    }
  }

  const requestCards = useMemo(() => {
    return requests.map((req) => {
      const statusLabel = req.submitted_to_moderator ? "Отправлено" : "Черновик"
      const badgeClass = req.submitted_to_moderator
        ? "bg-blue-500/20 text-blue-200 border-blue-500/30"
        : "bg-amber-500/20 text-amber-200 border-amber-500/30"
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
          <h1 className="text-3xl font-semibold">Все заявки</h1>
          <p className="text-slate-300">Полный список заявок. Для создания/распознавания перейдите в рабочий экран.</p>
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => (window.location.href = "/cabinet/requests")}>Рабочий экран</Button>
        </div>

        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white">Заявки</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {hasError && <p className="text-sm text-rose-200">Не удалось загрузить заявки. Попробуйте позже.</p>}
            {isLoading && <p className="text-sm text-slate-300">Загрузка заявок...</p>}
            {!isLoading && requestCards.length === 0 && <p className="text-sm text-slate-400">Пока нет заявок.</p>}

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
                      window.location.href = "/cabinet/requests"
                    }}
                  >
                    Открыть в рабочем экране
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      window.open(`/cabinet/requests/${request.id}`, "_blank", "noopener,noreferrer")
                    }}
                  >
                    Поставщики/переписка
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void handleEditRequest(request.raw)}
                    disabled={Boolean(request.raw.submitted_to_moderator)}
                  >
                    Редактировать
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void handleSubmitRequest(request.raw)}
                    disabled={Boolean(request.raw.submitted_to_moderator)}
                  >
                    Отправить модератору
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

export default function RequestsAllPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <RequestsAllPage />
    </AuthGuard>
  )
}
