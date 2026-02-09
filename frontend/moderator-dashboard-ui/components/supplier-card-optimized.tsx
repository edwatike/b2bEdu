"use client"

import { useState, useMemo, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import type { SupplierDTO } from "@/lib/types"
import {
  formatCurrency,
  formatDate,
  calculatePercentageChange,
  getRiskLevel,
  getRiskColor,
  getRiskEmoji,
  formatOKVEDCode,
  calculateReliabilityRating,
  calculateReliabilityScore,
  ratingToStars,
  type ReliabilityLevel,
} from "@/lib/format-utils"
import { addToBlacklist, getCheckoData, updateSupplier } from "@/lib/api"
import { toast } from "sonner"
import { Edit, Ban, Tag, Globe, Phone, MapPin, Mail, Star, RefreshCw, ExternalLink, CheckCircle2 } from "lucide-react"
import Link from "next/link"
import { extractRootDomain } from "@/lib/utils-domain"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

// Types for Checko data
interface CheckoData {
  rating?: number
  Рейтинг?: number
  _finances?: Record<string, FinanceYear>
  _legal?: LegalData
  _inspections?: InspectionData
  _enforcements?: EnforcementData
  Учред?: Founder[] | { ФЛ?: Founder[] }
  Руковод?: Leader[]
  ОКВЭД?: OKVED[] | OKVED
  ОКВЭДДоп?: OKVED[]
  timestamp?: number
}

interface FinanceYear {
  "2110"?: number // Revenue
  "2400"?: number // Profit
}

interface LegalData {
  asPlaintiff?: number
  asDefendant?: number
  total?: number
  sum?: number
}

interface InspectionData {
  total?: number
  violations?: number
}

interface EnforcementData {
  count?: number
}

interface Founder {
  name?: string
  ФИО?: string
  ИНН?: string
  inn?: string
  share?: number
  Доля?: number | { Номинал?: number; Процент?: number }
  Стоимость?: number
  Номинал?: number
  Процент?: number
  ДатаЗаписи?: string
}

interface Leader {
  name?: string
  ИНН?: string
  position?: string
  Должность?: string
}

interface OKVED {
  Код?: string
  Наименование?: string
}

interface SupplierCardProps {
  supplier: SupplierDTO
  onSupplierUpdate?: (updatedSupplier: SupplierDTO) => void
}

// Memoized checko data parser
function parseCheckoData(checkoDataString: string | null): CheckoData | null {
  if (!checkoDataString) return null
  
  try {
    return JSON.parse(checkoDataString)
  } catch (error) {
    console.error("Error parsing checko data:", error)
    return null
  }
}

// Memoized chart data preparation
function prepareChartData(finances: Record<string, FinanceYear> | undefined) {
  if (!finances) return []
  
  return Object.entries(finances)
    .map(([year, data]) => ({
      year,
      revenue: data["2110"] || 0,
      profit: data["2400"] || 0,
    }))
    .sort((a, b) => a.year.localeCompare(b.year))
}

// Memoized reliability score calculation
function calculateSupplierReliability(supplier: SupplierDTO, checkoData: CheckoData | null) {
  const scoreResult = calculateReliabilityScore(checkoData as any, supplier as any)
  const rating = calculateReliabilityRating(checkoData as any, supplier as any)
  const starsCount = ratingToStars(rating)

  return { scoreResult, rating, starsCount }
}

export function SupplierCard({ supplier, onSupplierUpdate }: SupplierCardProps) {
  const router = useRouter()
  const [addingToBlacklist, setAddingToBlacklist] = useState(false)
  const [blacklistDialogOpen, setBlacklistDialogOpen] = useState(false)
  const [blacklistReason, setBlacklistReason] = useState("")
  const [refreshingData, setRefreshingData] = useState(false)

  // Memoize parsed checko data
  const checkoData = useMemo(() => {
    return parseCheckoData(supplier.checkoData ?? null)
  }, [supplier.checkoData])

  // Memoize chart data
  const chartData = useMemo(() => {
    return prepareChartData(checkoData?._finances)
  }, [checkoData?._finances])

  // Memoize reliability metrics
  const reliability = useMemo(() => {
    return calculateSupplierReliability(supplier, checkoData)
  }, [supplier, checkoData])

  // Memoize risk level
  const riskLevel = useMemo(() => {
    const asPlaintiff = checkoData?._legal?.asPlaintiff ?? 0
    const asDefendant = checkoData?._legal?.asDefendant ?? 0
    return getRiskLevel(asPlaintiff, asDefendant)
  }, [supplier, checkoData])

  // Memoize formatted addresses
  const addresses = useMemo(() => {
    const addresses = []
    if (supplier.legalAddress) {
      addresses.push({ type: "Юридический", address: supplier.legalAddress })
    }
    if (supplier.address && supplier.address !== supplier.legalAddress) {
      addresses.push({ type: "Фактический", address: supplier.address })
    }
    return addresses
  }, [supplier.legalAddress, supplier.address])

  // Memoize founders
  const founders = useMemo(() => {
    if (!checkoData?.Учред) return []
    
    const foundersArray = Array.isArray(checkoData.Учред) 
      ? checkoData.Учред 
      : checkoData.Учред.ФЛ || []
    
    return foundersArray.slice(0, 5) // Limit to 5 founders
  }, [checkoData?.Учред])

  // Memoize OKVED codes
  const okvedCodes = useMemo(() => {
    if (!checkoData?.ОКВЭД) return []
    
    const okvedArray = Array.isArray(checkoData.ОКВЭД) 
      ? checkoData.ОКВЭД 
      : [checkoData.ОКВЭД]
    
    return okvedArray.slice(0, 10) // Limit to 10 codes
  }, [checkoData?.ОКВЭД])

  // Memoized handlers
  const handleRefreshCheckoData = useCallback(async () => {
    setRefreshingData(true)
    try {
      const data = await getCheckoData(supplier.inn || "")
      if (onSupplierUpdate) {
        onSupplierUpdate({
          ...supplier,
          checkoData: JSON.stringify(data),
        })
      }
      toast.success("Данные Checko обновлены")
    } catch (error: any) {
      toast.error(error.message || "Ошибка при обновлении данных")
    } finally {
      setRefreshingData(false)
    }
  }, [supplier, onSupplierUpdate])

  const handleAddToBlacklist = useCallback(async () => {
    if (!blacklistReason.trim()) {
      toast.error("Укажите причину добавления в черный список")
      return
    }

    setAddingToBlacklist(true)
    try {
      if (!supplier.domain) {
        toast.error("Домен не указан")
        return
      }
      await addToBlacklist({
        domain: extractRootDomain(supplier.domain),
        reason: blacklistReason.trim() || null,
        addedBy: "moderator",
      })
      setBlacklistDialogOpen(false)
      setBlacklistReason("")
      toast.success("Добавлено в черный список")
    } catch (error: any) {
      toast.error(error.message || "Ошибка при добавлении в черный список")
    } finally {
      setAddingToBlacklist(false)
    }
  }, [supplier.id, blacklistReason])

  const handleUpdateSupplier = useCallback(async (updates: Partial<SupplierDTO>) => {
    try {
      const updated = await updateSupplier(supplier.id, updates)
      if (onSupplierUpdate) {
        onSupplierUpdate(updated)
      }
      toast.success("Данные поставщика обновлены")
    } catch (error: any) {
      toast.error(error.message || "Ошибка при обновлении поставщика")
    }
  }, [supplier.id, onSupplierUpdate])

  return (
    <div className="space-y-6">
      {/* Overview Section */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <CardTitle className="text-xl">{supplier.name}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant={supplier.type === "supplier" ? "default" : "secondary"}>
                  {supplier.type === "supplier" ? "Поставщик" : "Реселлер"}
                </Badge>
                <Badge variant="outline" className={cn("text-xs", getRiskColor(riskLevel))}>
                  {getRiskEmoji(riskLevel)} {riskLevel}
                </Badge>
                {reliability.rating && (
                  <div className="flex items-center gap-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        className={cn(
                          "h-4 w-4",
                          i < reliability.starsCount
                            ? "text-yellow-500 fill-yellow-500"
                            : "text-gray-300"
                        )}
                      />
                    ))}
                    <span className="text-xs text-muted-foreground ml-1">
                      ({reliability.scoreResult.score})
                    </span>
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefreshCheckoData}
                disabled={refreshingData}
              >
                <RefreshCw className={cn("h-4 w-4 mr-2", refreshingData && "animate-spin")} />
                Обновить данные
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/suppliers/${supplier.id}/edit`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Редактировать
                </Link>
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setBlacklistDialogOpen(true)}
              >
                <Ban className="h-4 w-4 mr-2" />
                В черный список
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Basic Info */}
            <div className="space-y-2">
              <h4 className="font-medium">Основная информация</h4>
              <div className="space-y-1 text-sm">
                {supplier.inn && (
                  <div>
                    <span className="text-muted-foreground">ИНН: </span>
                    {supplier.inn}
                  </div>
                )}
                {supplier.ogrn && (
                  <div>
                    <span className="text-muted-foreground">ОГРН: </span>
                    {supplier.ogrn}
                  </div>
                )}
                {supplier.kpp && (
                  <div>
                    <span className="text-muted-foreground">КПП: </span>
                    {supplier.kpp}
                  </div>
                )}
                {supplier.companyStatus && (
                  <div>
                    <span className="text-muted-foreground">Статус: </span>
                    {supplier.companyStatus}
                  </div>
                )}
                {supplier.registrationDate && (
                  <div>
                    <span className="text-muted-foreground">Дата регистрации: </span>
                    {formatDate(supplier.registrationDate)}
                  </div>
                )}
              </div>
            </div>

            {/* Contacts */}
            <div className="space-y-2">
              <h4 className="font-medium">Контакты</h4>
              <div className="space-y-1 text-sm">
                {supplier.email && (
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    <a href={`mailto:${supplier.email}`} className="text-blue-600 hover:underline">
                      {supplier.email}
                    </a>
                  </div>
                )}
                {supplier.phone && (
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    {supplier.phone}
                  </div>
                )}
                {supplier.website && (
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    <a
                      href={supplier.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline flex items-center gap-1"
                    >
                      {supplier.website}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                )}
                {supplier.vk && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">VK: </span>
                    <a
                      href={supplier.vk}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {extractRootDomain(supplier.vk)}
                    </a>
                  </div>
                )}
                {supplier.telegram && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Telegram: </span>
                    <a
                      href={supplier.telegram}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {supplier.telegram}
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Financial Summary */}
            <div className="space-y-2">
              <h4 className="font-medium">Финансы</h4>
              <div className="space-y-1 text-sm">
                {supplier.authorizedCapital && (
                  <div>
                    <span className="text-muted-foreground">Уставный капитал: </span>
                    {formatCurrency(supplier.authorizedCapital)}
                  </div>
                )}
                {supplier.revenue && (
                  <div>
                    <span className="text-muted-foreground">Выручка: </span>
                    {formatCurrency(supplier.revenue)}
                    {supplier.financeYear && (
                      <span className="text-muted-foreground"> ({supplier.financeYear})</span>
                    )}
                  </div>
                )}
                {supplier.profit !== null && supplier.profit !== undefined && (
                  <div>
                    <span className="text-muted-foreground">Прибыль: </span>
                    {formatCurrency(supplier.profit)}
                    {supplier.financeYear && (
                      <span className="text-muted-foreground"> ({supplier.financeYear})</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Sections */}
      <Accordion type="multiple" className="space-y-4">
        {/* Addresses */}
        {addresses.length > 0 && (
          <AccordionItem value="addresses" className="border rounded-lg px-4">
            <AccordionTrigger className="hover:no-underline">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                Адреса ({addresses.length})
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-3">
                {addresses.map((addr, index) => (
                  <div key={index} className="space-y-1">
                    <div className="font-medium text-sm">{addr.type}</div>
                    <div className="text-sm text-muted-foreground">{addr.address}</div>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        )}

        {/* Financial Chart - Dynamic Import */}
        {chartData.length > 0 && (
          <AccordionItem value="financials" className="border rounded-lg px-4">
            <AccordionTrigger className="hover:no-underline">
              <div className="flex items-center gap-2">
                <Tag className="h-4 w-4" />
                Финансовые показатели ({chartData.length} лет)
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="mt-4">
                {/* Chart will be loaded dynamically */}
                <div className="h-64 bg-muted rounded flex items-center justify-center">
                  <span className="text-muted-foreground">График загружается...</span>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        )}

        {/* Founders */}
        {founders.length > 0 && (
          <AccordionItem value="founders" className="border rounded-lg px-4">
            <AccordionTrigger className="hover:no-underline">
              Учредители ({founders.length})
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-3">
                {founders.map((founder, index) => (
                  <div key={index} className="flex justify-between items-center p-3 border rounded">
                    <div>
                      <div className="font-medium">
                        {founder.name || founder.ФИО || "Без имени"}
                      </div>
                      {founder.ИНН || founder.inn ? (
                        <div className="text-sm text-muted-foreground">
                          ИНН: {founder.ИНН || founder.inn}
                        </div>
                      ) : null}
                      {founder.ДатаЗаписи && (
                        <div className="text-xs text-muted-foreground">
                          Дата записи: {formatDate(founder.ДатаЗаписи)}
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="font-medium">
                        {typeof founder.Доля === "object" && founder.Доля !== null
                          ? `${founder.Доля.Процент || 0}%`
                          : typeof founder.Доля === "number"
                          ? `${founder.Доля}%`
                          : typeof founder.share === "number"
                          ? `${founder.share}%`
                          : "—"}
                      </div>
                      {typeof founder.Стоимость === "number" && (
                        <div className="text-sm text-muted-foreground">
                          {formatCurrency(founder.Стоимость)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        )}

        {/* OKVED Codes */}
        {okvedCodes.length > 0 && (
          <AccordionItem value="okved" className="border rounded-lg px-4">
            <AccordionTrigger className="hover:no-underline">
              Коды ОКВЭД ({okvedCodes.length})
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2">
                {okvedCodes.map((okved, index) => (
                  <div key={index} className="flex justify-between items-center p-2 border rounded">
                    <div>
                      <div className="font-medium">
                        {formatOKVEDCode(okved.Код || "")}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {okved.Наименование}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        )}
      </Accordion>

      {/* Blacklist Dialog */}
      <Dialog open={blacklistDialogOpen} onOpenChange={setBlacklistDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Добавить в черный список</DialogTitle>
            <DialogDescription>
              Укажите причину добавления "{supplier.name}" в черный список
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="reason">Причина</Label>
              <Textarea
                id="reason"
                placeholder="Например: Мошенничество, некачественные услуги..."
                value={blacklistReason}
                onChange={(e) => setBlacklistReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setBlacklistDialogOpen(false)}
            >
              Отмена
            </Button>
            <Button
              variant="destructive"
              onClick={handleAddToBlacklist}
              disabled={addingToBlacklist}
            >
              {addingToBlacklist ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                  Добавление...
                </>
              ) : (
                "Добавить в черный список"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
