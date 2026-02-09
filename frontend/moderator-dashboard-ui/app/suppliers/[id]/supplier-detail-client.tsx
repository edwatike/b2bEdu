"use client"

import { useState, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { useRouter } from "next/navigation"
import { apiFetch, APIError } from "@/lib/api"
import { SupplierDTO, SupplierKeyword } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Navigation } from "@/components/navigation"
import { SupplierCard } from "@/components/dynamic/SupplierCard"

export function SupplierDetailClient({ supplierId }: { supplierId: number }) {
  const router = useRouter()
  const [supplier, setSupplier] = useState<SupplierDTO | null>(null)
  const [keywords, setKeywords] = useState<SupplierKeyword[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Проверяем валидность supplierId перед загрузкой данных
    if (!supplierId || isNaN(supplierId) || supplierId <= 0) {
      setError("Неверный ID поставщика")
      setLoading(false)
      return
    }
    
    loadSupplier()
    loadKeywords()
  }, [supplierId])

  async function loadSupplier() {
    try {
      setLoading(true)
      const data = await apiFetch<SupplierDTO>(`/moderator/suppliers/${supplierId}`)
      setSupplier(data)
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

  async function loadKeywords() {
    // Проверяем валидность supplierId перед запросом
    if (!supplierId || isNaN(supplierId) || supplierId <= 0) {
      return
    }
    
    try {
      const data = await apiFetch<{ keywords: SupplierKeyword[] }>(
        `/moderator/suppliers/${supplierId}/keywords`
      )
      setKeywords(data.keywords)
    } catch (err) {
      console.error("Failed to load keywords", err)
      // Не устанавливаем ошибку, так как keywords - это дополнительная информация
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

  if (error || !supplier) {
    const errorMessage = error || "Поставщик не найден"
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <main className="container mx-auto px-6 py-12">
          <div className="text-red-500 p-4">
            Ошибка: {typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage)}
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto px-6 py-6 max-w-7xl">
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <Button variant="outline" onClick={() => router.push("/suppliers")}>
              Назад
            </Button>
          </div>

          {/* Используем новый компонент SupplierCard */}
          <SupplierCard 
            supplier={supplier} 
            onSupplierUpdate={(updatedSupplier) => {
              setSupplier(updatedSupplier)
            }}
          />

          {/* Секция с ключевыми словами */}
          {keywords.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Ключевые слова</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {keywords.map((kw, idx) => (
                    <Badge key={idx} variant="outline">
                      {kw.keyword}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  )
}
