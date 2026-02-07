"use client"

import { useEffect, useMemo, useState, useCallback } from "react"
import { motion } from "framer-motion"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getParsingRuns } from "@/lib/api"
import type { ParsingRunDTO } from "@/lib/types"
import { ArrowRight, FilePlus2 } from "lucide-react"
import { useRouter } from "next/navigation"

function UserCabinetOverview() {
  const router = useRouter()
  const [runs, setRuns] = useState<ParsingRunDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  const handleCreateRequest = useCallback(async () => {
    router.push("/cabinet")
  }, [router])

  useEffect(() => {
    let isMounted = true

    const loadAllData = async () => {
      try {
        setIsLoading(true)
        setHasError(false)

        const runsResponse = await getParsingRuns({ limit: 50, offset: 0, order: "desc" })

        if (!isMounted) return

        setRuns(runsResponse.runs || [])
      } catch (error) {
        if (!isMounted) return
        setHasError(true)
      } finally {
        if (!isMounted) return
        setIsLoading(false)
      }
    }

    loadAllData()
    return () => {
      isMounted = false
    }
  }, [])

  const stats = useMemo(() => {
    const processingRuns = runs.filter((run) => run.status === "running" || run.status === "processing")
    const doneRuns = runs.filter((run) => run.status === "done" || run.status === "completed")
    return {
      processing: processingRuns.length,
      done: doneRuns.length,
    }
  }, [runs])

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
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold">Личный кабинет</h1>
            <Badge className="bg-emerald-500/20 text-emerald-200 border-emerald-500/30">MVP</Badge>
          </div>
          <p className="text-slate-300">Статус ваших заявок, живые результаты парсинга и почта поставщиков.</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-1">
          <Card className="bg-slate-900/60 border-slate-700">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-white">Текущие заявки</CardTitle>
              <FilePlus2 className="h-5 w-5 text-slate-300" />
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">В обработке</p>
                  <p className="text-2xl font-semibold text-white">{isLoading ? "—" : stats.processing}</p>
                </div>
                <div>
                  <p className="text-sm text-slate-400">Готово</p>
                  <p className="text-2xl font-semibold text-white">{isLoading ? "—" : stats.done}</p>
                </div>
              </div>
              {hasError && <p className="text-sm text-rose-200">Не удалось загрузить статистику. Попробуйте позже.</p>}
              <Button className="w-full" variant="secondary" onClick={handleCreateRequest}>
                Создать заявку
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </motion.main>
    </div>
  )
}

export default function UserCabinetOverviewWithAuth() {
  return (
    <AuthGuard allowedRoles={["user", "moderator"]}>
      <UserCabinetOverview />
    </AuthGuard>
  )
}
