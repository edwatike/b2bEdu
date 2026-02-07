"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Navigation } from "@/components/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { getCabinetSettings, updateCabinetSettings } from "@/lib/api"
import type { CabinetSettingsDTO } from "@/lib/types"

function ModeratorSettingsPage() {
  const [settings, setSettings] = useState<CabinetSettingsDTO | null>(null)
  const [openaiApiKey, setOpenaiApiKey] = useState("")
  const [groqApiKey, setGroqApiKey] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await getCabinetSettings()
        setSettings(data)
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Не удалось загрузить настройки"
        setError(msg)
      } finally {
        setIsLoading(false)
      }
    }

    void load()
  }, [])

  const handleSave = async () => {
    if (!settings) return
    setIsSaving(true)
    setError(null)
    try {
      const updated = await updateCabinetSettings({
        ...settings,
        openai_api_key: openaiApiKey || undefined,
        groq_api_key: groqApiKey || undefined,
      })
      setSettings(updated)
      setOpenaiApiKey("")
      setGroqApiKey("")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Не удалось сохранить настройки"
      setError(msg)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      <Navigation />
      <motion.main
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="container mx-auto px-6 py-10"
      >
        <div className="flex flex-col gap-2 mb-8">
          <h1 className="text-3xl font-semibold">Настройки модератора</h1>
          <p className="text-slate-300">Ключи интеграций и параметры модерации.</p>
        </div>

        {isLoading ? (
          <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">Загружаем настройки...</div>
        ) : error ? (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-6 text-rose-100">{error}</div>
        ) : settings ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="bg-slate-900/60 border-slate-700">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">OpenAI</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-slate-200">OpenAI API key</Label>
                    <Badge
                      className={
                        settings.openai_api_key_configured
                          ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
                          : "bg-slate-500/20 text-slate-200 border-slate-500/30"
                      }
                    >
                      {settings.openai_api_key_configured ? "Подключён" : "Не задан"}
                    </Badge>
                  </div>
                  <Input
                    type="password"
                    value={openaiApiKey}
                    onChange={(event) => setOpenaiApiKey(event.target.value)}
                    placeholder={settings.openai_api_key_configured ? "•••••••• (оставь пустым, чтобы не менять)" : "sk-..."}
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                </div>

                <Button variant="secondary" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Сохраняем..." : "Сохранить"}
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/60 border-slate-700">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">Groq</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-slate-200">Groq API key</Label>
                    <Badge
                      className={
                        settings.groq_api_key_configured
                          ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
                          : "bg-slate-500/20 text-slate-200 border-slate-500/30"
                      }
                    >
                      {settings.groq_api_key_configured ? "Подключён" : "Не задан"}
                    </Badge>
                  </div>
                  <Input
                    type="password"
                    value={groqApiKey}
                    onChange={(event) => setGroqApiKey(event.target.value)}
                    placeholder={settings.groq_api_key_configured ? "•••••••• (оставь пустым, чтобы не менять)" : "gsk_..."}
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                </div>

                <Button variant="secondary" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Сохраняем..." : "Сохранить"}
                </Button>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </motion.main>
    </div>
  )
}

export default function ModeratorSettingsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <ModeratorSettingsPage />
    </AuthGuard>
  )
}
