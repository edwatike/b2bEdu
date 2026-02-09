"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Loader2, Calendar, Activity, Database, AlertCircle } from "lucide-react"
import { getDomainHistory, type DomainLogEntry } from "@/lib/api"
import { format } from "date-fns"
import { ru } from "date-fns/locale"

interface DomainHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  domain: string
}

export function DomainHistoryDialog({ open, onOpenChange, domain }: DomainHistoryDialogProps) {
  const [logs, setLogs] = useState<DomainLogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open && domain) {
      loadHistory()
    }
  }, [open, domain])

  const loadHistory = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getDomainHistory(domain, 100)
      setLogs(data.logs)
    } catch (err) {
      console.error("Failed to load domain history:", err)
      setError("Не удалось загрузить историю парсинга")
    } finally {
      setLoading(false)
    }
  }

  const getActionColor = (action: string) => {
    switch (action?.toLowerCase()) {
      case "completed":
      case "supplier":
      case "reseller":
        return "bg-emerald-100 text-emerald-800 border-emerald-200"
      case "failed":
      case "error":
        return "bg-red-100 text-red-800 border-red-200"
      case "processing":
      case "running":
        return "bg-blue-100 text-blue-800 border-blue-200"
      case "requires_moderation":
      case "needs_moderation":
        return "bg-amber-100 text-amber-800 border-amber-200"
      default:
        return "bg-neutral-100 text-neutral-800 border-neutral-200"
    }
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—"
    try {
      return format(new Date(dateStr), "d MMM yyyy HH:mm:ss", { locale: ru })
    } catch {
      return dateStr
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Activity className="h-5 w-5 text-blue-600" />
            История парсинга: {domain}
          </DialogTitle>
          <DialogDescription>
            Полная хронология обработки домена во всех запусках
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden min-h-[400px]">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
              <span className="ml-2 text-neutral-500">Загрузка истории...</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full text-red-500 gap-2">
              <AlertCircle className="h-6 w-6" />
              {error}
            </div>
          ) : logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-neutral-400 flex-col gap-2">
              <Database className="h-10 w-10 opacity-20" />
              <p>История пуста</p>
            </div>
          ) : (
            <ScrollArea className="h-full pr-4">
              <div className="relative border-l border-neutral-200 ml-4 space-y-6 py-2">
                {logs.map((log) => (
                  <div key={log.id} className="relative pl-6">
                    {/* Timeline dot */}
                    <div className="absolute -left-1.5 top-1.5 h-3 w-3 rounded-full border-2 border-white bg-blue-500 shadow-sm" />
                    
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" className={`${getActionColor(log.action)}`}>
                          {log.action}
                        </Badge>
                        <span className="text-xs text-neutral-400 flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(log.created_at)}
                        </span>
                      </div>
                      
                      {log.message && (
                        <p className="text-sm font-medium text-neutral-800 mt-1">
                          {log.message}
                        </p>
                      )}
                      
                      {log.details && Object.keys(log.details).length > 0 && (
                        <div className="mt-2 bg-neutral-50 rounded-md p-3 text-xs font-mono text-neutral-600 border border-neutral-100 overflow-x-auto">
                          <pre className="whitespace-pre-wrap">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        </div>
                      )}
                      
                      {log.run_id && (
                        <div className="mt-1 text-xs text-neutral-400">
                          Run ID: {log.run_id}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
