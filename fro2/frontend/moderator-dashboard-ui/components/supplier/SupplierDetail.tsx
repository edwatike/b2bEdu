/**
 * SupplierDetail Component - REFACTORED VERSION
 * 
 * Полностью переработанная страница детализации поставщика
 * 
 * Архитектура:
 * - Hero Section: Название, ИНН, статус, рейтинг риска
 * - Tabs Navigation: Обзор, Юридические данные, История парсинга, Действия
 * - Финансовый блок: Интерактивные графики и метрики
 * - Actions Bar: Фиксированная панель действий
 * 
 * UX улучшения:
 * - Skeleton loaders для async операций
 * - Optimistic updates для CTA
 * - Улучшенная визуальная иерархия
 * - Responsive design (desktop-first)
 */

"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { 
  ArrowLeft, 
  Download, 
  Edit, 
  Ban, 
  Play, 
  FileText,
  Building2,
  Scale,
  History,
  Settings as SettingsIcon
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton, SkeletonCard } from "@/components/ui/skeleton"
import { toast } from "sonner"
import { SupplierHero } from "./SupplierHero"
import { SupplierFinancials } from "./SupplierFinancials"
import { apiFetch, addToBlacklist } from "@/lib/api"
import type { SupplierDTO } from "@/lib/types"

interface SupplierDetailProps {
  supplierId: number
}

export function SupplierDetail({ supplierId }: SupplierDetailProps) {
  const router = useRouter()
  const [supplier, setSupplier] = useState<SupplierDTO | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState("overview")
  
  // Optimistic update states
  const [isAddingToBlacklist, setIsAddingToBlacklist] = useState(false)

  // Загрузка данных поставщика
  useEffect(() => {
    loadSupplier()
  }, [supplierId])

  const loadSupplier = async () => {
    try {
      setLoading(true)
      const found = await apiFetch<SupplierDTO>(`/moderator/suppliers/${supplierId}`)

      let normalized = found
      if (found.checkoData) {
        try {
          const parsed = JSON.parse(found.checkoData)
          const years = parsed?._finances ? Object.keys(parsed._finances).filter(Boolean) : []
          const latestYear = years.length ? years.sort((a, b) => Number(a) - Number(b)).pop() : null
          const currentYearData = latestYear ? parsed?._finances?.[latestYear] : null

          normalized = {
            ...found,
            financeYear: found.financeYear ?? (latestYear ? Number(latestYear) : null),
            revenue: found.revenue ?? (currentYearData?.["2110"] ?? null),
            profit: found.profit ?? (currentYearData?.["2400"] ?? null),
            authorizedCapital: found.authorizedCapital ?? parsed?.УстКап?.Сумма ?? null,
          }
        } catch {
          // ignore parse errors, keep original data
        }
      }

      setSupplier(normalized)
    } catch (error) {
      toast.error("Ошибка загрузки данных поставщика")
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // Действия
  const handleAddToBlacklist = async () => {
    if (!supplier?.domain) {
      toast.error("Домен не указан")
      return
    }

    setIsAddingToBlacklist(true)
    
    try {
      await addToBlacklist({
        domain: supplier.domain,
        reason: "Добавлен модератором из карточки поставщика",
        addedBy: "moderator"
      })
      toast.success("Домен добавлен в blacklist")
      
      // Optimistic update - обновляем UI сразу
      setSupplier(prev => prev ? { ...prev, isBlacklisted: true } : null)
    } catch (error) {
      toast.error("Ошибка добавления в blacklist")
      console.error(error)
    } finally {
      setIsAddingToBlacklist(false)
    }
  }

  const handleEdit = () => {
    router.push(`/suppliers/${supplierId}/edit`)
  }

  const handleExportPDF = () => {
    toast.info("Экспорт в PDF - в разработке")
  }

  const handleRunParsing = () => {
    toast.info("Запуск парсинга - в разработке")
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
        <div className="container mx-auto px-6 py-6 max-w-7xl">
          <Skeleton className="h-10 w-32 mb-6" />
          <div className="space-y-6">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </div>
    )
  }

  if (!supplier) {
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
      {/* Header с навигацией */}
      <div className="border-b border-neutral-200 bg-white sticky top-0 z-40 shadow-sm">
        <div className="container mx-auto px-6 py-4 max-w-7xl">
          <div className="flex items-center justify-between">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Button
                variant="ghost"
                onClick={() => router.push("/suppliers")}
                className="gap-2"
              >
                <ArrowLeft className="h-4 w-4" />
                Назад к списку
              </Button>
            </motion.div>

            {/* Quick Actions */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-2"
            >
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportPDF}
                className="gap-2"
              >
                <Download className="h-4 w-4" />
                Экспорт PDF
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleEdit}
                className="gap-2"
              >
                <Edit className="h-4 w-4" />
                Редактировать
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleAddToBlacklist}
                disabled={isAddingToBlacklist}
                className="gap-2"
              >
                <Ban className="h-4 w-4" />
                {isAddingToBlacklist ? "Добавление..." : "В Blacklist"}
              </Button>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8 max-w-7xl">
        {/* Hero Section */}
        <SupplierHero supplier={supplier} />

        {/* Tabs Navigation */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-8"
        >
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-flex">
              <TabsTrigger value="overview" className="gap-2">
                <Building2 className="h-4 w-4" />
                <span className="hidden sm:inline">Обзор</span>
              </TabsTrigger>
              <TabsTrigger value="legal" className="gap-2">
                <Scale className="h-4 w-4" />
                <span className="hidden sm:inline">Юридические данные</span>
              </TabsTrigger>
              <TabsTrigger value="history" className="gap-2">
                <History className="h-4 w-4" />
                <span className="hidden sm:inline">История парсинга</span>
              </TabsTrigger>
              <TabsTrigger value="actions" className="gap-2">
                <SettingsIcon className="h-4 w-4" />
                <span className="hidden sm:inline">Действия модератора</span>
              </TabsTrigger>
            </TabsList>

            {/* Tab: Обзор */}
            <TabsContent value="overview" className="space-y-6">
              <SupplierFinancials supplier={supplier} />
              
              {/* Контактная информация */}
              <Card>
                <CardHeader>
                  <CardTitle>Контактная информация</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {supplier.email && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">Email</p>
                        <p className="font-mono text-sm font-medium">{supplier.email}</p>
                      </div>
                    )}
                    {supplier.phone && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">Телефон</p>
                        <p className="font-mono text-sm font-medium">{supplier.phone}</p>
                      </div>
                    )}
                    {supplier.website && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">Веб-сайт</p>
                        <a 
                          href={supplier.website} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-primary-600 hover:underline"
                        >
                          {supplier.website}
                        </a>
                      </div>
                    )}
                    {supplier.domain && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">Домен</p>
                        <p className="font-mono text-sm font-medium">{supplier.domain}</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Tab: Юридические данные */}
            <TabsContent value="legal" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Регистрационные данные</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {supplier.inn && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">ИНН</p>
                        <p className="font-mono text-base font-semibold">{supplier.inn}</p>
                      </div>
                    )}
                    {supplier.ogrn && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">ОГРН</p>
                        <p className="font-mono text-base font-semibold">{supplier.ogrn}</p>
                      </div>
                    )}
                    {supplier.kpp && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">КПП</p>
                        <p className="font-mono text-base font-semibold">{supplier.kpp}</p>
                      </div>
                    )}
                    {supplier.okpo && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">ОКПО</p>
                        <p className="font-mono text-base font-semibold">{supplier.okpo}</p>
                      </div>
                    )}
                    {supplier.registrationDate && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">Дата регистрации</p>
                        <p className="text-base font-medium">{supplier.registrationDate}</p>
                      </div>
                    )}
                    {supplier.companyStatus && (
                      <div>
                        <p className="text-sm text-neutral-600 mb-1">Статус компании</p>
                        <p className="text-base font-medium">{supplier.companyStatus}</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {supplier.legalAddress && (
                <Card>
                  <CardHeader>
                    <CardTitle>Юридический адрес</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-base">{supplier.legalAddress}</p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Tab: История парсинга */}
            <TabsContent value="history">
              <Card>
                <CardHeader>
                  <CardTitle>История проверок</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-neutral-600">
                    История парсинга для этого поставщика будет отображаться здесь
                  </p>
                  <Button
                    onClick={handleRunParsing}
                    className="mt-4 gap-2"
                  >
                    <Play className="h-4 w-4" />
                    Запустить новую проверку
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Tab: Действия модератора */}
            <TabsContent value="actions">
              <Card>
                <CardHeader>
                  <CardTitle>Логи и действия</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-neutral-600">
                    Логи действий модератора будут отображаться здесь
                  </p>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </motion.div>
      </div>

      {/* Fixed Actions Bar (Bottom) */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-200 shadow-lg z-30"
      >
        <div className="container mx-auto px-6 py-4 max-w-7xl">
          <div className="flex items-center justify-between">
            <div className="text-sm text-neutral-600">
              Последнее обновление: {new Date().toLocaleString('ru-RU')}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadSupplier()}
              >
                Обновить данные
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleRunParsing}
                className="gap-2"
              >
                <Play className="h-4 w-4" />
                Запустить парсинг
              </Button>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Spacer для fixed bottom bar */}
      <div className="h-20" />
    </div>
  )
}
