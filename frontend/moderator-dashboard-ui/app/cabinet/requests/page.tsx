"use client"

import { useState, useMemo } from "react"
import { motion } from "framer-motion"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { createCabinetRequest, submitCabinetRequest, updateCabinetRequest, uploadCabinetRequestPositions, uploadCabinetRequestPositionsWithEngineProof } from "@/lib/api"
import type { CabinetParsingRequestDTO } from "@/lib/types"
import { Upload, FileText, X } from "lucide-react"

const DEFAULT_SOURCE = "google"
const DEFAULT_DEPTH = 25

function cleanCabinetKeys(input: string[]): string[] {
  // OCR/paste may contain mixed Cyrillic/Latin ("шT"), so include [тt].
  const unitRe = /\b(ш[тt]\.?\-?|шту?к\.?\-?|м2|м²|кг|г|т|тонн|п\.м|пог\.\s*м|мм|см|м)\b/i
  const moneyRe = /\b\d{1,3}(?:[\s\u00A0]\d{3})+(?:[\.,]\d{2})?\b/
  const currencyRe = /\b(руб\.?|р\.?|₽|eur|usd|\$|€)\b/i
  const percentRe = /\b\d{1,3}(?:[\.,]\d+)?\s*%\b/
  const techRe = /\b(?:dnid|dn|sn|pn|sdr|od|id|ø|d=|l=|len=|length=)\b/i
  const headerLikeRe = /\b(счет\b|сч[её]т\s*№|итого\b|всего\b|к\s+оплате|ндс\b|условия\b|контакты\b)\b/i
  const alphaRe = /[A-Za-zА-Яа-я]/

  const seen = new Set<string>()
  const out: string[] = []

  for (const raw of input || []) {
    let s = (raw || "").trim().replace(/\s+/g, " ")
    if (!s) continue
    if (headerLikeRe.test(s)) continue

    const m = s.match(moneyRe)
    if (m?.index != null) s = s.slice(0, m.index).trim()
    const m2 = s.match(currencyRe)
    if (m2?.index != null) s = s.slice(0, m2.index).trim()

    s = s.replace(/^\s*№\s*\d+\s*/g, "").replace(/^\s*\d{1,4}\s*[\)\.]\s*/g, "").replace(/^\s*\d{1,4}\s+/g, "").trim()

    const parts = s.split(" ")
    let cut = parts.length
    for (let i = 0; i < parts.length; i++) {
      const tok = parts[i]
      if (i >= 2 && (unitRe.test(tok) || techRe.test(tok) || percentRe.test(tok))) {
        cut = i
        break
      }
    }
    if (cut < parts.length) s = parts.slice(0, cut).join(" ").trim()

    // guard: if still very numeric, keep only left word tokens
    const digits = (s.match(/\d/g) || []).length
    const letters = (s.match(/[A-Za-zА-Яа-я]/g) || []).length
    if (s.length > 30 && digits >= 10 && letters >= 6) {
      const toks = s.split(" ").filter((t) => alphaRe.test(t))
      if (toks.length >= 3) s = toks.slice(0, 7).join(" ").trim()
    }

    if (s.length < 2) continue
    const low = s.toLowerCase()
    if (seen.has(low)) continue
    seen.add(low)
    out.push(s)
  }

  return out
}

function RequestsPage() {
  const [activeTab, setActiveTab] = useState<"create" | "files">("create")
  const [draftRequestId, setDraftRequestId] = useState<number | null>(null)
  const [createTitle, setCreateTitle] = useState("")
  const [createKeys, setCreateKeys] = useState<string[]>([""])
  const [recognizeFile, setRecognizeFile] = useState<File | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)
  const [groqUsed, setGroqUsed] = useState(false)

  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadRequestId, setUploadRequestId] = useState<string>("")
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const normalizedKeys = useMemo(() => {
    const base = (createKeys || []).map((k) => (k || "").trim()).filter(Boolean)
    return cleanCabinetKeys(base)
  }, [createKeys])

  const ensureDraftExists = async (): Promise<number> => {
    const title = createTitle.trim()
    if (!title) {
      throw new Error("Укажите название заявки")
    }

    if (draftRequestId) return draftRequestId

    const created = await createCabinetRequest({
      title,
      keys: [],
      depth: DEFAULT_DEPTH,
      source: DEFAULT_SOURCE,
    })
    setDraftRequestId(created.id)
    setUploadRequestId(String(created.id))
    return created.id
  }

  const handleSaveDraft = async () => {
    try {
      setIsCreating(true)
      setCreateError(null)
      setCreateSuccess(null)

      const id = await ensureDraftExists()
      const updated = await updateCabinetRequest(id, { title: createTitle.trim(), keys: normalizedKeys, depth: DEFAULT_DEPTH, source: DEFAULT_SOURCE })

      let parsed: unknown = []
      try {
        parsed = updated.raw_keys_json ? JSON.parse(updated.raw_keys_json) : []
      } catch {
        parsed = []
      }
      const nextKeys = Array.isArray(parsed) ? parsed.map((x) => String(x)) : []
      const cleaned = cleanCabinetKeys(nextKeys)
      setCreateKeys(cleaned.length ? cleaned : [""])
      setCreateSuccess("Черновик сохранён")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось сохранить черновик"
      setCreateError(message)
    } finally {
      setIsCreating(false)
    }
  }

  const handleRecognize = async () => {
    try {
      setIsCreating(true)
      setCreateError(null)
      setCreateSuccess(null)
      setGroqUsed(false)

      const file = recognizeFile
      if (!file) {
        setCreateError("Выберите файл для распознавания")
        return
      }

      const id = await ensureDraftExists()
      const result = await uploadCabinetRequestPositionsWithEngineProof(id, file, "auto")
      const updated = result.data
      setGroqUsed(Boolean(result.groqUsed))

      let parsed: unknown = []
      try {
        parsed = updated.raw_keys_json ? JSON.parse(updated.raw_keys_json) : []
      } catch {
        parsed = []
      }
      const nextKeys = Array.isArray(parsed) ? parsed.map((x) => String(x)) : []
      setCreateKeys(nextKeys.length ? nextKeys : [""])
      setCreateSuccess("Позиции распознаны и добавлены в черновик")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось распознать файл"
      setCreateError(message)
    } finally {
      setIsCreating(false)
    }
  }

  const handleSubmitDraft = async () => {
    try {
      setIsCreating(true)
      setCreateError(null)
      setCreateSuccess(null)

      const id = await ensureDraftExists()
      const updated = await updateCabinetRequest(id, { title: createTitle.trim(), keys: normalizedKeys, depth: DEFAULT_DEPTH, source: DEFAULT_SOURCE })

      let parsed: unknown = []
      try {
        parsed = updated.raw_keys_json ? JSON.parse(updated.raw_keys_json) : []
      } catch {
        parsed = []
      }
      const nextKeys = Array.isArray(parsed) ? parsed.map((x) => String(x)) : []
      const cleaned = cleanCabinetKeys(nextKeys)
      setCreateKeys(cleaned.length ? cleaned : [""])
      await submitCabinetRequest(id)
      setCreateSuccess("Заявка отправлена в работу")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось отправить заявку"
      setCreateError(message)
    } finally {
      setIsCreating(false)
    }
  }

  const addKeyField = () => {
    setCreateKeys((prev) => [...(prev.length ? prev : [""]), ""])
  }

  const updateKeyAt = (index: number, value: string) => {
    setCreateKeys((prev) => prev.map((k, i) => (i === index ? value : k)))
  }

  const removeKeyAt = (index: number) => {
    setCreateKeys((prev) => {
      const next = prev.filter((_, i) => i !== index)
      return next.length ? next : [""]
    })
  }

  const addFiles = (files: FileList | null) => {
    if (!files) return
    const list = Array.from(files)
    if (list.length === 0) return

    setSelectedFiles((prev) => {
      const next = [...prev]
      for (const f of list) {
        if (!next.some((x) => x.name === f.name && x.size === f.size && x.lastModified === f.lastModified)) {
          next.push(f)
        }
      }
      return next
    })
  }

  const removeFileAt = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleFilesAction = () => {
    void (async () => {
      const requestIdNum = Number(uploadRequestId)
      if (!Number.isFinite(requestIdNum) || requestIdNum <= 0) {
        setUploadError("Укажите ID заявки")
        return
      }

      const file = selectedFiles[0]
      if (!file) {
        setUploadError("Выберите файл")
        return
      }

      try {
        setIsUploading(true)
        setUploadError(null)
        setUploadSuccess(null)
        await uploadCabinetRequestPositions(requestIdNum, file)
        setUploadSuccess("Позиции загружены в заявку")
        setSelectedFiles([])
      } catch (error) {
        const message = error instanceof Error ? error.message : "Не удалось загрузить файл"
        setUploadError(message)
      } finally {
        setIsUploading(false)
      }
    })()
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
          <h1 className="text-3xl font-semibold">Заявка</h1>
          <p className="text-slate-300">Рабочий экран: распознавание и редактирование позиций.</p>
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => (window.location.href = "/cabinet/requests/all")}>Все заявки</Button>
          {draftRequestId && (
            <Button variant="secondary" onClick={() => window.open(`/cabinet/requests/${draftRequestId}`, "_blank", "noopener,noreferrer")}>
              Поставщики/переписка
            </Button>
          )}
        </div>

        <div className="grid gap-6 lg:grid-cols-1">
          <div className="flex flex-col gap-6">
            <Card className="bg-slate-900/60 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Создать заявку</CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "create" | "files")}>
                  <TabsList className="w-full">
                    <TabsTrigger className="flex-1" value="create">
                      Поиск
                    </TabsTrigger>
                    <TabsTrigger className="flex-1" value="files">
                      Файлы
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="create" className="mt-4">
                    <div className="space-y-3">
                      <div className="space-y-1">
                        <div className="text-sm text-slate-200">Название</div>
                        <Input
                          value={createTitle}
                          onChange={(e) => setCreateTitle(e.target.value)}
                          placeholder="Например: Поставщики бетона — Москва"
                        />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="text-sm text-slate-200">Позиции</div>
                          <Button type="button" size="sm" variant="outline" onClick={addKeyField}>
                            Добавить позицию
                          </Button>
                        </div>

                        <div className="space-y-2">
                          {createKeys.map((value, idx) => (
                            <div key={idx} className="flex items-center gap-2">
                              <textarea
                                className="min-h-[44px] w-full resize-y rounded-md border border-slate-700 bg-slate-950/30 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-400"
                                value={value}
                                onChange={(e) => updateKeyAt(idx, e.target.value)}
                                placeholder={`Позиция ${idx + 1}`}
                              />
                              <Button type="button" variant="ghost" size="sm" onClick={() => removeKeyAt(idx)}>
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-1">
                        <div className="text-sm text-slate-200">Файл заявки для распознавания</div>
                        <input
                          type="file"
                          className="block w-full text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-slate-800 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700"
                          accept=".pdf,.docx,.xlsx,.csv,.txt,.png,.jpg,.jpeg"
                          onChange={(e) => setRecognizeFile(e.target.files?.[0] || null)}
                        />
                        <div className="text-xs text-slate-400">Нажмите «Распознать заявку» — поля позиций заполнятся автоматически</div>
                      </div>

                      {createError && <div className="text-sm text-rose-200">{createError}</div>}
                      {createSuccess && <div className="text-sm text-emerald-200">{createSuccess}</div>}
                      {groqUsed && <div className="text-sm text-emerald-200">Логотип GROQ</div>}

                      <div className="grid grid-cols-1 gap-2">
                        <Button className="w-full" variant="outline" onClick={() => void handleRecognize()} disabled={isCreating}>
                          Распознать заявку
                        </Button>
                        <Button className="w-full" variant="secondary" onClick={() => void handleSaveDraft()} disabled={isCreating}>
                          Сохранить черновик
                        </Button>
                        <Button className="w-full" variant="default" onClick={() => void handleSubmitDraft()} disabled={isCreating}>
                          Отправить в работу
                        </Button>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="files" className="mt-4">
                    <div className="space-y-3">
                      <div className="space-y-1">
                        <div className="text-sm text-slate-200">ID заявки</div>
                        <Input value={uploadRequestId} onChange={(e) => setUploadRequestId(e.target.value)} placeholder="Например: 123" />
                      </div>

                      <div
                        className="rounded-lg border border-dashed border-slate-600/70 bg-slate-950/30 p-4"
                        onDragOver={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                        }}
                        onDrop={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          addFiles(e.dataTransfer.files)
                        }}
                      >
                        <div className="flex items-start gap-3">
                          <Upload className="mt-0.5 h-5 w-5 text-slate-300" />
                          <div className="flex-1">
                            <div className="text-sm text-slate-200">Перетащите файлы сюда или выберите вручную</div>
                            <div className="text-xs text-slate-400">PDF, DOCX, XLSX, CSV, JPG/PNG</div>
                          </div>
                        </div>
                        <div className="mt-3">
                          <input
                            type="file"
                            multiple
                            className="block w-full text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-slate-800 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700"
                            onChange={(e) => addFiles(e.target.files)}
                          />
                        </div>
                      </div>

                      {selectedFiles.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-sm text-slate-200">Файлы</div>
                          <div className="space-y-2">
                            {selectedFiles.map((f, idx) => (
                              <div
                                key={`${f.name}-${f.size}-${f.lastModified}`}
                                className="flex items-center justify-between rounded-md border border-slate-700/60 bg-slate-900/30 px-3 py-2"
                              >
                                <div className="min-w-0">
                                  <div className="truncate text-sm text-slate-100">{f.name}</div>
                                  <div className="text-xs text-slate-400">{Math.round(f.size / 1024)} KB</div>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => removeFileAt(idx)}>
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <Button className="w-full" variant="outline" onClick={handleFilesAction}>
                        Загрузить файл с позициями
                      </Button>

                      {uploadError && <div className="text-sm text-rose-200">{uploadError}</div>}
                      {uploadSuccess && <div className="text-sm text-emerald-200">{uploadSuccess}</div>}

                      {isUploading && <div className="text-sm text-slate-300">Загрузка...</div>}
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/60 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Поддерживаемые форматы</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-slate-300">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  PDF, DOCX, XLSX, CSV
                </div>
                <p>OCR включается автоматически для сканов и изображений.</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.main>
    </div>
  )
}

export default function RequestsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <RequestsPage />
    </AuthGuard>
  )
}
