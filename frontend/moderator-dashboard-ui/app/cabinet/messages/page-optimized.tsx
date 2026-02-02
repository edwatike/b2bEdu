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
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { Mail, Paperclip, AlertCircle, RefreshCw, Search, Inbox, PaperclipIcon, X, Loader2, Send } from "lucide-react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { composeCabinetMessage, getCabinetMessages, getYandexMailMessage, getYandexMailMessages, sendYandexEmail, unspamYandexMailMessage, uploadAttachment } from "@/lib/api"
import type { CabinetMessageDTO } from "@/lib/types"
import { ComposeDialog } from "@/components/ComposeDialog"

type InlineAttachmentItem = {
  localId: string
  file: File
  status: "queued" | "uploading" | "done" | "error"
  uploadedId?: string
  error?: string
}

// Оптимизированные query ключи
const QUERY_KEYS = {
  yandexStatus: ["yandex", "status"],
  yandexFolderCounts: ["yandex", "folderCounts"],
  messages: (folder: string, connected: boolean) => ["messages", folder, connected],
  message: (id: string) => ["message", id],
} as const;

// Оптимизированные API функции с кэшированием
const fetchYandexStatus = async () => {
  const response = await fetch("/api/yandex/status", { cache: "no-store" });
  const data = await response.json().catch(() => ({ connected: false, email: null }));
  return { connected: Boolean(data?.connected), email: typeof data?.email === "string" ? data.email : null };
};

const fetchYandexFolderCounts = async () => {
  const response = await fetch("/api/yandex/mail/folders", { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  return data || {};
};

const fetchMessages = async ({ folder, yandexConnected }: { folder: string; yandexConnected: boolean }) => {
  if (yandexConnected) {
    const mappedMailbox = undefined; // Будет получено из folderCounts
    const imapFolder = folder === "spam" ? "SPAM" : folder === "sent" ? "Sent" : folder === "trash" ? "Trash" : "INBOX";
    const response = await getYandexMailMessages({ limit: 20, page: 1, folder: imapFolder });
    return response;
  } else {
    const data = await getCabinetMessages();
    return { messages: data, total: data.length, page: 1, limit: 20, demo: data.length > 0 && data[0].id?.toString().startsWith('demo_') };
  }
};

function MessagesPage() {
  const [folder, setFolder] = useState<"inbox" | "sent" | "spam" | "trash">("inbox")
  const [selectedMessage, setSelectedMessage] = useState<CabinetMessageDTO | null>(null)
  const [fullMessageBody, setFullMessageBody] = useState<string>("")
  const [fullMessageHtml, setFullMessageHtml] = useState<string>("")
  const [fullMessageAttachments, setFullMessageAttachments] = useState<CabinetMessageDTO["attachments"]>([])
  const [isOpeningMessage, setIsOpeningMessage] = useState(false)
  const [openMessageError, setOpenMessageError] = useState<string | null>(null)
  const [isUnspamming, setIsUnspamming] = useState(false)
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [composeOpen, setComposeOpen] = useState(false)
  const [inlineReplyOpen, setInlineReplyOpen] = useState(false)
  const [inlineReplyBody, setInlineReplyBody] = useState("")
  const [inlineReplyAttachments, setInlineAttachmentItems] = useState<InlineAttachmentItem[]>([])
  const [inlineReplySubmitting, setInlineReplySubmitting] = useState(false)
  const [inlineReplyUploadingCount, setInlineReplyUploadingCount] = useState(0)
  const [inlineReplyHasUploadError, setInlineReplyHasUploadError] = useState(false)
  
  const queryClient = useQueryClient();
  const inlineReplyTextareaRef = useRef<HTMLTextAreaElement>(null)
  const inlineReplyFileInputRef = useRef<HTMLInputElement>(null)
  const activeLoadIdRef = useRef(0)

  // Оптимизированный: один useEffect для debounce
  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(search)
    }, 350)
    return () => clearTimeout(handle)
  }, [search])

  // Оптимизированный: React Query для статуса Яндекса
  const { data: yandexStatus } = useQuery({
    queryKey: QUERY_KEYS.yandexStatus,
    queryFn: fetchYandexStatus,
    staleTime: 1000 * 60 * 2, // 2 минуты
    refetchInterval: false,
  });

  // Оптимизированный: React Query для счетчиков папок
  const { data: yandexFolderCounts } = useQuery({
    queryKey: QUERY_KEYS.yandexFolderCounts,
    queryFn: fetchYandexFolderCounts,
    enabled: yandexStatus?.connected,
    staleTime: 1000 * 60 * 5, // 5 минут
  });

  // Оптимизированный: React Query для сообщений с автоматическим обновлением
  const { 
    data: messagesData, 
    isLoading, 
    error,
    refetch: refetchMessages 
  } = useQuery({
    queryKey: QUERY_KEYS.messages(folder, yandexStatus?.connected || false),
    queryFn: () => fetchMessages({ folder, yandexConnected: yandexStatus?.connected || false }),
    staleTime: 1000 * 30, // 30 секунд
    refetchOnWindowFocus: false,
  });

  // Оптимизированный: мутации с автоматическим обновлением кэша
  const unspamMutation = useMutation({
    mutationFn: unspamYandexMailMessage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.messages(folder, true) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.yandexFolderCounts });
    },
  });

  const sendMessageMutation = useMutation({
    mutationFn: async ({ to, subject, body, attachments }: { to: string; subject: string; body: string; attachments: string[] }) => {
      if (yandexConnected) {
        if (attachments.length > 0) {
          throw new Error("Attachments are not supported for Yandex mail")
        }
        await sendYandexEmail({ to_email: to, subject, body });
      } else {
        await composeCabinetMessage({ to_email: to, subject, body, attachments });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.messages(folder, yandexConnected) });
      setComposeOpen(false);
    },
  });

  // Вычисляемые значения с мемоизацией
  const yandexConnected = yandexStatus?.connected || false;
  const yandexEmail = yandexStatus?.email || null;
  const messages = messagesData?.messages || [];
  const isDemoMode = messagesData?.demo || false;

  // Оптимизированная фильтрация с мемоизацией
  const filteredMessages = useMemo(() => {
    const q = debouncedSearch.trim().toLowerCase()
    return messages.filter((message) => {
      const matchesFolder = (() => {
        if (yandexConnected) return true;
        if (folder === "inbox") return true;
        if (folder === "sent") return message.status === "sent" || message.status === "replied";
        return false;
      })()
      if (!matchesFolder) return false;
      if (!q && statusFilter === "all") return true;
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

  // Оптимизированные обработчики с useCallback
  const handleRefresh = useCallback(() => {
    refetchMessages();
  }, [refetchMessages]);

  const handleMessageClick = useCallback(async (message: CabinetMessageDTO) => {
    if (selectedMessage?.id === message.id) return;
    
    setSelectedMessage(message);
    setFullMessageBody("");
    setFullMessageHtml("");
    setFullMessageAttachments([]);
    setIsOpeningMessage(true);
    setOpenMessageError(null);

    try {
      if (yandexConnected) {
        const fullMessage = await getYandexMailMessage(String(message.id));
        setFullMessageBody(fullMessage.body || "");
        setFullMessageHtml(fullMessage.html || "");
        setFullMessageAttachments(fullMessage.attachments || []);
      } else {
        setFullMessageBody(message.body || "");
        setFullMessageAttachments(message.attachments || []);
      }
    } catch (error) {
      setOpenMessageError(error instanceof Error ? error.message : "Не удалось загрузить письмо");
    } finally {
      setIsOpeningMessage(false);
    }
  }, [selectedMessage?.id, yandexConnected]);

  // Остальные функции...
  const handleUnspam = async (messageId: string) => {
    setIsUnspamming(true);
    try {
      await unspamMutation.mutateAsync(String(messageId));
    } catch (error) {
      console.error("Unspam error:", error);
    } finally {
      setIsUnspamming(false);
    }
  };

  const handleInlineReplySubmit = async () => {
    if (!selectedMessage || inlineReplySubmitting) return;
    
    setInlineReplySubmitting(true);
    try {
      await sendMessageMutation.mutateAsync({
        to: selectedMessage.from_email || "",
        subject: `Re: ${selectedMessage.subject || ""}`,
        body: inlineReplyBody,
        attachments: inlineReplyAttachments.filter(a => a.status === "done").map(a => a.uploadedId!),
      });
      setInlineReplyOpen(false);
      setInlineReplyBody("");
      setInlineAttachmentItems([]);
    } catch (error) {
      console.error("Reply error:", error);
    } finally {
      setInlineReplySubmitting(false);
    }
  };

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
              <div className="relative sm:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Поиск..."
                  className="pl-10 bg-slate-900 border-slate-700 text-white"
                />
              </div>
              
              <Select value={folder} onValueChange={(value: any) => setFolder(value)}>
                <SelectTrigger className="bg-slate-900 border-slate-700 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  <SelectItem value="inbox">Входящие</SelectItem>
                  <SelectItem value="sent">Отправленные</SelectItem>
                  <SelectItem value="spam">Спам</SelectItem>
                  <SelectItem value="trash">Корзина</SelectItem>
                </SelectContent>
              </Select>
              
              <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
                <RefreshCw className={cn("mr-2 h-4 w-4", isLoading ? "animate-spin" : "")} />
                {isLoading ? "Загрузка..." : "Обновить"}
              </Button>
            </div>
          </CardHeader>
          
          <CardContent>
            {error && (
              <div className="mb-4 p-3 rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-200 text-sm">
                {error instanceof Error ? error.message : "Ошибка загрузки писем"}
              </div>
            )}
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Список писем */}
              <div className="lg:col-span-1">
                <ScrollArea className="h-[60vh] lg:h-[70vh]">
                  <div className="space-y-2">
                    {filteredMessages.length === 0 ? (
                      <div className="text-center text-slate-400 py-8">
                        {isLoading ? "Загрузка..." : "Нет писем"}
                      </div>
                    ) : (
                      filteredMessages.map((message) => (
                        <div
                          key={message.id}
                          className={cn(
                            "p-3 rounded-lg border cursor-pointer transition-colors",
                            selectedMessage?.id === message.id
                              ? "bg-slate-800 border-slate-600"
                              : "bg-slate-900/40 border-slate-700/60 hover:bg-slate-800/60 hover:border-slate-600"
                          )}
                          onClick={() => handleMessageClick(message)}
                        >
                          <div className="flex items-start justify-between gap-2 mb-1">
                            <div className="min-w-0 flex-1">
                              <p className="font-medium text-white text-sm truncate">
                                {message.from_email || "Неизвестный отправитель"}
                              </p>
                              <p className="text-slate-300 text-xs truncate">
                                {message.subject || "Без темы"}
                              </p>
                            </div>
                            <div className="flex flex-col items-end gap-1 shrink-0">
                              {!message.is_read && (
                                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                              )}
                              <p className="text-xs text-slate-400 whitespace-nowrap">
                                {message.date
                                  ? new Date(message.date).toLocaleDateString("ru-RU", {
                                      day: "numeric",
                                      month: "short",
                                    })
                                  : ""}
                              </p>
                            </div>
                          </div>
                          <p className="text-xs text-slate-400 line-clamp-2">
                            {message.body?.substring(0, 100) || "Нет текста"}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </div>

              {/* Детали письма */}
              <div className="lg:col-span-2">
                {selectedMessage ? (
                  <div className="h-[60vh] lg:h-[70vh] flex flex-col">
                    <div className="flex items-center justify-between p-4 border-b border-slate-700">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-white truncate">
                          {selectedMessage.subject || "Без темы"}
                        </h3>
                        <p className="text-sm text-slate-300">
                          От: {selectedMessage.from_email || "Неизвестный отправитель"}
                        </p>
                        <p className="text-xs text-slate-400">
                          {selectedMessage.date
                            ? new Date(selectedMessage.date).toLocaleString("ru-RU")
                            : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {folder === "spam" && yandexConnected && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleUnspam(String(selectedMessage.id))}
                            disabled={isUnspamming}
                          >
                            Не спам
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="flex-1 p-4 overflow-auto">
                      {isOpeningMessage ? (
                        <div className="flex items-center justify-center h-full text-slate-400">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          Загрузка...
                        </div>
                      ) : openMessageError ? (
                        <div className="text-center text-rose-400">
                          {openMessageError}
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {fullMessageHtml ? (
                            <div 
                              className="rounded-md border border-slate-700/60 bg-slate-900/40 p-4 text-slate-100 prose prose-invert max-w-none"
                              dangerouslySetInnerHTML={{ __html: fullMessageHtml }}
                            />
                          ) : (
                            <div className="rounded-md border border-slate-700/60 bg-slate-900/40 p-4 text-slate-100 whitespace-pre-wrap break-words">
                              {fullMessageBody || "(Пусто)"}
                            </div>
                          )}

                          {fullMessageAttachments && fullMessageAttachments.length > 0 && (
                            <div className="rounded-md border border-slate-700/60 bg-slate-900/40 p-4">
                              <p className="text-sm font-medium text-white">Вложения</p>
                              <div className="mt-2 space-y-2">
                                {fullMessageAttachments.map((a) => (
                                  <a
                                    key={a.id}
                                    href={`/api/attachments/${encodeURIComponent(a.id)}`}
                                    className="flex items-center justify-between gap-3 rounded-md border border-slate-700/60 bg-slate-950/20 px-3 py-2 text-sm text-slate-100 hover:bg-slate-950/40"
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
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-400">
                    Выберите письмо слева
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.main>
      
      <ComposeDialog
        open={composeOpen}
        onOpenChange={setComposeOpen}
        mode="compose"
        onSubmit={handleInlineReplySubmit}
      />
    </div>
  )
}

export default function MessagesPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user"]}>
      <MessagesPage />
    </AuthGuard>
  )
}
