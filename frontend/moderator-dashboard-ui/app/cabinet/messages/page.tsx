"use client"

import { motion } from "framer-motion"
import { useEffect, useMemo, useRef, useState, useCallback } from "react"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { GlowSearchInput } from "@/components/ui/glow-search-input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { Mail, Paperclip, AlertCircle, RefreshCw, Inbox, PaperclipIcon, X, Loader2, Send, Maximize2 } from "lucide-react"
import { composeCabinetMessage, getCabinetMessages, getYandexMailMessage, getYandexMailMessages, sendYandexEmail, unspamYandexMailMessage, uploadAttachment } from "@/lib/api"
import { fetchAllMailData } from "@/lib/optimized-api"
import type { CabinetMessageDTO } from "@/lib/types"
import { ComposeDialog } from "@/components/ComposeDialog"

type InlineAttachmentItem = {
  localId: string
  file: File
  status: "queued" | "uploading" | "done" | "error"
  uploadedId?: string
  error?: string
}

function MessagesPage() {
  const [messages, setMessages] = useState<CabinetMessageDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [yandexConnected, setYandexConnected] = useState(false)
  const [yandexEmail, setYandexEmail] = useState<string | null>(null)
  const [folder, setFolder] = useState<"inbox" | "sent" | "spam" | "trash">("inbox")
  const [yandexFolderCounts, setYandexFolderCounts] = useState<Record<string, { mailbox?: string; total: number; unseen: number }>>({})
  const activeLoadIdRef = useRef(0)
  const [selectedMessage, setSelectedMessage] = useState<CabinetMessageDTO | null>(null)
  const [fullMessageBody, setFullMessageBody] = useState<string>("")
  const [fullMessageHtml, setFullMessageHtml] = useState<string>("")
  const [fullMessageAttachments, setFullMessageAttachments] = useState<CabinetMessageDTO["attachments"]>([])
  const [isOpeningMessage, setIsOpeningMessage] = useState(false)
  const [openMessageError, setOpenMessageError] = useState<string | null>(null)
  const [isUnspamming, setIsUnspamming] = useState(false)
  const [fullScreenOpen, setFullScreenOpen] = useState(false)
  const [webmailOpen, setWebmailOpen] = useState(false)
  const [webmailFullScreenOpen, setWebmailFullScreenOpen] = useState(false)
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [composeOpen, setComposeOpen] = useState(false)
  const [inlineReplyOpen, setInlineReplyOpen] = useState(false)
  const [inlineReplyBody, setInlineReplyBody] = useState("")
  const [inlineReplyAttachments, setInlineReplyAttachments] = useState<InlineAttachmentItem[]>([])
  const [inlineReplySubmitting, setInlineReplySubmitting] = useState(false)
  const inlineReplyFileInputRef = useRef<HTMLInputElement | null>(null)
  const inlineReplyTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const inlineReplyWrapRef = useRef<HTMLDivElement | null>(null)

  const formatDateTime = (value: string) => {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    return d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(search)
    }, 350)
    return () => {
      window.clearTimeout(handle)
    }
  }, [search])

  const buildSafeEmailHtml = (html: string) => {
    const normalized = String(html || "")
    if (!normalized.trim()) return ""

    return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <base target="_blank" />
    <style>
      body{margin:0;padding:16px;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:15px;line-height:1.6;color:#333;background:#fff}
      img{max-width:100%;height:auto}
      pre{white-space:pre-wrap;word-break:break-word;background:#f5f5f5;padding:12px;border-radius:4px}
      a{color:#0066cc}
      blockquote{margin:0 0 1em 0;padding-left:1em;border-left:3px solid #ddd;color:#666}
    </style>
  </head>
  <body>${normalized}</body>
</html>`
  }

  const loadMessages = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getCabinetMessages()
      setMessages(data)
      
      // Проверяем если это демо-данные (для Яндекс.Почты)
      if (data.length > 0 && data[0].id?.toString().startsWith('demo_')) {
        setIsDemoMode(true)
      }
    } catch (fetchError) {
      const message = fetchError instanceof Error ? fetchError.message : "Не удалось загрузить письма"
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  const loadYandexMessages = async () => {
    const loadId = ++activeLoadIdRef.current
    setIsLoading(true)
    setIsRefreshing(true)
    setError(null)
    try {
      const mappedMailbox = yandexFolderCounts?.[folder]?.mailbox
      const imapFolder = mappedMailbox || (folder === "spam" ? "SPAM" : folder === "sent" ? "Sent" : folder === "trash" ? "Trash" : "INBOX")
      const response = await getYandexMailMessages({ limit: 20, page: 1, folder: imapFolder })
      if (loadId !== activeLoadIdRef.current) return
      setMessages(response.messages)
      // Если API вернул ошибку авторизации, считаем что подключение отсутствует
      if (response.error && String(response.error).toLowerCase().includes("not connected")) {
        setYandexConnected(false)
        setIsDemoMode(true)
        // Не показываем красную ошибку — это ожидаемое состояние (Яндекс не подключён)
        setError(null)
        return
      }

      // Если сообщения пришли без ошибки — считаем подключение активным
      if (!response.error) {
        setYandexConnected(true)
      }

      setIsDemoMode(Boolean(response.demo))
      if (response.error) {
        setError(response.error)
      }
      
      if (response.demo) {
        console.log("Working with demo data - Yandex OAuth not connected or API unavailable")
      }
    } catch (fetchError) {
      const message = fetchError instanceof Error ? fetchError.message : "Не удалось загрузить письма с Яндекс.Почты"
      if (loadId !== activeLoadIdRef.current) return
      setError(message)
      // Fallback к демо-данным
      const demoMessages = [
        {
          id: 'demo_1',
          subject: 'Добро пожаловать в B2B Platform',
          from_email: 'system@b2b-platform.com',
          to_email: 'admin@example.com',
          date: new Date().toISOString(),
          body: 'Это демо-сообщение. Для просмотра реальных писем подключите Яндекс.Почту.',
          status: 'received' as const,
          attachments_count: 0,
          is_read: false,
        },
        {
          id: 'demo_2',
          subject: 'Тестовое сообщение',
          from_email: 'test@example.com',
          to_email: 'admin@example.com',
          date: new Date(Date.now() - 86400000).toISOString(),
          body: 'Это тестовое демо-сообщение для проверки работы интерфейса почты.',
          status: 'received' as const,
          attachments_count: 0,
          is_read: true,
        }
      ]
      setMessages(demoMessages)
      setIsDemoMode(true)
    } finally {
      if (loadId !== activeLoadIdRef.current) return
      setIsRefreshing(false)
      setIsLoading(false)
    }
  }

  const handleOpen = async (message: CabinetMessageDTO) => {
    setSelectedMessage(message)
    setFullMessageBody(message.body || "")
    setFullMessageHtml("")
    setFullMessageAttachments([])
    setOpenMessageError(null)

    // Для Яндекс.Почты подгружаем полное письмо (html/text) по id
    if (yandexConnected && !String(message.id).startsWith("demo_")) {
      setIsOpeningMessage(true)
      try {
        const full = await getYandexMailMessage(String(message.id))
        if ((full as any)?.error) {
          throw new Error(String((full as any).error))
        }
        const html = full?.html ? buildSafeEmailHtml(full.html) : ""
        setFullMessageHtml(html)
        setFullMessageBody(full?.body || message.body || "")
        setFullMessageAttachments(Array.isArray((full as any)?.attachments) ? ((full as any).attachments as any) : [])

        // помечаем как прочитанное локально
        setMessages((prev) =>
          prev.map((m) => (m.id === message.id ? { ...m, is_read: true } : m)),
        )
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Не удалось открыть письмо"
        setOpenMessageError(msg)
      } finally {
        setIsOpeningMessage(false)
      }
    }
  }

  const openFullScreen = () => {
    if (!selectedMessage) return
    setFullScreenOpen(true)
  }

  const closeFullScreen = () => {
    setFullScreenOpen(false)
  }

  const handleUnspam = async () => {
    if (!selectedMessage) return
    if (isUnspamming) return
    if (!yandexConnected) return
    if (folder !== "spam") return
    if (String(selectedMessage.id).startsWith("demo_")) return

    setIsUnspamming(true)
    try {
      await unspamYandexMailMessage(String(selectedMessage.id))
      setSelectedMessage(null)
      setFullMessageBody("")
      setFullMessageHtml("")
      setFullMessageAttachments([])
      try {
        const resp = await fetch("/api/yandex/folders", { cache: "no-store" })
        const data = await resp.json().catch(() => null)
        if (resp.ok && data?.folders) {
          const next: Record<string, { mailbox?: string; total: number; unseen: number }> = {}
          for (const [role, meta] of Object.entries<any>(data.folders)) {
            next[role] = {
              mailbox: String(meta?.mailbox || ""),
              total: Number(meta?.total || 0),
              unseen: Number(meta?.unseen || 0),
            }
          }
          setYandexFolderCounts(next)
        }
      } catch {
        // ignore
      }
      await loadYandexMessages()
    } finally {
      setIsUnspamming(false)
    }
  }

  const handleRetryOpen = async () => {
    if (!selectedMessage) return
    await handleOpen(selectedMessage)
  }

  const inlineReplyUploadingCount = useMemo(
    () => inlineReplyAttachments.filter((a) => a.status === "queued" || a.status === "uploading").length,
    [inlineReplyAttachments],
  )

  const inlineReplyHasUploadError = useMemo(
    () => inlineReplyAttachments.some((a) => a.status === "error"),
    [inlineReplyAttachments],
  )

  const inlineReplyUploadedIds = useMemo(
    () => inlineReplyAttachments.filter((a) => a.status === "done" && a.uploadedId).map((a) => a.uploadedId as string),
    [inlineReplyAttachments],
  )

  const startInlineReplyUpload = async (localId: string, file: File) => {
    setInlineReplyAttachments((prev) =>
      prev.map((a) => (a.localId === localId ? { ...a, status: "uploading", error: undefined } : a)),
    )
    try {
      const uploaded = await uploadAttachment(file)
      setInlineReplyAttachments((prev) =>
        prev.map((a) => (a.localId === localId ? { ...a, status: "done", uploadedId: uploaded.id, error: undefined } : a)),
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось загрузить файл"
      setInlineReplyAttachments((prev) => prev.map((a) => (a.localId === localId ? { ...a, status: "error", error: msg } : a)))
    }
  }

  const addInlineReplyFiles = (files: FileList | File[]) => {
    const list = Array.from(files)
    if (list.length === 0) return
    const newItems: InlineAttachmentItem[] = list.map((file) => ({
      localId: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      file,
      status: "queued",
    }))
    setInlineReplyAttachments((prev) => [...prev, ...newItems])
    for (const item of newItems) {
      void startInlineReplyUpload(item.localId, item.file)
    }
  }

  const removeInlineReplyAttachment = (localId: string) => {
    setInlineReplyAttachments((prev) => prev.filter((a) => a.localId !== localId))
  }

  const openInlineReply = () => {
    if (!selectedMessage) return
    setInlineReplyOpen(true)
    setInlineReplyBody("")
    setInlineReplyAttachments([])
    requestAnimationFrame(() => {
      inlineReplyWrapRef.current?.scrollIntoView({ block: "nearest" })
      inlineReplyTextareaRef.current?.focus()
    })
  }

  const closeInlineReply = () => {
    setInlineReplyOpen(false)
    setInlineReplyBody("")
    setInlineReplyAttachments([])
  }

  const handleInlineReplySubmit = async () => {
    if (!selectedMessage) return
    if (inlineReplySubmitting) return
    if (inlineReplyUploadingCount > 0 || inlineReplyHasUploadError) return

    const to = selectedMessage.from_email || ""
    const subject = selectedMessage.subject ? `Re: ${selectedMessage.subject}` : "Re:"
    const body = inlineReplyBody
    const attachments = inlineReplyUploadedIds

    setInlineReplySubmitting(true)
    try {
      await handleReplySubmit(to, subject, body, attachments)
      // локально помечаем как replied (best-effort)
      setMessages((prev) => prev.map((m) => (m.id === selectedMessage.id ? { ...m, status: "replied" } : m)))
      closeInlineReply()
    } finally {
      setInlineReplySubmitting(false)
    }
  }

  const handleCompose = async () => {
    setComposeOpen(true)
  }

  const handleComposeSubmit = async (to: string, subject: string, body: string, attachments: string[]) => {
    try {
      // Пробуем отправить через Яндекс.Почту
      if (!yandexConnected) {
        throw new Error("Yandex OAuth not connected")
      }
      if (attachments.length > 0) {
        throw new Error("Attachments are not supported for Yandex mail")
      }
      await sendYandexEmail({ to_email: to, subject, body })
      try {
        const resp = await fetch("/api/yandex/folders", { cache: "no-store" })
        const data = await resp.json().catch(() => null)
        if (resp.ok && data?.folders) {
          const next: Record<string, { mailbox?: string; total: number; unseen: number }> = {}
          for (const [role, meta] of Object.entries<any>(data.folders)) {
            next[role] = {
              mailbox: String(meta?.mailbox || ""),
              total: Number(meta?.total || 0),
              unseen: Number(meta?.unseen || 0),
            }
          }
          setYandexFolderCounts(next)
        }
      } catch {
        // ignore
      }
      await loadYandexMessages()
    } catch (yandexError) {
      // Fallback к обычной отправке
      try {
        await composeCabinetMessage({ to_email: to, subject, body, attachments })
        setError(null)
        await loadMessages()
      } catch (fallbackError) {
        const message = fallbackError instanceof Error ? fallbackError.message : "Не удалось отправить письмо"
        setError(message)
        throw fallbackError
      }
    }
  }

  const handleReplySubmit = async (to: string, subject: string, body: string, attachments: string[]) => {
    try {
      // Пробуем отправить через Яндекс.Почту
      if (!yandexConnected) {
        throw new Error("Yandex OAuth not connected")
      }
      if (attachments.length > 0) {
        throw new Error("Attachments are not supported for Yandex mail")
      }
      await sendYandexEmail({ to_email: to, subject, body })

      try {
        const resp = await fetch("/api/yandex/folders", { cache: "no-store" })
        const data = await resp.json().catch(() => null)
        if (resp.ok && data?.folders) {
          const next: Record<string, { mailbox?: string; total: number; unseen: number }> = {}
          for (const [role, meta] of Object.entries<any>(data.folders)) {
            next[role] = {
              mailbox: String(meta?.mailbox || ""),
              total: Number(meta?.total || 0),
              unseen: Number(meta?.unseen || 0),
            }
          }
          setYandexFolderCounts(next)
        }
      } catch {
        // ignore
      }
      
      // Обновляем список писем
      await loadYandexMessages()
    } catch (composeError) {
      // Fallback к обычной отправке
      try {
        await composeCabinetMessage({ to_email: to, subject, body, attachments })
        setError(null)
        await loadMessages()
      } catch (fallbackError) {
        const errText = fallbackError instanceof Error ? fallbackError.message : "Не удалось отправить письмо"
        setError(errText)
        throw fallbackError
      }
    }
  }

  useEffect(() => {
    const el = inlineReplyTextareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [inlineReplyBody, inlineReplyOpen])

  // Оптимизированный: объединенная загрузка всех данных
  useEffect(() => {
    let isMounted = true
    const loadId = ++activeLoadIdRef.current

    const loadAllData = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        const data = await fetchAllMailData({ folder, yandexConnected })
        if (!isMounted || loadId !== activeLoadIdRef.current) return

        setYandexConnected(data.status.connected)
        setYandexEmail(data.status.email)
        setYandexFolderCounts(data.folderCounts)
        setMessages(data.messages.messages)
        setIsDemoMode(data.messages.demo || false)
        
        if (data.error) {
          setError(data.error)
        }
      } catch (fetchError) {
        if (!isMounted || loadId !== activeLoadIdRef.current) return
        const message = fetchError instanceof Error ? fetchError.message : "Не удалось загрузить данные"
        setError(message)
      } finally {
        if (!isMounted || loadId !== activeLoadIdRef.current) return
        setIsLoading(false)
        setIsRefreshing(false)
      }
    }

    loadAllData()
    return () => {
      isMounted = false
    }
  }, [folder])

  const filteredMessages = useMemo(() => {
    const q = debouncedSearch.trim().toLowerCase()
    return messages.filter((message) => {
      const matchesFolder = (() => {
        if (yandexConnected) {
          return true
        }
        if (folder === "inbox") return true
        if (folder === "sent") return message.status === "sent" || message.status === "replied"
        if (folder === "trash") return false
        if (folder === "spam") return false
        return true
      })()
      if (!matchesFolder) return false
      if (!q && statusFilter === "all") return true
      if (!q && statusFilter !== "all") {
        return message.status === statusFilter
      }
      const subject = (message.subject ?? "").toLowerCase()
      const from = (message.from_email ?? "").toLowerCase()
      const to = (message.to_email ?? "").toLowerCase()
      const matchesSearch = subject.includes(q) || from.includes(q) || to.includes(q)
      const matchesStatus = statusFilter === "all" || message.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [messages, debouncedSearch, folder, statusFilter, yandexConnected])

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
          <h1 className="text-3xl font-semibold">Почта</h1>
          <p className="text-slate-300">
            {isDemoMode ? "Демо-режим: показаны тестовые письма" : "История всех отправленных и полученных сообщений."}
          </p>
        </div>

        {isDemoMode && (
          <Card className="bg-amber-500/10 border-amber-500/30 mb-6">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-amber-400" />
                <div>
                  <p className="text-amber-200 font-medium">Демо-режим</p>
                  <p className="text-amber-300 text-sm">
                    Для просмотра реальных писем необходимо авторизоваться через Яндекс.Почту
                  </p>
                  {yandexEmail && <p className="text-amber-300 text-xs mt-1">{yandexEmail}</p>}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <CardTitle className="text-white">Письма</CardTitle>
              {!isLoading && (
                <Badge className="bg-slate-500/20 text-slate-200 border-slate-500/30">
                  {filteredMessages.length}
                </Badge>
              )}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
              <div className="w-full sm:max-w-[314px]">
                <GlowSearchInput
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Поиск..."
                  containerClassName="w-full"
                  className="bg-slate-900 text-white"
                />
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-40 bg-slate-900 border-slate-700 text-white">
                  <SelectValue placeholder="Статус" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  <SelectItem value="all">Все</SelectItem>
                  <SelectItem value="received">Получено</SelectItem>
                  <SelectItem value="sent">Отправлено</SelectItem>
                  <SelectItem value="replied">Ответ</SelectItem>
                  <SelectItem value="waiting">Ожидание</SelectItem>
                </SelectContent>
              </Select>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={loadYandexMessages} disabled={isRefreshing}>
                  <RefreshCw className={cn("mr-2 h-4 w-4", isRefreshing ? "animate-spin" : "")} />
                  {isRefreshing ? "Загрузка..." : "Загрузить Яндекс.Почту"}
                </Button>
                <Button
                  variant={webmailOpen ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => setWebmailOpen((v) => !v)}
                >
                  {webmailOpen ? "Закрыть Webmail" : "Открыть Webmail"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Загружаем письма...</div>
            ) : error ? (
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-6 text-rose-100">{error}</div>
            ) : filteredMessages.length === 0 ? (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Пока нет писем.</div>
            ) : webmailOpen ? (
              <div className="h-[70vh] w-full overflow-hidden rounded-lg border border-slate-700/60 bg-slate-950/20">
                <div className="flex items-center justify-between gap-3 border-b border-slate-700/60 px-3 py-2">
                  <p className="text-sm text-slate-200 truncate">Roundcube</p>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => setWebmailFullScreenOpen(true)}>
                      На весь экран
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setWebmailOpen(false)}>
                      Закрыть
                    </Button>
                  </div>
                </div>
                <iframe className="h-full w-full" src="/webmail" title="roundcube-embedded" />
              </div>
            ) : (
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-1">
                    <div className="space-y-2">
                      {filteredMessages.map((message) => (
                        <button
                          key={message.id}
                          type="button"
                          onClick={() => void handleOpen(message)}
                          className={cn(
                            "w-full text-left rounded-lg border border-slate-700/60 bg-slate-950/20 px-3 py-2 hover:bg-slate-950/40",
                            selectedMessage?.id === message.id ? "border-blue-500/60" : "",
                          )}
                        >
                          <p className="text-sm text-white truncate">{message.subject || "(Без темы)"}</p>
                          <p className="text-xs text-slate-400 truncate">{message.from_email}</p>
                          <p className="text-[11px] text-slate-500 truncate">{formatDateTime(message.date)}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="lg:col-span-2 min-w-0">
                    {selectedMessage ? (
                      <div className="rounded-lg border border-slate-700/60 bg-slate-950/20 p-4 min-w-0">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h2 className="text-lg font-semibold text-white truncate">{selectedMessage.subject || "(Без темы)"}</h2>
                            <p className="text-xs text-slate-300 mt-1">
                              <span className="text-slate-400">От:</span> {selectedMessage.from_email}
                            </p>
                            <p className="text-xs text-slate-300">
                              <span className="text-slate-400">Кому:</span> {selectedMessage.to_email}
                            </p>
                          </div>
                          <Button size="sm" variant="outline" onClick={openFullScreen}>
                            На весь экран
                          </Button>
                        </div>
                        <Separator className="bg-slate-700/60 my-3" />
                        <div className="rounded-md border border-slate-700/60 bg-slate-900/40 p-4 text-slate-100 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                          {fullMessageBody || selectedMessage.body || "(Пусто)"}
                        </div>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-400">Выберите письмо слева</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Dialog open={fullScreenOpen} onOpenChange={setFullScreenOpen}>
          <DialogContent className="fixed inset-0 z-50 w-screen max-w-none translate-x-0 translate-y-0 left-0 top-0 h-screen rounded-none border-0 bg-slate-950 p-0 shadow-none">
            <div className="h-full w-full flex flex-col">
              <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-xs text-slate-400">Письмо</p>
                  <p className="text-sm font-semibold text-white truncate">
                    {selectedMessage?.subject || "(Без темы)"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {yandexConnected && folder === "spam" && selectedMessage && !String(selectedMessage.id).startsWith("demo_") && (
                    <Button size="sm" variant="outline" onClick={handleUnspam} disabled={isUnspamming || isOpeningMessage}>
                      {isUnspamming ? "Перенос…" : "Не спам"}
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" onClick={openInlineReply} disabled={!selectedMessage}>
                    Ответить
                  </Button>
                  <Button size="sm" variant="outline" onClick={closeFullScreen}>
                    Закрыть
                  </Button>
                </div>
              </div>

              <div className="flex-1 min-h-0 overflow-hidden p-4">
                {selectedMessage ? (
                  <div className="h-full flex flex-col gap-3 min-h-0">
                    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                      <p className="text-xs text-slate-300">
                        <span className="text-slate-500">От:</span> {selectedMessage.from_email}
                      </p>
                      <p className="text-xs text-slate-300">
                        <span className="text-slate-500">Кому:</span> {selectedMessage.to_email}
                      </p>
                      <p className="text-xs text-slate-500">{formatDateTime(selectedMessage.date)}</p>
                    </div>

                    {openMessageError && (
                      <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 text-rose-100">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm">Не удалось загрузить письмо целиком.</p>
                            <p className="text-xs text-rose-200/80 mt-1 break-words">{openMessageError}</p>
                          </div>
                          <Button size="sm" variant="outline" onClick={() => void handleRetryOpen()} disabled={isOpeningMessage}>
                            Повторить
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="flex-1 min-h-0 min-w-0">
                      {fullMessageHtml ? (
                        <iframe
                          className="w-full h-full rounded-md border border-slate-800 bg-white min-w-0"
                          sandbox=""
                          srcDoc={fullMessageHtml}
                          title="email-fullscreen"
                        />
                      ) : (
                        <ScrollArea className="h-full min-h-0">
                          <div className="rounded-md border border-slate-800 bg-slate-900/40 p-4 text-slate-100 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                            {fullMessageBody || "(Пусто)"}
                          </div>
                        </ScrollArea>
                      )}
                    </div>

                    {fullMessageAttachments && fullMessageAttachments.length > 0 && (
                      <div className="rounded-md border border-slate-800 bg-slate-900/40 p-4">
                        <p className="text-sm font-medium text-white">Вложения</p>
                        <div className="mt-2 space-y-2">
                          {fullMessageAttachments.map((a) => (
                            <a
                              key={a.id}
                              href={`/api/attachments/${encodeURIComponent(a.id)}`}
                              className="flex items-center justify-between gap-3 rounded-md border border-slate-800 bg-slate-950/20 px-3 py-2 text-sm text-slate-100 hover:bg-slate-950/40"
                              target="_blank"
                              rel="noreferrer"
                            >
                              <span className="flex items-center gap-2 min-w-0">
                                <Paperclip className="h-4 w-4 shrink-0" />
                                <span className="truncate">{a.filename}</span>
                              </span>
                              <span className="text-xs text-slate-400 shrink-0">{Math.round((a.size || 0) / 1024)} KB</span>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-400">Выберите письмо</div>
                )}
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={webmailFullScreenOpen} onOpenChange={setWebmailFullScreenOpen}>
          <DialogContent className="fixed inset-0 z-50 w-screen max-w-none translate-x-0 translate-y-0 left-0 top-0 h-screen rounded-none border-0 bg-slate-950 p-0 shadow-none">
            <div className="h-full w-full flex flex-col">
              <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-xs text-slate-400">Webmail</p>
                  <p className="text-sm font-semibold text-white truncate">Roundcube</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => setWebmailFullScreenOpen(false)}>
                    Закрыть
                  </Button>
                </div>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden">
                <iframe className="h-full w-full" src="/webmail" title="roundcube-fullscreen" />
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </motion.main>
      
      <ComposeDialog
        open={composeOpen}
        onOpenChange={setComposeOpen}
        mode="compose"
        onSubmit={handleComposeSubmit}
      />
    </div>
  )
}

export default function MessagesPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <MessagesPage />
    </AuthGuard>
  )
}
