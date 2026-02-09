"use client"

import type React from "react"
import { useEffect, useMemo, useRef, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { AlertCircle, Loader2, Paperclip, X } from "lucide-react"
import { uploadAttachment } from "@/lib/api"
import { cn } from "@/lib/utils"

interface ComposeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "compose" | "reply"
  defaultTo?: string
  defaultSubject?: string
  defaultBody?: string
  onSubmit: (to: string, subject: string, body: string, attachments: string[]) => Promise<void>
}

type AttachmentItem = {
  localId: string
  file: File
  status: "queued" | "uploading" | "done" | "error"
  uploadedId?: string
  error?: string
}

export function ComposeDialog({
  open,
  onOpenChange,
  mode,
  defaultTo = "",
  defaultSubject = "",
  defaultBody = "",
  onSubmit,
}: ComposeDialogProps) {
  const [to, setTo] = useState(defaultTo)
  const [subject, setSubject] = useState(defaultSubject)
  const [body, setBody] = useState(defaultBody)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [attachments, setAttachments] = useState<AttachmentItem[]>([])
  const [isDragActive, setIsDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    if (!open) return
    setTo(defaultTo)
    setSubject(defaultSubject)
    setBody(defaultBody)
    setAttachments([])
    setIsDragActive(false)
  }, [open, defaultTo, defaultSubject, defaultBody])

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [body, open])

  const uploadingCount = useMemo(() => attachments.filter((a) => a.status === "uploading" || a.status === "queued").length, [attachments])
  const hasUploadError = useMemo(() => attachments.some((a) => a.status === "error"), [attachments])
  const uploadedIds = useMemo(
    () => attachments.filter((a) => a.status === "done" && a.uploadedId).map((a) => a.uploadedId as string),
    [attachments],
  )

  const startUpload = async (localId: string, file: File) => {
    setAttachments((prev) => prev.map((a) => (a.localId === localId ? { ...a, status: "uploading", error: undefined } : a)))
    try {
      const uploaded = await uploadAttachment(file)
      setAttachments((prev) =>
        prev.map((a) => (a.localId === localId ? { ...a, status: "done", uploadedId: uploaded.id, error: undefined } : a)),
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось загрузить файл"
      setAttachments((prev) => prev.map((a) => (a.localId === localId ? { ...a, status: "error", error: msg } : a)))
    }
  }

  const addFiles = (files: FileList | File[]) => {
    const list = Array.from(files)
    if (list.length === 0) return

    const newItems: AttachmentItem[] = list.map((file) => ({
      localId: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      file,
      status: "queued",
    }))

    setAttachments((prev) => [...prev, ...newItems])
    for (const item of newItems) {
      void startUpload(item.localId, item.file)
    }
  }

  const removeAttachment = (localId: string) => {
    setAttachments((prev) => prev.filter((a) => a.localId !== localId))
  }

  const handleChooseFile = () => {
    fileInputRef.current?.click()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!to.trim() || !subject.trim() || !body.trim()) return
    if (uploadingCount > 0 || hasUploadError) return
    setIsSubmitting(true)
    try {
      await onSubmit(to.trim(), subject.trim(), body.trim(), uploadedIds)
      onOpenChange(false)
      // Reset form
      setTo("")
      setSubject("")
      setBody("")
      setAttachments([])
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "sm:max-w-[560px] bg-slate-900 border-slate-700 text-white",
          isDragActive ? "ring-2 ring-blue-500/60" : "",
        )}
        onDragEnter={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setIsDragActive(true)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setIsDragActive(true)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setIsDragActive(false)
        }}
        onDrop={handleDrop}
      >
        <DialogHeader>
          <DialogTitle>{mode === "compose" ? "Новое письмо" : "Ответить"}</DialogTitle>
          <DialogDescription className="sr-only">
            {mode === "compose" ? "Создание нового письма" : "Ответ на письмо"}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="to">Кому</Label>
            <Input
              id="to"
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="email@example.com"
              className="bg-slate-800 border-slate-600 text-white"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="subject">Тема</Label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Тема письма"
              className="bg-slate-800 border-slate-600 text-white"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="body">Текст</Label>
            <Textarea
              id="body"
              ref={textareaRef}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
                  e.preventDefault()
                  void handleSubmit(e as unknown as React.FormEvent)
                }
              }}
              placeholder="Текст письма..."
              rows={4}
              className="bg-slate-800 border-slate-600 text-white resize-none overflow-hidden"
              required
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Вложения</Label>
              <Button type="button" variant="outline" size="sm" onClick={handleChooseFile} disabled={isSubmitting}>
                <Paperclip className="mr-2 h-4 w-4" />
                Прикрепить
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                multiple
                onChange={(e) => {
                  if (e.target.files) addFiles(e.target.files)
                  e.target.value = ""
                }}
              />
            </div>

            {attachments.length > 0 && (
              <div className="rounded-md border border-slate-700/60 bg-slate-950/20 p-2">
                <div className="space-y-2">
                  {attachments.map((a) => (
                    <div key={a.localId} className="flex items-center justify-between gap-2 rounded-md bg-slate-900/40 px-2 py-1">
                      <div className="min-w-0">
                        <p className="text-sm text-slate-100 truncate">{a.file.name}</p>
                        <p className="text-[11px] text-slate-400">
                          {a.status === "uploading" ? "Загрузка…" : a.status === "queued" ? "В очереди…" : a.status === "done" ? "Готово" : "Ошибка"}
                        </p>
                        {a.status === "error" && a.error && (
                          <p className="text-[11px] text-rose-300 break-words">{a.error}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {(a.status === "uploading" || a.status === "queued") && <Loader2 className="h-4 w-4 animate-spin" />}
                        {a.status === "error" && <AlertCircle className="h-4 w-4 text-rose-400" />}
                        <Button type="button" variant="ghost" size="icon" onClick={() => removeAttachment(a.localId)} disabled={isSubmitting}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {isDragActive && (
              <div className="rounded-md border border-dashed border-blue-500/50 bg-blue-500/10 p-3 text-sm text-blue-200">
                Отпустите файл, чтобы прикрепить
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Отмена
            </Button>
            <Button type="submit" disabled={isSubmitting || uploadingCount > 0 || hasUploadError}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "compose" ? "Отправить" : "Ответить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
