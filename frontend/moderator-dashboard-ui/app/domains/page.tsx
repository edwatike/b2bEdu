"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Progress } from "@/components/ui/progress"
import { addToBlacklist, clearPendingDomains, enrichPendingDomain, getPendingDomains } from "@/lib/api"
import { extractRootDomain } from "@/lib/utils-domain"
import { toast } from "sonner"

const PAGE_SIZE = 50

export default function PendingDomainsPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <PendingDomainsPageInner />
    </AuthGuard>
  )
}

function PendingDomainsPageInner() {
  const router = useRouter()
  const [entries, setEntries] = useState<Array<{ domain: string; occurrences: number; last_seen_at?: string | null }>>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkRunning, setBulkRunning] = useState(false)
  const [bulkProgress, setBulkProgress] = useState({ total: 0, done: 0, current: "" })

  async function loadDomains(nextPage: number = page, searchTerm: string = search) {
    setLoading(true)
    try {
      const query = searchTerm.trim()
      const data = await getPendingDomains({
        limit: PAGE_SIZE,
        offset: nextPage * PAGE_SIZE,
        search: query ? query : undefined,
      })
      setEntries(Array.isArray(data.entries) ? data.entries : [])
      setTotal(Number(data.total || 0))
      setPage(nextPage)
    } catch (e) {
      toast.error("Ошибка загрузки доменов")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const handle = setTimeout(() => {
      setSelected(new Set())
      void loadDomains(0, search)
    }, 300)
    return () => clearTimeout(handle)
  }, [search])

  const normalizedEntries = useMemo(() => {
    const map = new Map<string, { domain: string; occurrences: number; last_seen_at?: string | null }>()
    for (const e of entries) {
      const rootRaw = extractRootDomain(e.domain)
      const root = (rootRaw || "").trim().toLowerCase()
      if (!root) continue
      const existing = map.get(root)
      if (!existing) {
        map.set(root, { domain: root, occurrences: e.occurrences || 0, last_seen_at: e.last_seen_at ?? null })
        continue
      }
      const lastSeen =
        existing.last_seen_at && e.last_seen_at
          ? (new Date(existing.last_seen_at) > new Date(e.last_seen_at) ? existing.last_seen_at : e.last_seen_at)
          : (existing.last_seen_at || e.last_seen_at || null)
      map.set(root, {
        domain: root,
        occurrences: (existing.occurrences || 0) + (e.occurrences || 0),
        last_seen_at: lastSeen,
      })
    }
    return Array.from(map.values())
  }, [entries])

  const filtered = normalizedEntries

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allSelected = filtered.length > 0 && filtered.every((e) => selected.has(e.domain))

  const toggleSelectAll = (value: boolean) => {
    if (!value) {
      const next = new Set(selected)
      for (const e of filtered) next.delete(e.domain)
      setSelected(next)
      return
    }
    const next = new Set(selected)
    for (const e of filtered) next.add(e.domain)
    setSelected(next)
  }

  const toggleSelectOne = (domain: string, value: boolean) => {
    const next = new Set(selected)
    if (!value) {
      next.delete(domain)
    } else {
      next.add(domain)
    }
    setSelected(next)
  }

  async function handleBulkEnrich() {
    const domains = Array.from(selected)
    if (domains.length === 0) return
    setBulkRunning(true)
    setBulkProgress({ total: domains.length, done: 0, current: "" })
    try {
      let done = 0
      for (const domain of domains) {
        setBulkProgress({ total: domains.length, done, current: domain })
        try {
          const result = await enrichPendingDomain(domain)
          if (result.status !== "completed") {
            toast.error(`Не удалось получить данные: ${domain}`)
          }
        } catch {
          toast.error(`Ошибка получения данных: ${domain}`)
        } finally {
          done += 1
          setBulkProgress({ total: domains.length, done, current: domain })
        }
      }
      toast.success(`Готово: ${done} доменов`)
      setSelected(new Set())
      await loadDomains(0, search)
    } finally {
      setBulkRunning(false)
    }
  }

  async function handleClearAll() {
    setLoading(true)
    try {
      const result = await clearPendingDomains()
      toast.success(`Удалено: ${result.deleted}`)
      setSelected(new Set())
      await loadDomains(0, search)
    } catch {
      toast.error("Ошибка очистки списка")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
      <Navigation />
      <main className="container mx-auto px-6 py-6 max-w-7xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold">Домены в очереди</h1>
            <p className="text-neutral-600">Доменов, которые еще не стали поставщиками и не в blacklist.</p>
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Поиск домена (по всем страницам)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-72"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => toggleSelectAll(!allSelected)}
              disabled={filtered.length === 0}
            >
              {allSelected ? "Снять все" : "Выделить все"}
            </Button>
            <Button size="sm" onClick={handleBulkEnrich} disabled={bulkRunning || selected.size === 0}>
              {bulkRunning ? "Получаем..." : "Получить данные"}
            </Button>
            <Button variant="destructive" size="sm" onClick={handleClearAll} disabled={loading || bulkRunning}>
              Очистить список
            </Button>
            <Button variant="outline" onClick={() => loadDomains(page, search)} disabled={loading}>
              Обновить
            </Button>
          </div>
        </div>

        {selected.size > 0 && (
          <div className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <div className="text-sm text-amber-900">
              Выбрано доменов: <strong>{selected.size}</strong>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelected(new Set())} disabled={bulkRunning}>
                Снять выбор
              </Button>
              <Button size="sm" onClick={handleBulkEnrich} disabled={bulkRunning}>
                {bulkRunning ? "Получаем..." : "Получить данные"}
              </Button>
            </div>
          </div>
        )}

        {bulkRunning && (
          <div className="mb-4 rounded-lg border border-neutral-200 bg-white px-4 py-3">
            <div className="flex items-center justify-between text-sm text-neutral-700">
              <span>
                Обработка: {bulkProgress.done}/{bulkProgress.total}
              </span>
              <span className="truncate max-w-[60%]">Сейчас: {bulkProgress.current}</span>
            </div>
            <div className="mt-2">
              <Progress value={bulkProgress.total ? (bulkProgress.done / bulkProgress.total) * 100 : 0} />
            </div>
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Список доменов</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-neutral-500">Загрузка...</div>
            ) : filtered.length === 0 ? (
              <div className="text-neutral-500">Нет данных</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-neutral-500 border-b">
                      <th className="py-2 w-10 text-center">#</th>
                      <th className="py-2 w-8">
                        <Checkbox checked={allSelected} onCheckedChange={(v) => toggleSelectAll(Boolean(v))} />
                      </th>
                      <th className="py-2">Домен</th>
                      <th className="py-2">Встречался</th>
                      <th className="py-2">Последний раз</th>
                      <th className="py-2">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((row, index) => (
                      <tr key={row.domain} className="border-b">
                        <td className="py-2 text-center text-neutral-500">{page * PAGE_SIZE + index + 1}</td>
                        <td className="py-2">
                          <Checkbox
                            checked={selected.has(row.domain)}
                            onCheckedChange={(v) => toggleSelectOne(row.domain, Boolean(v))}
                          />
                        </td>
                        <td className="py-2 font-medium text-neutral-900">
                          <a
                            href={`https://${row.domain}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary-700 hover:underline"
                          >
                            {row.domain}
                          </a>
                        </td>
                        <td className="py-2 text-neutral-700">{row.occurrences}</td>
                        <td className="py-2 text-neutral-700">
                          {row.last_seen_at ? new Date(row.last_seen_at).toLocaleString("ru-RU") : "—"}
                        </td>
                        <td className="py-2">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                try {
                                  await addToBlacklist({
                                    domain: row.domain,
                                    reason: "Добавлено модератором из очереди доменов",
                                    addedBy: "moderator",
                                  })
                                  toast.success("Домен добавлен в blacklist")
                                  await loadDomains(page, search)
                                } catch {
                                  toast.error("Ошибка добавления в blacklist")
                                }
                              }}
                            >
                              В blacklist
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => router.push(`/suppliers/new?domain=${encodeURIComponent(row.domain)}`)}
                            >
                              В поставщики
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="mt-4 flex items-center justify-between">
          <div className="text-sm text-neutral-600">
            Страница {page + 1} из {pageCount} • всего {total}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" disabled={page <= 0 || loading} onClick={() => loadDomains(page - 1, search)}>
              Назад
            </Button>
            <Button
              variant="outline"
              disabled={page >= pageCount - 1 || loading}
              onClick={() => loadDomains(page + 1, search)}
            >
              Вперёд
            </Button>
          </div>
        </div>
      </main>
    </div>
  )
}
