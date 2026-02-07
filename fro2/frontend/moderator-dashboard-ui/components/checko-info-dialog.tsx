"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { getCheckoData, APIError } from "@/lib/api"

interface CheckoInfoDialogProps {
  inn: string
  onDataLoaded: (data: any) => void
}

export function CheckoInfoDialog({ inn, onDataLoaded }: CheckoInfoDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  async function loadCheckoData() {
    if (!inn || inn.length < 10) {
      setError("Введите корректный ИНН (10 или 12 цифр)")
      return
    }

    try {
      setLoading(true)
      setError(null)

      // Используем backend endpoint с кэшированием
      const data = await getCheckoData(inn)

      // Формируем данные в формате, ожидаемом onDataLoaded
      // Гарантируем строковые значения вместо null/undefined для всех текстовых полей
      const updates: any = {
        name: data.name || "",
        ogrn: data.ogrn || "",
        kpp: data.kpp || "",
        okpo: data.okpo || "",
        companyStatus: data.companyStatus || "",
        registrationDate: data.registrationDate || "",
        legalAddress: data.legalAddress || "",
        address: data.legalAddress || "",  // ✅ Заполняем поле "Адрес" юридическим адресом
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
        checkoData: data.checkoData || null,
      }
      
      console.log('[Checko] Loaded data:', updates)
      console.log('[Checko] Legal Address:', updates.legalAddress)
      console.log('[Checko] Address field:', updates.address)

      onDataLoaded(updates)
      setOpen(false)
    } catch (err: any) {
      let errorMessage = "Ошибка загрузки данных из Checko"
      
      if (err instanceof APIError) {
        if (err.status === 400) {
          errorMessage = err.message || "Некорректный ИНН"
        } else if (err.status === 404) {
          errorMessage = "Компания с таким ИНН не найдена в Checko"
        } else if (err.status === 403) {
          errorMessage = "API ключ Checko недействителен или истек"
        } else if (err.status === 500) {
          errorMessage = err.message || "Ошибка сервера при загрузке данных из Checko"
        } else {
          errorMessage = err.message || `Ошибка загрузки данных: ${err.status}`
        }
      } else if (err?.message) {
        errorMessage = err.message
      }
      
      setError(errorMessage)
      console.error("Checko API error:", err)
    } finally {
      setLoading(false)
    }
  }

  // Сбрасываем ошибку при открытии диалога
  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen)
    if (newOpen) {
      setError(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">
          Заполнить Данные
        </Button>
      </DialogTrigger>
      <DialogContent className="resizable-dialog">
        <DialogHeader>
          <DialogTitle>Загрузка данных из Checko</DialogTitle>
          <DialogDescription>
            Загрузка данных о компании по ИНН: {inn || "не указан"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {error && (
            <div className="text-red-500 text-sm p-2 bg-red-50 rounded border border-red-200">
              {error}
            </div>
          )}
          {!inn || inn.length < 10 ? (
            <div className="text-yellow-600 text-sm p-2 bg-yellow-50 rounded border border-yellow-200">
              ⚠️ Введите корректный ИНН (10 или 12 цифр) в поле выше для загрузки данных
            </div>
          ) : (
            <div className="text-green-600 text-sm p-2 bg-green-50 rounded border border-green-200">
              ✓ ИНН введен корректно. Нажмите "Загрузить данные" для получения информации из Checko.
            </div>
          )}
          
          <Button
            onClick={loadCheckoData}
            disabled={loading || !inn || inn.length < 10}
            className="w-full"
          >
            {loading ? "Загрузка..." : "Загрузить данные"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
