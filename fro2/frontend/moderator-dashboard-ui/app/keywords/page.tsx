"use client"

import { Suspense, useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { getKeywords, createKeyword, deleteKeyword, getDomainsQueue, getSuppliers, getBlacklist } from "@/lib/api"
import { extractRootDomain } from "@/lib/utils-domain"
import { getCachedSuppliers, setCachedSuppliers, setCachedBlacklist } from "@/lib/cache"
import { toast } from "sonner"
import {
  Plus,
  Trash2,
  RefreshCw,
  Key,
  Globe,
  Building2,
  AlertTriangle,
  Link2,
  ChevronRight,
  ChevronDown,
  Search,
} from "lucide-react"
import type { KeywordDTO, DomainQueueEntryDTO } from "@/lib/types"

interface DomainGroup {
  rootDomain: string
  urls: DomainQueueEntryDTO[]
  supplierType?: "supplier" | "reseller" | null
  isBlacklisted: boolean
}

interface KeywordWithDomains extends KeywordDTO {
  domains: DomainGroup[]
  totalUrls: number
}

function KeywordsContent() {
  const [keywords, setKeywords] = useState<KeywordWithDomains[]>([])
  const [loading, setLoading] = useState(true)
  const [newKeyword, setNewKeyword] = useState("")
  const [addingKeyword, setAddingKeyword] = useState(false)
  const [expandedKeywords, setExpandedKeywords] = useState<Set<number>>(new Set())
  const [loadedUrls, setLoadedUrls] = useState<Map<number, DomainGroup[]>>(new Map())
  const [selectedKeywords, setSelectedKeywords] = useState<Set<number>>(new Set())
  const [searchFilter, setSearchFilter] = useState("")

  useEffect(() => {
    loadKeywords()
    const interval = setInterval(() => {
      loadKeywords()
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  async function loadKeywords() {
    setLoading(true)
    try {
      let suppliersData: { suppliers: any[]; total: number; limit: number; offset: number }
      let blacklistData: { entries: any[]; total: number; limit: number; offset: number }

      const cachedSuppliers = getCachedSuppliers()

      if (cachedSuppliers) {
        suppliersData = {
          suppliers: cachedSuppliers,
          total: cachedSuppliers.length,
          limit: 1000,
          offset: 0,
        }
      } else {
        const suppliersResult = await getSuppliers({ limit: 1000 })
        suppliersData = suppliersResult
        setCachedSuppliers(suppliersData.suppliers)
      }

      const blacklistResult = await getBlacklist({ limit: 1000 })
      blacklistData = blacklistResult
      setCachedBlacklist(blacklistData.entries)

      const keywordsData = await getKeywords()

      const suppliersMap = new Map<string, "supplier" | "reseller">()
      suppliersData.suppliers.forEach((supplier) => {
        if (supplier.domain) {
          const rootDomain = extractRootDomain(supplier.domain).toLowerCase()
          suppliersMap.set(rootDomain, supplier.type)
        }
      })

      const keywordsWithDomains = keywordsData.keywords.map((keyword) => ({
        ...keyword,
        domains: [],
        totalUrls: 0,
      }))

      setKeywords(keywordsWithDomains)
      setLoadedUrls(new Map())

      const expandedKeywordsList = Array.from(expandedKeywords)
      for (const keywordId of expandedKeywordsList) {
        const keyword = keywordsWithDomains.find((k) => k.id === keywordId)
        if (keyword) {
          loadUrlsForKeyword(keywordId, keyword.keyword, true).catch((err) => {
            console.error(`Error reloading URLs for keyword ${keyword.keyword}:`, err)
          })
        }
      }
    } catch (error) {
      toast.error("Ошибка загрузки ключевых слов")
      console.error("Error loading keywords:", error)
    } finally {
      setLoading(false)
    }
  }

  const filteredKeywords = keywords.filter(
    (k) => searchFilter === "" || k.keyword.toLowerCase().includes(searchFilter.toLowerCase()),
  )

  async function handleAdd() {
    if (!newKeyword.trim()) {
      toast.error("Введите ключевое слово")
      return
    }

    setAddingKeyword(true)
    try {
      await createKeyword(newKeyword.trim())
      toast.success(`Ключевое слово "${newKeyword}" добавлено`)
      setNewKeyword("")
      loadKeywords()
    } catch (error) {
      toast.error("Ошибка добавления ключевого слова")
      console.error("Error adding keyword:", error)
    } finally {
      setAddingKeyword(false)
    }
  }

  async function handleDelete(id: number, keyword: string) {
    if (!confirm(`Удалить ключевое слово "${keyword}"?`)) return

    try {
      await deleteKeyword(id)
      toast.success(`Ключевое слово "${keyword}" удалено`)
      loadKeywords()
    } catch (error) {
      toast.error("Ошибка удаления ключевого слова")
      console.error("Error deleting keyword:", error)
    }
  }

  async function loadUrlsForKeyword(keywordId: number, keywordText: string, forceReload = false) {
    if (!forceReload && loadedUrls.has(keywordId)) {
      return
    }

    try {
      const domainsData = await getDomainsQueue({ keyword: keywordText, limit: 1000 })
      const cachedSuppliers = getCachedSuppliers()

      const suppliersMap = new Map<string, "supplier" | "reseller">()
      if (cachedSuppliers) {
        cachedSuppliers.forEach((supplier) => {
          if (supplier.domain) {
            const rootDomain = extractRootDomain(supplier.domain).toLowerCase()
            suppliersMap.set(rootDomain, supplier.type)
          }
        })
      }

      const blacklistResult = await getBlacklist({ limit: 1000 })
      setCachedBlacklist(blacklistResult.entries)

      const blacklistedDomains = new Set<string>()
      blacklistResult.entries.forEach((e) => {
        blacklistedDomains.add(extractRootDomain(e.domain).toLowerCase())
      })

      const filteredEntries = domainsData.entries.filter((urlEntry) => {
        const rootDomain = extractRootDomain(urlEntry.domain).toLowerCase()
        return !blacklistedDomains.has(rootDomain)
      })

      const domainGroupsMap = new Map<string, DomainGroup>()
      filteredEntries.forEach((urlEntry) => {
        const rootDomain = extractRootDomain(urlEntry.domain).toLowerCase()
        if (!domainGroupsMap.has(rootDomain)) {
          domainGroupsMap.set(rootDomain, {
            rootDomain,
            urls: [],
            supplierType: suppliersMap.get(rootDomain) || null,
            isBlacklisted: false,
          })
        }
        domainGroupsMap.get(rootDomain)!.urls.push(urlEntry)
      })

      const domains = Array.from(domainGroupsMap.values())
      const totalUrls = domains.reduce((sum, d) => sum + d.urls.length, 0)

      setLoadedUrls((prev) => new Map(prev).set(keywordId, domains))

      setKeywords((prev) =>
        prev.map((k) =>
          k.id === keywordId
            ? {
                ...k,
                domains,
                totalUrls,
              }
            : k,
        ),
      )
    } catch (error) {
      console.error(`Error loading URLs for keyword ${keywordText}:`, error)
      toast.error(`Ошибка загрузки URL для ключа "${keywordText}"`)
    }
  }

  function toggleKeyword(keywordId: number, keywordText: string) {
    const isExpanded = expandedKeywords.has(keywordId)
    if (isExpanded) {
      setExpandedKeywords((prev) => {
        const newSet = new Set(prev)
        newSet.delete(keywordId)
        return newSet
      })
    } else {
      setExpandedKeywords((prev) => new Set(prev).add(keywordId))
      loadUrlsForKeyword(keywordId, keywordText)
    }
  }

  function toggleSelectKeyword(keywordId: number) {
    const newSelected = new Set(selectedKeywords)
    if (newSelected.has(keywordId)) {
      newSelected.delete(keywordId)
    } else {
      newSelected.add(keywordId)
    }
    setSelectedKeywords(newSelected)
  }

  function toggleSelectAll() {
    if (selectedKeywords.size === filteredKeywords.length) {
      setSelectedKeywords(new Set())
    } else {
      const allKeywordIds = filteredKeywords.map((k) => k.id)
      setSelectedKeywords(new Set(allKeywordIds))
    }
  }

  async function handleBulkDelete() {
    if (selectedKeywords.size === 0) return
    if (!confirm(`Удалить ${selectedKeywords.size} ключевых слов?`)) return

    try {
      const keywordIds = Array.from(selectedKeywords)
      for (const keywordId of keywordIds) {
        await deleteKeyword(keywordId)
      }
      toast.success(`Удалено ${keywordIds.length} ключевых слов`)
      setSelectedKeywords(new Set())
      loadKeywords()
    } catch (error) {
      toast.error("Ошибка массового удаления")
      console.error("Error bulk deleting keywords:", error)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-cyan-50/20">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-4 py-6 max-w-6xl"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
              <Key className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">
                Ключевые слова
              </h1>
              <p className="text-sm text-muted-foreground">{keywords.length} ключей</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadKeywords}
            disabled={loading}
            className="border-blue-200 text-blue-700 hover:bg-blue-50 bg-transparent"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Обновить
          </Button>
        </div>

        <div className="flex gap-3 mb-4">
          <div className="flex-1 flex gap-2">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="search"
                name="search"
                placeholder="Поиск..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="pl-9 h-9 bg-white border-slate-200"
              />
            </div>
            <Input
              id="new-keyword"
              name="new-keyword"
              autoComplete="off"
              aria-label="Новое ключевое слово"
              placeholder="Новое ключевое слово..."
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              className="flex-1 h-9 bg-white border-slate-200"
            />
            <Button
              onClick={handleAdd}
              disabled={addingKeyword}
              size="sm"
              className="h-9 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white"
            >
              <Plus className="mr-1 h-4 w-4" />
              Добавить
            </Button>
          </div>
        </div>

        <AnimatePresence>
          {selectedKeywords.size > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4"
            >
              <div className="flex items-center justify-between bg-red-50 p-3 rounded-lg border border-red-200">
                <span className="text-sm text-red-700 font-medium">Выбрано: {selectedKeywords.size}</span>
                <Button variant="destructive" size="sm" onClick={handleBulkDelete} className="h-8">
                  <Trash2 className="mr-1 h-3 w-3" />
                  Удалить
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {loading && keywords.length === 0 ? (
          <Card className="bg-white/80 backdrop-blur-sm border-blue-100">
            <CardContent className="py-8 text-center">
              <RefreshCw className="h-6 w-6 text-blue-400 mx-auto mb-3 animate-spin" />
              <p className="text-muted-foreground text-sm">Загрузка...</p>
            </CardContent>
          </Card>
        ) : keywords.length === 0 ? (
          <Card className="bg-white/80 backdrop-blur-sm border-blue-100">
            <CardContent className="py-8 text-center">
              <Key className="h-8 w-8 text-blue-300 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Добавьте первое ключевое слово</p>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-white/90 backdrop-blur-sm border-slate-200 shadow-sm overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-2 bg-slate-50 border-b border-slate-200 text-xs font-medium text-muted-foreground">
              <Checkbox
                checked={selectedKeywords.size === filteredKeywords.length && filteredKeywords.length > 0}
                onCheckedChange={toggleSelectAll}
                className="h-4 w-4"
              />
              <span className="flex-1">Ключевое слово</span>
              <span className="w-20 text-center">URL</span>
              <span className="w-20 text-center">Домены</span>
              <span className="w-24 text-center">Дата</span>
              <span className="w-8"></span>
            </div>

            <div className="divide-y divide-slate-100">
              {filteredKeywords.map((keyword, index) => {
                const isExpanded = expandedKeywords.has(keyword.id)
                const isSelected = selectedKeywords.has(keyword.id)

                return (
                  <motion.div
                    key={keyword.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: index * 0.02 }}
                  >
                    <div
                      className={`flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors cursor-pointer ${
                        isSelected ? "bg-blue-50/50" : ""
                      }`}
                      onClick={() => toggleKeyword(keyword.id, keyword.keyword)}
                    >
                      <div onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => toggleSelectKeyword(keyword.id)}
                          className="h-4 w-4"
                        />
                      </div>
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-blue-500 flex-shrink-0" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-slate-400 flex-shrink-0" />
                        )}
                        <span className="font-medium text-sm truncate">{keyword.keyword}</span>
                      </div>
                      <Badge
                        variant="outline"
                        className="w-20 justify-center text-xs bg-blue-50 border-blue-200 text-blue-700"
                      >
                        <Link2 className="h-3 w-3 mr-1" />
                        {keyword.totalUrls}
                      </Badge>
                      <Badge
                        variant="outline"
                        className="w-20 justify-center text-xs bg-cyan-50 border-cyan-200 text-cyan-700"
                      >
                        <Globe className="h-3 w-3 mr-1" />
                        {keyword.domains.length}
                      </Badge>
                      <span className="w-24 text-xs text-muted-foreground text-center">
                        {new Date(keyword.createdAt).toLocaleDateString("ru-RU")}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDelete(keyword.id, keyword.keyword)
                        }}
                        className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="bg-slate-50/50 border-t border-slate-100"
                        >
                          {keyword.domains.length === 0 ? (
                            <div className="px-12 py-4 text-sm text-muted-foreground">Домены не найдены</div>
                          ) : (
                            <div className="px-4 py-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                              {keyword.domains.slice(0, 20).map((domain) => (
                                <div
                                  key={domain.rootDomain}
                                  className="flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 text-xs"
                                >
                                  {domain.supplierType === "supplier" && (
                                    <Building2 className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                                  )}
                                  {domain.supplierType === "reseller" && (
                                    <AlertTriangle className="h-3 w-3 text-amber-500 flex-shrink-0" />
                                  )}
                                  {!domain.supplierType && <Globe className="h-3 w-3 text-slate-400 flex-shrink-0" />}
                                  <a
                                    href={`https://${domain.rootDomain}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="truncate text-blue-600 hover:underline flex-1"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    {domain.rootDomain}
                                  </a>
                                  <Badge variant="outline" className="h-5 text-[10px] bg-slate-50">
                                    {domain.urls.length}
                                  </Badge>
                                </div>
                              ))}
                              {keyword.domains.length > 20 && (
                                <div className="flex items-center justify-center p-2 text-xs text-muted-foreground">
                                  +{keyword.domains.length - 20} ещё
                                </div>
                              )}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                )
              })}
            </div>
          </Card>
        )}
      </motion.main>
    </div>
  )
}

export default function KeywordsPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <Suspense fallback={null}>
        <KeywordsContent />
      </Suspense>
    </AuthGuard>
  )
}
