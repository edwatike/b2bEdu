"use client"

import { motion } from "framer-motion"
import { useEffect, useState } from "react"
import { UserNavigation } from "@/components/user-navigation"
import { AuthGuard } from "@/components/auth-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ShieldCheck, Mail } from "lucide-react"
import { changeCabinetPassword, getCabinetSettings, updateCabinetSettings } from "@/lib/api"
import type { CabinetSettingsDTO } from "@/lib/types"

function SettingsPage() {
  const [settings, setSettings] = useState<CabinetSettingsDTO | null>(null)
  const [email, setEmail] = useState("")
  const [appPassword, setAppPassword] = useState("")
  const [openaiApiKey, setOpenaiApiKey] = useState("")
  const [role, setRole] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadSettings = async () => {
      setIsLoading(true)
      setError(null)
      try {
        try {
          const resp = await fetch("/api/auth/status")
          const data = await resp.json().catch(() => ({ authenticated: false }))
          if (resp.ok && data?.authenticated) {
            setRole(typeof data?.user?.role === "string" ? data.user.role : null)
          } else {
            setRole(null)
          }
        } catch {
          setRole(null)
        }
        const data = await getCabinetSettings()
        setSettings(data)
        setEmail(data.email ?? "")
      } catch (fetchError) {
        const message = fetchError instanceof Error ? fetchError.message : "Не удалось загрузить настройки"
        setError(message)
      } finally {
        setIsLoading(false)
      }
    }

    void loadSettings()
  }, [])

  const handleSave = async () => {
    if (!settings) return
    setIsSaving(true)
    setError(null)
    try {
      const updated = await updateCabinetSettings({
        ...settings,
        email,
        app_password: appPassword || undefined,
        openai_api_key: openaiApiKey || undefined,
      })
      setSettings(updated)
      setAppPassword("")
      setOpenaiApiKey("")
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : "Не удалось сохранить настройки"
      setError(message)
    } finally {
      setIsSaving(false)
    }
  }

  const handlePasswordChange = async () => {
    const oldPassword = window.prompt("Текущий пароль")
    if (!oldPassword) return
    const newPassword = window.prompt("Новый пароль")
    if (!newPassword) return
    try {
      await changeCabinetPassword(oldPassword, newPassword)
    } catch (passwordError) {
      const message = passwordError instanceof Error ? passwordError.message : "Не удалось сменить пароль"
      setError(message)
    }
  }

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
          <h1 className="text-3xl font-semibold">Настройки</h1>
          <p className="text-slate-300">Почта для отправки запросов и настройки безопасности.</p>
        </div>

        {isLoading ? (
          <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-6 text-slate-300">
            Загружаем настройки...
          </div>
        ) : error ? (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-6 text-rose-100">
            {error}
          </div>
        ) : settings ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="bg-slate-900/60 border-slate-700">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">Почта</CardTitle>
                <Mail className="h-5 w-5 text-slate-300" />
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-slate-200">Email</Label>
                  <Input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@company.ru"
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-200">App‑password</Label>
                  <Input
                    type="password"
                    value={appPassword}
                    onChange={(event) => setAppPassword(event.target.value)}
                    placeholder="••••••••"
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                  <p className="text-xs text-slate-400">Храним в зашифрованном виде согласно 152‑ФЗ.</p>
                </div>

                {(role === "admin" || role === "moderator") && (
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
                )}
                <Button variant="secondary" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Сохраняем..." : "Сохранить"}
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/60 border-slate-700">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">Безопасность</CardTitle>
                <ShieldCheck className="h-5 w-5 text-slate-300" />
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-300">2FA</p>
                    <p className="text-xs text-slate-500">TOTP аутентификация</p>
                  </div>
                  <Badge
                    className={
                      settings.two_fa_enabled
                        ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
                        : "bg-slate-500/20 text-slate-200 border-slate-500/30"
                    }
                  >
                    {settings.two_fa_enabled ? "Включено" : "Отключено"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-300">Организация</p>
                    <p className="text-xs text-slate-500">{settings.organization_name ?? "—"}</p>
                  </div>
                  <Badge
                    className={
                      settings.organization_verified
                        ? "bg-blue-500/20 text-blue-200 border-blue-500/30"
                        : "bg-slate-500/20 text-slate-200 border-slate-500/30"
                    }
                  >
                    {settings.organization_verified ? "Верифицировано" : "Не проверено"}
                  </Badge>
                </div>
                <Button variant="outline" onClick={handlePasswordChange}>Сменить пароль</Button>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </motion.main>
    </div>
  )
}

export default function SettingsPageWithAuth() {
  return (
    <AuthGuard allowedRoles={["moderator", "user"]}>
      <SettingsPage />
    </AuthGuard>
  )
}
