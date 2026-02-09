"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { startParsing } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Navigation } from "@/components/navigation"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { AuthGuard } from "@/components/auth-guard"
import { toast } from "sonner"
import { Play, Search, Globe, Target, Zap, Settings } from "lucide-react"

function ManualParsingPage() {
  const router = useRouter()
  const [keyword, setKeyword] = useState("")
  const [depth, setDepth] = useState(10)
  const [source, setSource] = useState<"google" | "yandex" | "both">("google")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleStart() {
    if (!keyword.trim()) {
      toast.error("Введите ключевое слово")
      return
    }

    try {
      setLoading(true)
      setError(null)
      const result = await startParsing({
        keyword: keyword.trim(),
        depth,
        source,
      })
      const runId = result.runId || result.run_id || ""
      toast.success(`Парсинг запущен: ${result.keyword}`)
      if (runId) {
        router.push(`/parsing-runs/${runId}`)
      }
    } catch (err) {
      console.error("[Manual Parsing] Error starting parsing:", err)
      toast.error("Ошибка запуска парсинга")
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError("Ошибка запуска парсинга")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50/30">
      <Navigation />
      <motion.main 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-12 max-w-7xl"
      >
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-orange-600 to-amber-600 flex items-center justify-center">
              <Target className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-6xl font-bold text-gradient">Ручной парсинг</h1>
          </div>
          <p className="text-xl text-muted-foreground">
            Запустите парсинг для конкретного ключевого слова
          </p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
        >
          <Card className="card-hover bg-gradient-to-br from-white to-orange-50 border-orange-200 shadow-xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-2xl">
                <Zap className="h-6 w-6 text-orange-600" />
                Настройки парсинга
                {loading && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  >
                    <Play className="h-5 w-5 text-blue-500" />
                  </motion.div>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {error && (
                <motion.div 
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"
                >
                  {error}
                </motion.div>
              )}
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <Label htmlFor="keyword" className="text-sm font-medium text-gray-700 flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    Ключевое слово
                  </Label>
                  <Input
                    id="keyword"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="Например: металлопрокат"
                    disabled={loading}
                    className="mt-2 border-orange-300 focus:border-orange-500 focus:ring-orange-500"
                  />
                </div>

                <div>
                  <Label htmlFor="source" className="text-sm font-medium text-gray-700 flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    Источник поиска
                  </Label>
                  <Select
                    value={source}
                    onValueChange={(value: "google" | "yandex" | "both") => setSource(value)}
                    disabled={loading}
                  >
                    <SelectTrigger id="source" className="mt-2 border-orange-300 focus:border-orange-500">
                      <SelectValue placeholder="Выберите источник" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="google">🔍 Google</SelectItem>
                      <SelectItem value="yandex">🔎 Yandex</SelectItem>
                      <SelectItem value="both">🌐 Google + Yandex</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="depth" className="text-sm font-medium text-gray-700 flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    Глубина парсинга
                  </Label>
                  <Input
                    id="depth"
                    type="number"
                    value={depth}
                    onChange={(e) => setDepth(parseInt(e.target.value) || 1)}
                    min={1}
                    max={10}
                    disabled={loading}
                    className="mt-2 border-orange-300 focus:border-orange-500 focus:ring-orange-500"
                  />
                  <p className="text-xs text-gray-500 mt-2">
                    1 страница ≈ 10-20 URL
                  </p>
                </div>
              </div>

              <motion.div 
                whileHover={{ scale: 1.02 }} 
                whileTap={{ scale: 0.98 }}
                className="pt-4"
              >
                <Button 
                  onClick={handleStart} 
                  disabled={loading || !keyword.trim()}
                  className="w-full bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-700 hover:to-amber-700 text-white font-medium py-4 text-lg shadow-lg"
                >
                  {loading ? (
                    <>
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        className="mr-3"
                      >
                        <Play className="h-5 w-5" />
                      </motion.div>
                      Запуск...
                    </>
                  ) : (
                    <>
                      <Play className="mr-3 h-5 w-5" />
                      Запустить парсинг
                    </>
                  )}
                </Button>
              </motion.div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.main>
    </div>
  )
}

export default function ManualParsingPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <ManualParsingPage />
    </AuthGuard>
  )
}
