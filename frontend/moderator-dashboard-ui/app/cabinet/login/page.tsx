"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { Mail } from "lucide-react"

export default function CabinetLoginPage() {
  const router = useRouter()
  const [step, setStep] = useState<"email" | "code">("email")
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [loading, setLoading] = useState(false)
  const [activeRole, setActiveRole] = useState<string | null>(null)

  const redirectPath = useMemo(() => {
    if (typeof window === "undefined") return "/cabinet"
    const urlParams = new URLSearchParams(window.location.search)
    return urlParams.get("redirect") || "/cabinet"
  }, [])

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const redirect = urlParams.get("redirect") || "/cabinet"
    router.replace(`/login?redirect=${encodeURIComponent(redirect)}`)
    return
  }, [redirectPath, router])

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" })
    } catch (error) {
      // ignore
    } finally {
      setActiveRole(null)
      setStep("email")
      setCode("")
    }
  }

  async function requestOtp() {
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail) {
      toast.error("Введите email")
      return
    }

    setLoading(true)
    try {
      const response = await fetch("/api/auth/otp/request", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: normalizedEmail }),
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        toast.error(data.error || "Не удалось отправить код")
        return
      }

      toast.success("Код отправлен на почту")
      setStep("code")
    } catch (error) {
      toast.error("Ошибка соединения")
    } finally {
      setLoading(false)
    }
  }

  async function verifyOtp() {
    const normalizedEmail = email.trim().toLowerCase()
    const normalizedCode = code.trim()

    if (!normalizedEmail) {
      toast.error("Введите email")
      return
    }

    if (!normalizedCode) {
      toast.error("Введите код")
      return
    }

    setLoading(true)
    try {
      const response = await fetch("/api/auth/otp/verify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: normalizedEmail, code: normalizedCode }),
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        toast.error(data.error || "Неверный код")
        return
      }

      toast.success("Вы вошли в личный кабинет")
      router.push(redirectPath)
    } catch (error) {
      toast.error("Ошибка соединения")
    } finally {
      setLoading(false)
    }
  }

  async function handleYandexLogin() {
    try {
      window.location.href = "/api/yandex/login"
    } catch (error) {
      toast.error("Ошибка при переходе к авторизации Яндекса")
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <Card className="bg-slate-900/60 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white">Вход в личный кабинет</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {activeRole && activeRole !== "user" && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-amber-100 text-sm">
                Сейчас вы авторизованы как <span className="font-semibold">{activeRole}</span>. Для входа в ЛК
                пользователя по email используйте OTP ниже или нажмите «Войти другим email».
              </div>
            )}
            <div className="space-y-2">
              <Label className="text-slate-200">Email</Label>
              <Input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yandex.ru"
                className="bg-slate-900 border-slate-700 text-white"
                disabled={loading || step === "code"}
              />
            </div>

            {step === "code" && (
              <div className="space-y-2">
                <Label className="text-slate-200">Код из письма</Label>
                <Input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="000000"
                  className="bg-slate-900 border-slate-700 text-white"
                  disabled={loading}
                />
                <p className="text-xs text-slate-400">Код действует 10 минут.</p>
              </div>
            )}

            {step === "email" ? (
              <div className="space-y-2">
                <Button className="w-full" variant="secondary" onClick={requestOtp} disabled={loading}>
                  {loading ? "Отправляем..." : "Получить код"}
                </Button>
                {activeRole && activeRole !== "user" && (
                  <Button className="w-full" variant="outline" onClick={handleLogout} disabled={loading}>
                    Войти другим email
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <Button className="w-full" variant="secondary" onClick={verifyOtp} disabled={loading}>
                  {loading ? "Проверяем..." : "Войти"}
                </Button>
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() => {
                    setStep("email")
                    setCode("")
                  }}
                  disabled={loading}
                >
                  Назад
                </Button>
                <Button className="w-full" variant="outline" onClick={requestOtp} disabled={loading}>
                  Отправить код снова
                </Button>
              </div>
            )}

            {/* Разделитель */}
            <div className="flex items-center gap-4 my-6">
              <div className="flex-1 h-px bg-slate-700"></div>
              <span className="text-xs text-slate-500">или</span>
              <div className="flex-1 h-px bg-slate-700"></div>
            </div>

            {/* Кнопка входа через Яндекс */}
            <Button 
              className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white" 
              onClick={handleYandexLogin}
              disabled={loading}
            >
              <Mail className="mr-2 h-4 w-4" />
              Войти через Яндекс
            </Button>

            <p className="text-xs text-slate-400">
              Для входа нужен только доступ к вашей почте. Никаких настроек IMAP/SMTP на стороне пользователя не
              требуется.
            </p>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
