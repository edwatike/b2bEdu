"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { motion } from "framer-motion"
import { AuthGuard } from "@/components/auth-guard"
import { UserNavigation } from "@/components/user-navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import {
  getCabinetRequest,
  getCabinetRequestSupplierMessages,
  getCabinetRequestSuppliers,
  sendCabinetRequestEmailToSupplier,
  sendCabinetRequestEmailToSuppliersBulk,
} from "@/lib/api"
import type { CabinetParsingRequestDTO, CabinetRequestSupplierDTO, CabinetRequestSupplierMessageDTO } from "@/lib/types"

function formatStatus(status: CabinetRequestSupplierDTO["status"]) {
  if (status === "sent") return "запрос отправлен"
  if (status === "replied") return "ответ получен"
  return "ответ не получен"
}

function statusBadgeClass(status: CabinetRequestSupplierDTO["status"]) {
  if (status === "replied") return "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
  if (status === "sent") return "bg-blue-500/20 text-blue-200 border-blue-500/30"
  return "bg-amber-500/20 text-amber-200 border-amber-500/30"
}

function RequestDetailPage() {
  const params = useParams<{ id: string }>()
  const requestId = Number(params?.id)

  const [request, setRequest] = useState<CabinetParsingRequestDTO | null>(null)
  const [positions, setPositions] = useState<string[]>([])

  const [suppliers, setSuppliers] = useState<CabinetRequestSupplierDTO[]>([])
  const [loadingSuppliers, setLoadingSuppliers] = useState(true)
  const [suppliersError, setSuppliersError] = useState<string | null>(null)

  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null)
  const [selectedSupplierIds, setSelectedSupplierIds] = useState<Set<number>>(new Set())

  const [messages, setMessages] = useState<CabinetRequestSupplierMessageDTO[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)

  const [threadOpen, setThreadOpen] = useState(false)

  const [isSending, setIsSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [sendSuccess, setSendSuccess] = useState<string | null>(null)


  const canLoad = Number.isFinite(requestId) && requestId > 0
  const [pollingSuppliers, setPollingSuppliers] = useState(false)

  async function loadRequest() {
    if (!canLoad) return
    try {
      const dto = await getCabinetRequest(requestId)
      setRequest(dto)
      try {
        const parsed = JSON.parse(dto?.raw_keys_json || "[]")
        if (Array.isArray(parsed)) {
          setPositions(parsed.map((x) => String(x)).filter((x) => x.trim().length > 0))
        } else {
          setPositions([])
        }
      } catch {
        setPositions([])
      }
    } catch {
      setRequest(null)
      setPositions([])
    }
  }

  const selectedSupplier = useMemo(
    () => suppliers.find((s) => s.supplier_id === selectedSupplierId) || null,
    [suppliers, selectedSupplierId],
  )

  async function loadSuppliers() {
    if (!canLoad) return
    setLoadingSuppliers(true)
    setSuppliersError(null)
    try {
      const list = await getCabinetRequestSuppliers(requestId)
      setSuppliers(list)
      if (list.length > 0 && selectedSupplierId == null) {
        setSelectedSupplierId(list[0].supplier_id)
      }

      setSelectedSupplierIds((prev) => {
        if (!prev.size) return prev
        const available = new Set(list.map((s) => s.supplier_id))
        const next = new Set<number>()
        for (const id of prev) {
          if (available.has(id)) next.add(id)
        }
        return next
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось загрузить поставщиков"
      setSuppliersError(msg)
    } finally {
      setLoadingSuppliers(false)
    }
  }

  async function loadMessages(supplierId: number) {
    if (!canLoad) return
    setLoadingMessages(true)
    setMessagesError(null)
    try {
      const list = await getCabinetRequestSupplierMessages(requestId, supplierId)
      setMessages(list)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось загрузить сообщения"
      setMessagesError(msg)
    } finally {
      setLoadingMessages(false)
    }
  }

  useEffect(() => {
    void loadRequest()
    void loadSuppliers()
  }, [requestId])

  useEffect(() => {
    if (!canLoad) return

    const intervalMs = 10000
    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const tick = async () => {
      if (cancelled) return
      setPollingSuppliers((prev) => {
        if (prev) return prev
        return true
      })

      try {
        const list = await getCabinetRequestSuppliers(requestId)
        if (cancelled) return

        setSuppliers(list)
        if (list.length > 0 && selectedSupplierId == null) {
          setSelectedSupplierId(list[0].supplier_id)
        }

        setSelectedSupplierIds((prev) => {
          if (!prev.size) return prev
          const available = new Set(list.map((s) => s.supplier_id))
          const next = new Set<number>()
          for (const id of prev) {
            if (available.has(id)) next.add(id)
          }
          return next
        })
      } catch {
        // Silent polling: no UI errors
      } finally {
        if (!cancelled) setPollingSuppliers(false)
      }
    }

    const schedule = () => {
      if (cancelled) return
      timeoutId = setTimeout(async () => {
        if (cancelled) return
        if (!pollingSuppliers) {
          await tick()
        }
        schedule()
      }, intervalMs)
    }

    schedule()

    return () => {
      cancelled = true

      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [canLoad, requestId, selectedSupplierId, pollingSuppliers])

  useEffect(() => {
    if (!threadOpen) return
    if (selectedSupplierId == null) return
    void loadMessages(selectedSupplierId)
  }, [selectedSupplierId, threadOpen])

  const handleSend = async () => {
    if (!selectedSupplier) return
    try {
      setIsSending(true)
      setSendError(null)
      setSendSuccess(null)
      const updated = await sendCabinetRequestEmailToSupplier(requestId, selectedSupplier.supplier_id)
      setSuppliers((prev) => prev.map((s) => (s.supplier_id === updated.supplier_id ? updated : s)))
      await loadMessages(selectedSupplier.supplier_id)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось отправить запрос"
      setSendError(msg)
    } finally {
      setIsSending(false)
    }
  }

  const handleSendBulk = async () => {
    if (!canLoad) return
    const ids = Array.from(selectedSupplierIds)
    if (!ids.length) {
      setSendError("Выберите поставщиков")
      return
    }
    try {
      setIsSending(true)
      setSendError(null)
      setSendSuccess(null)
      const res = await sendCabinetRequestEmailToSuppliersBulk(requestId, ids)
      setSendSuccess(`Отправлено писем: ${res.batches_sent}. Адресов: ${res.total_emails}`)
      await loadSuppliers()
      if (selectedSupplierId != null) {
        await loadMessages(selectedSupplierId)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось отправить запросы"
      setSendError(msg)
    } finally {
      setIsSending(false)
    }
  }

  const toggleSupplierSelected = (supplierId: number) => {
    setSelectedSupplierIds((prev) => {
      const next = new Set(prev)
      if (next.has(supplierId)) next.delete(supplierId)
      else next.add(supplierId)
      return next
    })
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
          <h1 className="text-3xl font-semibold">Заявка #{canLoad ? requestId : "—"}</h1>
          <p className="text-slate-300">Поставщики по заявке. Переписка открывается поверх по выбранному поставщику.</p>
        </div>

        {!canLoad && <p className="text-sm text-rose-200">Некорректный ID заявки.</p>}

        <div className="space-y-4">
          <Accordion type="single" collapsible defaultValue={positions.length ? "positions" : undefined}>
            <AccordionItem value="positions" className="border-slate-700/60">
              <AccordionTrigger className="text-white">Позиции (ключи)</AccordionTrigger>
              <AccordionContent>
                <Card className="bg-slate-900/60 border-slate-700">
                  <CardContent className="space-y-3 pt-6">
                    {positions.length === 0 ? (
                      <p className="text-sm text-slate-400">Позиции не указаны.</p>
                    ) : (
                      <div className="space-y-2">
                        {positions.slice(0, 80).map((p, idx) => (
                          <div
                            key={`${idx}-${p}`}
                            className="rounded-md border border-slate-700/60 bg-slate-950/20 px-3 py-2 text-sm text-slate-100"
                          >
                            {p}
                          </div>
                        ))}
                      </div>
                    )}

                    {request?.comment && <p className="text-xs text-slate-400">Комментарий: {request.comment}</p>}
                  </CardContent>
                </Card>
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          <Card className="bg-slate-900/60 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">Поставщики ({suppliers.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {!loadingSuppliers && !suppliersError && suppliers.length === 0 && (
                <p className="text-sm text-slate-400">Поставщики пока не найдены.</p>
              )}

              <ScrollArea className="h-[calc(100vh-340px)] rounded-md border border-slate-700/60 bg-slate-950/20">
                <div className="p-3 space-y-2" data-testid="supplier-list">
                  {suppliers.map((s, idx) => (
                    <div
                      key={s.supplier_id}
                      className={cn(
                        "w-full text-left rounded-lg border border-slate-700/60 bg-slate-900/40 p-3 transition",
                        s.supplier_id === selectedSupplierId ? "ring-1 ring-blue-400/60" : "hover:bg-slate-900/60",
                      )}
                      data-testid={`supplier-item-${s.supplier_id}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <label className="mt-1 flex items-center gap-2 text-xs text-slate-300">
                          <Checkbox
                            checked={selectedSupplierIds.has(s.supplier_id)}
                            onCheckedChange={() => toggleSupplierSelected(s.supplier_id)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </label>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedSupplierId(s.supplier_id)
                            setThreadOpen(true)
                          }}
                          className="flex-1 min-w-0 text-left"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                              <div className="truncate text-sm font-semibold text-white">{idx + 1}. {s.name}</div>
                              <div className="truncate text-xs text-slate-400">{s.email || s.domain || "—"}</div>
                              {s.source_url ? (
                                <a
                                  className="mt-1 block truncate text-xs text-blue-300 underline"
                                  href={s.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  title={s.source_url}
                                >
                                  {s.source_url}
                                </a>
                              ) : null}
                              {!!(s.keyword_urls && s.keyword_urls.length) && (
                                <div className="mt-1 space-y-1">
                                  {s.keyword_urls.map((ku, i) => (
                                    <a
                                      key={`${ku.keyword}-${ku.url}-${i}`}
                                      className="block truncate text-[11px] text-cyan-300 underline"
                                      href={ku.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      onClick={(e) => e.stopPropagation()}
                                      title={`${ku.keyword}: ${ku.url}`}
                                    >
                                      {ku.keyword ? `[${ku.keyword}] ` : ""}{ku.url}
                                    </a>
                                  ))}
                                </div>
                              )}
                            </div>
                            <Badge className={statusBadgeClass(s.status)} data-testid={`supplier-status-${s.supplier_id}`}>
                              {formatStatus(s.status)}
                            </Badge>
                          </div>
                          {s.last_error && <div className="mt-1 truncate text-xs text-rose-200">{s.last_error}</div>}
                        </button>
                      </div>
                      <div className="mt-2 flex gap-3">
                        <a
                          className="text-xs text-slate-300 underline"
                          href={`/suppliers/${encodeURIComponent(String(s.supplier_id))}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Открыть карточку
                        </a>
                        <button
                          type="button"
                          className="text-xs text-slate-300 underline"
                          onClick={() => {
                            setSelectedSupplierId(s.supplier_id)
                            setThreadOpen(true)
                          }}
                        >
                          Открыть переписку
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => void loadSuppliers()} disabled={loadingSuppliers}>
                  Обновить
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void handleSendBulk()}
                  disabled={isSending || selectedSupplierIds.size === 0}
                >
                  Отправить выбранным
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <Dialog open={threadOpen && Boolean(selectedSupplier)} onOpenChange={(open) => setThreadOpen(open)}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>Переписка</DialogTitle>
            </DialogHeader>

            {!selectedSupplier && <p className="text-sm text-slate-400">Выберите поставщика.</p>}

            {selectedSupplier && (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-lg font-semibold">{selectedSupplier.name}</div>
                    <div className="truncate text-sm text-slate-300">{selectedSupplier.email || "—"}</div>
                  </div>
                  <Badge className={statusBadgeClass(selectedSupplier.status)}>{formatStatus(selectedSupplier.status)}</Badge>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void handleSend()}
                    disabled={isSending || !selectedSupplier.email}
                    data-testid="send-request"
                  >
                    Отправить запрос
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void loadMessages(selectedSupplier.supplier_id)}
                    disabled={loadingMessages}
                  >
                    Обновить тред
                  </Button>
                </div>

                {sendError && <p className="text-sm text-rose-200">{sendError}</p>}
                {sendSuccess && <p className="text-sm text-emerald-200">{sendSuccess}</p>}

                <Separator className="bg-slate-700/60" />

                {loadingMessages && <p className="text-sm text-slate-300">Загрузка сообщений...</p>}
                {messagesError && <p className="text-sm text-rose-200">{messagesError}</p>}

                <ScrollArea className="h-[60vh] rounded-md border border-slate-700/60 bg-slate-950/20">
                  <div className="p-4 space-y-3" data-testid="supplier-thread">
                    {messages.length === 0 && !loadingMessages && !messagesError && (
                      <p className="text-sm text-slate-400">Сообщений пока нет.</p>
                    )}
                    {messages.map((m) => (
                      <div
                        key={m.id}
                        className={cn(
                          "rounded-lg border p-3",
                          m.direction === "out" ? "border-blue-500/30 bg-blue-500/10" : "border-emerald-500/30 bg-emerald-500/10",
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-xs text-slate-300">{m.direction === "out" ? "Исходящее" : "Входящее"}</div>
                          <div className="text-xs text-slate-400">{new Date(m.date).toLocaleString("ru-RU")}</div>
                        </div>
                        <div className="mt-1 text-sm font-semibold text-white">{m.subject}</div>
                        <div className="mt-2 text-sm text-slate-200 whitespace-pre-wrap">{m.body}</div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </motion.main>
    </div>
  )
}

export default function RequestDetailPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <RequestDetailPage />
    </AuthGuard>
  )
}
