"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { apiFetch, APIError } from "@/lib/api"
import { SupplierDTO } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { CheckoInfoDialog } from "@/components/checko-info-dialog"
import { Navigation } from "@/components/navigation"

export function SupplierEditClient({ supplierId }: { supplierId: number }) {
  const router = useRouter()
  const [supplier, setSupplier] = useState<SupplierDTO | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({})
  const [formData, setFormData] = useState({
    name: "",
    inn: "",
    email: "",
    domain: "",
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
    } else {
      loadSupplier()
    }
  }, [supplierId, isNewSupplier])

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
    if (!formData.name.trim()) {
      setError("Название обязательно для заполнения")
      return false
    }
    if (formData.inn && !/^\d{10,12}$/.test(formData.inn)) {
      setError("ИНН должен содержать 10 или 12 цифр")
      return false
    }
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      setError("Некорректный формат email")
      return false
    }
    return true
  }

  async function handleSave() {
    // Валидация формы
    if (!validateForm()) {
      return
    }

    try {
      setSaving(true)
      setError(null)
      
      if (isNewSupplier) {
        // Создание нового поставщика
        const newSupplier = await apiFetch<SupplierDTO>(`/moderator/suppliers`, {
          method: "POST",
          body: JSON.stringify({
            name: formData.name,
            inn: formData.inn || null,
            email: formData.email || null,
            domain: formData.domain || null,
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
            email: formData.email || null,
            domain: formData.domain || null,
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
            <Label htmlFor="domain">Домен</Label>
            <Input
              id="domain"
              name="domain"
              value={formData.domain}
              onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
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
    </div>
  )
}
