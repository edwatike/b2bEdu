"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getSuppliers } from "@/lib/api"
import type { SupplierDTO } from "@/lib/types"
import { Mail, Building2 } from "lucide-react"

function ResultsPage() {
  const [suppliers, setSuppliers] = useState<SupplierDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    let isMounted = true

    const loadSuppliers = async () => {
      try {
        setIsLoading(true)
        setHasError(false)
        const response = await getSuppliers({ limit: 50, offset: 0 })
        if (!isMounted) return
        setSuppliers(response.suppliers || [])
      } catch (error) {
        if (!isMounted) return
        setHasError(true)
      } finally {
        if (!isMounted) return
        setIsLoading(false)
      }
    }

    loadSuppliers()
    return () => {
      isMounted = false
    }
  }, [])

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
          <h1 className="text-3xl font-semibold">Результаты</h1>
          <p className="text-slate-300">Список найденных поставщиков и статусы коммуникаций.</p>
        </div>

        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-white">Поставщики</CardTitle>
            <Button variant="secondary" size="sm">
              <Mail className="mr-2 h-4 w-4" />
              Отправить письма
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {hasError && (
              <p className="text-sm text-rose-200">Не удалось загрузить поставщиков. Попробуйте позже.</p>
            )}
            {isLoading && <p className="text-sm text-slate-300">Загрузка поставщиков...</p>}
            {!isLoading && suppliers.length === 0 && (
              <p className="text-sm text-slate-400">Пока нет найденных поставщиков.</p>
            )}
            {suppliers.map((supplier) => (
              <div
                key={supplier.inn}
                className="flex flex-col gap-3 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Building2 className="h-5 w-5 text-slate-300" />
                    <div>
                      <p className="text-lg font-semibold text-white">{supplier.name}</p>
                      <p className="text-sm text-slate-400">ИНН {supplier.inn || "—"}</p>
                    </div>
                  </div>
                  <Badge
                    className="bg-blue-500/20 text-blue-200 border-blue-500/30"
                  >
                    Новый
                  </Badge>
                </div>
                <div className="text-sm text-slate-300">{supplier.email || "email не указан"}</div>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary">
                    Открыть карточку
                  </Button>
                  <Button size="sm" variant="outline">
                    История писем
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </motion.main>
    </div>
  )
}

export default function ResultsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <ResultsPage />
    </AuthGuard>
  )
}
