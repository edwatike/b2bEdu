"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { apiFetch, APIError } from "@/lib/api"
import { SupplierDTO } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { CheckoInfoDialog } from "@/components/checko-info-dialog"
import { Navigation } from "@/components/navigation"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { attachDomainToSupplier, updateSupplier } from "@/lib/api"

export function SupplierEditClient({ supplierId }: { supplierId: number }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [supplier, setSupplier] = useState<SupplierDTO | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({})
  const [innConflict, setInnConflict] = useState<{
    existingSupplierId: number
    existingSupplierName?: string
    existingSupplierDomains?: string[]
    existingSupplierEmails?: string[]
  } | null>(null)
  const [formData, setFormData] = useState({
    name: "",
    inn: "",
    email: "",
    domain: "",
    emailsText: "",
    domainsText: "",
    address: "",
    type: "supplier" as "supplier" | "reseller",
    // Checko fields
    ogrn: "",
    kpp: "",
    okpo: "",
    companyStatus: "",
    registrationDate: "",
    legalAddress: "",
    phone: "",
    website: "",
    vk: "",
    telegram: "",
    authorizedCapital: null as number | null,
    revenue: null as number | null,
    profit: null as number | null,
    financeYear: null as number | null,
    legalCasesCount: null as number | null,
    legalCasesSum: null as number | null,
    legalCasesAsPlaintiff: null as number | null,
    legalCasesAsDefendant: null as number | null,
    checkoData: null as string | null,
  })

  const isNewSupplier = supplierId === 0

  useEffect(() => {
    if (isNewSupplier) {
      // Для нового поставщика не загружаем данные
      setLoading(false)
      setSupplier(null)
      const prefillDomain = searchParams.get("domain")
      if (prefillDomain) {
        setFormData((prev) => {
          if (prev.domain || prev.domainsText) return prev
          return {
            ...prev,
            domain: prefillDomain,
            domainsText: prefillDomain,
          }
        })
      }
    } else {
      loadSupplier()
    }
  }, [supplierId, isNewSupplier, searchParams])

  async function loadSupplier() {
    try {
      setLoading(true)
      const data = await apiFetch<SupplierDTO>(`/moderator/suppliers/${supplierId}`)
      setSupplier(data)
      setFormData({
        name: data.name || "",
        inn: data.inn || "",
        email: data.email || "",
        domain: data.domain || "",
        emailsText: (data.emails && data.emails.length ? data.emails : data.email ? [data.email] : []).join(", "),
        domainsText: (data.domains && data.domains.length ? data.domains : data.domain ? [data.domain] : []).join(", "),
        address: data.address || "",
        type: data.type || "supplier",
        // Checko fields
        ogrn: data.ogrn || "",
        kpp: data.kpp || "",
        okpo: data.okpo || "",
        companyStatus: data.companyStatus || "",
        registrationDate: data.registrationDate || "",
        legalAddress: data.legalAddress || "",
        phone: data.phone || "",
        website: data.website || "",
        vk: data.vk || "",
        telegram: data.telegram || "",
        authorizedCapital: data.authorizedCapital ?? null,
        revenue: data.revenue ?? null,
        profit: data.profit ?? null,
        financeYear: data.financeYear ?? null,
        legalCasesCount: data.legalCasesCount ?? null,
        legalCasesSum: data.legalCasesSum ?? null,
        legalCasesAsPlaintiff: data.legalCasesAsPlaintiff ?? null,
        legalCasesAsDefendant: data.legalCasesAsDefendant ?? null,
        checkoData: data.checkoData ?? null,
      })
      setError(null)
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.message)
      } else {
        setError("Ошибка загрузки поставщика")
      }
    } finally {
      setLoading(false)
    }
  }

  function validateForm(): boolean {
    const emailsList = parseList(formData.emailsText)
    const primaryEmail = (formData.email || emailsList[0] || "").trim()
    if (!formData.name.trim()) {
      setError("Название обязательно для заполнения")
      return false
    }
    if (!formData.inn || !/^\d{10,12}$/.test(formData.inn)) {
      setError("ИНН должен содержать 10 или 12 цифр")
      return false
    }
    if (!primaryEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(primaryEmail)) {
      setError("Некорректный формат email")
      return false
    }
    return true
  }

  function parseList(raw: string): string[] {
    return raw
      .split(/[;,\\n\\s]+/)
      .map((x) => x.trim())
      .filter(Boolean)
  }

  async function handleSave() {
    // Валидация формы
    if (!validateForm()) {
      return
    }

    try {
      setSaving(true)
      setError(null)
      setInnConflict(null)

      const emails = parseList(formData.emailsText)
      const domains = parseList(formData.domainsText)
      const primaryEmail = (formData.email || emails[0] || "").trim()
      const primaryDomain = (formData.domain || domains[0] || "").trim()
      
      if (isNewSupplier) {
        // Создание нового поставщика
        const newSupplier = await apiFetch<SupplierDTO>(`/moderator/suppliers`, {
          method: "POST",
          body: JSON.stringify({
            name: formData.name,
            inn: formData.inn || null,
            email: primaryEmail || null,
            domain: primaryDomain || null,
            emails: emails.length ? emails : null,
            domains: domains.length ? domains : null,
            address: formData.address || null,
            type: formData.type,
            // Checko fields
            ogrn: formData.ogrn || null,
            kpp: formData.kpp || null,
            okpo: formData.okpo || null,
            companyStatus: formData.companyStatus || null,
            registrationDate: formData.registrationDate || null,
            legalAddress: formData.legalAddress || null,
            phone: formData.phone || null,
            website: formData.website || null,
            vk: formData.vk || null,
            telegram: formData.telegram || null,
            authorizedCapital: formData.authorizedCapital,
            revenue: formData.revenue,
            profit: formData.profit,
            financeYear: formData.financeYear,
            legalCasesCount: formData.legalCasesCount,
            legalCasesSum: formData.legalCasesSum,
            legalCasesAsPlaintiff: formData.legalCasesAsPlaintiff,
            legalCasesAsDefendant: formData.legalCasesAsDefendant,
            checkoData: formData.checkoData,
          }),
        })
        router.push(`/suppliers/${newSupplier.id}`)
      } else {
        // Обновление существующего поставщика
        await apiFetch(`/moderator/suppliers/${supplierId}`, {
          method: "PUT",
          body: JSON.stringify({
            name: formData.name,
            inn: formData.inn || null,
            email: primaryEmail || null,
            domain: primaryDomain || null,
            emails: emails.length ? emails : null,
            domains: domains.length ? domains : null,
            address: formData.address || null,
            type: formData.type,
            // Checko fields
            ogrn: formData.ogrn || null,
            kpp: formData.kpp || null,
            okpo: formData.okpo || null,
            companyStatus: formData.companyStatus || null,
            registrationDate: formData.registrationDate || null,
            legalAddress: formData.legalAddress || null,
            phone: formData.phone || null,
            website: formData.website || null,
            vk: formData.vk || null,
            telegram: formData.telegram || null,
            authorizedCapital: formData.authorizedCapital,
            revenue: formData.revenue,
            profit: formData.profit,
            financeYear: formData.financeYear,
            legalCasesCount: formData.legalCasesCount,
            legalCasesSum: formData.legalCasesSum,
            legalCasesAsPlaintiff: formData.legalCasesAsPlaintiff,
            legalCasesAsDefendant: formData.legalCasesAsDefendant,
            checkoData: formData.checkoData,
          }),
        })
        router.push(`/suppliers/${supplierId}`)
      }
    } catch (err) {
      if (err instanceof APIError) {
        // Улучшенная обработка ошибок валидации
        const detail = (err.data as any)?.detail
        if (err.status === 409 && detail?.code === "inn_conflict") {
          setInnConflict({
            existingSupplierId: Number(detail.existingSupplierId),
            existingSupplierName: detail.existingSupplierName,
            existingSupplierDomains: detail.existingSupplierDomains,
            existingSupplierEmails: detail.existingSupplierEmails,
          })
          return
        }
        if (err.status === 422) {
          // Ошибки валидации от Backend
          const errorData = err.data as any
          const validationErrors = Array.isArray(errorData?.detail) 
            ? errorData.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ')
            : errorData?.detail || err.message
          setError(`Ошибка валидации: ${validationErrors}`)
        } else {
          setError(err.message || `Ошибка сохранения (${err.status})`)
        }
      } else {
        setError("Ошибка сохранения. Попробуйте еще раз.")
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <main className="container mx-auto px-6 py-12">
          <div className="text-center text-muted-foreground">Загрузка...</div>
        </main>
      </div>
    )
  }

  if (!isNewSupplier && (error || !supplier)) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <main className="container mx-auto px-6 py-12">
          <div className="text-red-500">Ошибка: {error || "Поставщик не найден"}</div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto px-6 py-12 max-w-7xl">
        <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{isNewSupplier ? "Добавление поставщика" : "Редактирование поставщика"}</h1>
        <Button variant="outline" onClick={() => router.back()}>
          Отмена
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Основная информация</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="name">Название {!isNewSupplier || formData.name ? "" : " *"}</Label>
            <Input
              id="name"
              name="name"
              value={formData.name}
              onChange={(e) => {
                const value = e.target.value
                setFormData({ ...formData, name: value })
                // Валидация в реальном времени
                if (!value.trim()) {
                  setFieldErrors({ ...fieldErrors, name: "Название обязательно для заполнения" })
                } else {
                  setFieldErrors({ ...fieldErrors, name: null })
                }
                setError(null)
              }}
              className={fieldErrors.name ? "border-red-500" : ""}
            />
            {fieldErrors.name && (
              <p className="text-red-500 text-xs mt-1">{fieldErrors.name}</p>
            )}
          </div>

          <div>
            <div className="flex items-start gap-2">
              <div className="flex-1">
                <Label htmlFor="inn">ИНН</Label>
                <Input
                  id="inn"
                  name="inn"
                  value={formData.inn}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '') // Только цифры
                    setFormData({ ...formData, inn: value })
                    // Валидация в реальном времени
                    if (value && !/^\d{10,12}$/.test(value)) {
                      setFieldErrors({ ...fieldErrors, inn: "ИНН должен содержать 10 или 12 цифр" })
                    } else {
                      setFieldErrors({ ...fieldErrors, inn: null })
                    }
                    setError(null)
                  }}
                  className={fieldErrors.inn ? "border-red-500" : fieldErrors.inn === null && formData.inn && /^\d{10,12}$/.test(formData.inn) ? "border-green-500" : ""}
                  placeholder="10 или 12 цифр"
                />
                {fieldErrors.inn && (
                  <p className="text-red-500 text-xs mt-1">{fieldErrors.inn}</p>
                )}
                {!fieldErrors.inn && formData.inn && /^\d{10,12}$/.test(formData.inn) && (
                  <p className="text-green-600 text-xs mt-1">✓ ИНН корректен</p>
                )}
              </div>
              <div className="pt-7">
                <CheckoInfoDialog
                  inn={formData.inn}
                  onDataLoaded={(data) => {
                    setFormData({ ...formData, ...data })
                    // Очищаем ошибки при успешной загрузке
                    setFieldErrors({})
                    setError(null)
                  }}
                />
              </div>
            </div>
          </div>

          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              value={formData.email}
              onChange={(e) => {
                const value = e.target.value
                setFormData({ ...formData, email: value })
                // Валидация в реальном времени
                if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                  setFieldErrors({ ...fieldErrors, email: "Некорректный формат email" })
                } else {
                  setFieldErrors({ ...fieldErrors, email: null })
                }
                setError(null)
              }}
              className={fieldErrors.email ? "border-red-500" : fieldErrors.email === null && formData.email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email) ? "border-green-500" : ""}
            />
            {fieldErrors.email && (
              <p className="text-red-500 text-xs mt-1">{fieldErrors.email}</p>
            )}
            {!fieldErrors.email && formData.email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email) && (
              <p className="text-green-600 text-xs mt-1">✓ Email корректен</p>
            )}
          </div>

          <div>
            <Label htmlFor="emails">Emails (несколько)</Label>
            <Textarea
              id="emails"
              value={formData.emailsText}
              onChange={(e) => setFormData({ ...formData, emailsText: e.target.value })}
              placeholder="email1@example.com, email2@example.com"
            />
          </div>

          <div>
            <Label htmlFor="domain">Домен</Label>
            <Input
              id="domain"
              name="domain"
              value={formData.domain}
              onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
            />
          </div>

          <div>
            <Label htmlFor="domains">Домены (несколько)</Label>
            <Textarea
              id="domains"
              value={formData.domainsText}
              onChange={(e) => setFormData({ ...formData, domainsText: e.target.value })}
              placeholder="example.com, sub.example.com"
            />
          </div>

          <div>
            <Label htmlFor="address">Адрес</Label>
            <Input
              id="address"
              name="address"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
            />
          </div>

          <div>
            <Label htmlFor="type">Тип</Label>
            <select
              id="type"
              value={formData.type}
              onChange={(e) => setFormData({ ...formData, type: e.target.value as "supplier" | "reseller" })}
              className="w-full rounded-md border border-input bg-background px-3 py-2"
            >
              <option value="supplier">Поставщик</option>
              <option value="reseller">Реселлер</option>
            </select>
          </div>

          {error && (
            <div className="text-red-500 text-sm p-3 bg-red-50 rounded border border-red-200">
              {error}
            </div>
          )}

          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Сохранение..." : "Сохранить"}
            </Button>
            <Button variant="outline" onClick={() => router.back()}>
              Отмена
            </Button>
          </div>
        </CardContent>
      </Card>
        </div>
      </main>

      <Dialog open={!!innConflict} onOpenChange={(open) => !open && setInnConflict(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Конфликт ИНН</DialogTitle>
            <DialogDescription>
              В базе уже есть поставщик с таким ИНН.
            </DialogDescription>
          </DialogHeader>
          {innConflict && (
            <div className="space-y-2 text-sm">
              <div>Поставщик: {innConflict.existingSupplierName || `ID ${innConflict.existingSupplierId}`}</div>
              {innConflict.existingSupplierDomains?.length ? (
                <div>Домены: {innConflict.existingSupplierDomains.join(", ")}</div>
              ) : null}
              {innConflict.existingSupplierEmails?.length ? (
                <div>Email: {innConflict.existingSupplierEmails.join(", ")}</div>
              ) : null}
            </div>
          )}
          <DialogFooter className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => setInnConflict(null)}
            >
              Отмена
            </Button>
            {innConflict && (
              <Button
                variant="secondary"
                onClick={async () => {
                  try {
                    const domains = parseList(formData.domainsText)
                    const domain = (formData.domain || domains[0] || "").trim()
                    if (!domain) {
                      setError("Укажите домен для привязки")
                      return
                    }
                    await attachDomainToSupplier(innConflict.existingSupplierId, {
                      domain,
                      email: formData.email || null,
                    })
                    router.push(`/suppliers/${innConflict.existingSupplierId}`)
                  } finally {
                    setInnConflict(null)
                  }
                }}
              >
                Привязать домен
              </Button>
            )}
            {innConflict && (
              <Button
                onClick={async () => {
                  try {
                    const emails = parseList(formData.emailsText)
                    const domains = parseList(formData.domainsText)
                    await updateSupplier(innConflict.existingSupplierId, {
                      name: formData.name,
                      inn: formData.inn || null,
                      email: formData.email || emails[0] || null,
                      domain: formData.domain || domains[0] || null,
                      emails: emails.length ? emails : null,
                      domains: domains.length ? domains : null,
                      address: formData.address || null,
                      type: formData.type,
                    })
                    router.push(`/suppliers/${innConflict.existingSupplierId}`)
                  } finally {
                    setInnConflict(null)
                  }
                }}
              >
                Обновить поставщика
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
