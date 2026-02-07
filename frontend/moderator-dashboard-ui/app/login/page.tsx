"use client"

import type React from "react"
import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { toast } from "sonner"
import { ShoppingCart, DollarSign, Truck, Brain, Shield, Zap, Mail, CheckCircle, XCircle, AlertCircle, Loader2 } from "lucide-react"

// Плавающие иконки для фона
const floatingIcons = [
  { Icon: ShoppingCart, color: "text-blue-400", delay: 0 },
  { Icon: DollarSign, color: "text-emerald-400", delay: 0.5 },
  { Icon: Truck, color: "text-orange-400", delay: 1 },
  { Icon: Brain, color: "text-purple-400", delay: 1.5 },
  { Icon: Shield, color: "text-cyan-400", delay: 2 },
  { Icon: Zap, color: "text-yellow-400", delay: 2.5 },
]

// Компонент анимированной иконки для центра
const morphingIcons = [
  { Icon: ShoppingCart, gradient: "from-blue-500 to-blue-600" },
  { Icon: DollarSign, gradient: "from-emerald-500 to-emerald-600" },
  { Icon: Truck, gradient: "from-orange-500 to-orange-600" },
  { Icon: Brain, gradient: "from-purple-500 to-violet-600" },
]

function AnimatedCenterLogo() {
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % morphingIcons.length)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  const current = morphingIcons[currentIndex]

  return (
    <div className="relative h-24 w-24">
      {/* Внешние кольца */}
      {[...Array(3)].map((_, i) => (
        <motion.div
          key={i}
          className={`absolute inset-0 rounded-full border-2 border-white/20`}
          style={{ scale: 1 + i * 0.2 }}
          animate={{
            rotate: [0, 360],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 8 + i * 2,
            repeat: Number.POSITIVE_INFINITY,
            ease: "linear",
          }}
        />
      ))}

      {/* Свечение */}
      <motion.div
        className={`absolute inset-0 rounded-full bg-gradient-to-br ${current.gradient} opacity-40 blur-xl`}
        animate={{
          scale: [1, 1.4, 1],
          opacity: [0.4, 0.7, 0.4],
        }}
        transition={{
          duration: 2,
          repeat: Number.POSITIVE_INFINITY,
          ease: "easeInOut",
        }}
      />

      {/* Основной контейнер */}
      <motion.div
        className={`relative h-full w-full rounded-full bg-gradient-to-br ${current.gradient} flex items-center justify-center shadow-2xl`}
        animate={{
          rotate: [0, 360],
        }}
        transition={{
          duration: 20,
          repeat: Number.POSITIVE_INFINITY,
          ease: "linear",
        }}
      >
        {/* Блик */}
        <motion.div
          className="absolute inset-0 rounded-full bg-gradient-to-tr from-white/40 via-transparent to-transparent"
          animate={{
            rotate: [0, 360],
          }}
          transition={{
            duration: 4,
            repeat: Number.POSITIVE_INFINITY,
            ease: "linear",
          }}
        />

        {/* Иконка в центре */}
        <motion.div
          key={currentIndex}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="relative z-10"
        >
          <current.Icon className="h-12 w-12 text-white" />
        </motion.div>
      </motion.div>
    </div>
  )
}

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [mounted, setMounted] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null)
  const [yandexConfigured, setYandexConfigured] = useState<boolean | null>(null)

  useEffect(() => {
    setMounted(true)

    // Проверяем ошибки OAuth
    const error = searchParams.get("error")
    const message = searchParams.get("message")
    if (error === "yandex_oauth_failed" && message) {
      toast.error(message)
    }

    // Проверяем подключение к backend и конфигурацию Яндекса
    checkServices()
  }, [searchParams])

  async function checkServices() {
    // Проверяем backend
    try {
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
      const response = await fetch(`${backendUrl}/health`, {
        headers: { "ngrok-skip-browser-warning": "true" },
      })
      setBackendConnected(response.ok)
    } catch {
      setBackendConnected(false)
    }

    // Проверяем конфигурацию Яндекса
    try {
      const response = await fetch("/api/yandex/config")
      const data = await response.json()
      setYandexConfigured(data.yandexOAuthEnabled === true)
    } catch {
      setYandexConfigured(false)
    }
  }

  async function handleYandexLogin() {
    setIsLoading(true)
    try {
      // Перенаправляем на endpoint логина через Яндекс
      window.location.href = "/api/yandex/login"
    } catch (error) {
      console.error("Yandex login error:", error)
      toast.error("Ошибка при попытке входа через Яндекс")
      setIsLoading(false)
    }
  }

  if (!mounted) return null

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950 relative overflow-hidden flex items-center justify-center">
      {/* Фоновые элементы */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Градиентные сферы */}
        <motion.div
          className="absolute -top-40 -left-40 w-80 h-80 bg-blue-500/20 rounded-full blur-3xl"
          animate={{
            y: [0, 100, 0],
            x: [0, 50, 0],
          }}
          transition={{
            duration: 20,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        />
        <motion.div
          className="absolute top-1/4 right-0 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl"
          animate={{
            y: [0, -80, 0],
            x: [0, -60, 0],
          }}
          transition={{
            duration: 25,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        />
        <motion.div
          className="absolute bottom-0 left-1/4 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl"
          animate={{
            y: [0, 60, 0],
            x: [0, 40, 0],
          }}
          transition={{
            duration: 30,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        />
      </div>

      {/* Плавающие иконки */}
      {floatingIcons.map(({ Icon, color, delay }, idx) => (
        <motion.div
          key={idx}
          className="absolute"
          style={{
            top: `${Math.random() * 100}%`,
            left: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [0, -30, 0],
            opacity: [0.1, 0.3, 0.1],
          }}
          transition={{
            duration: 4 + Math.random() * 2,
            delay: delay,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        >
          <Icon className={`${color} h-8 w-8`} />
        </motion.div>
      ))}

      {/* Основной контент */}
      <div className="relative z-10 max-w-md w-full mx-4 px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          {/* Логотип */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5, type: "spring" }}
            className="flex justify-center mb-8"
          >
            <AnimatedCenterLogo />
          </motion.div>

          {/* Заголовок */}
          <motion.h1
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="text-4xl font-bold text-white mb-2"
          >
            B2B Платформа
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="text-slate-400 mb-8"
          >
            Система управления поставщиками и модератоацией
          </motion.p>
        </motion.div>

        {/* Статус backend */}
        {backendConnected !== null && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="mb-4"
          >
            <div
              className={`p-3 rounded-lg border ${
                backendConnected
                  ? "bg-emerald-500/10 border-emerald-500/20"
                  : "bg-red-500/10 border-red-500/20"
              }`}
            >
              <div className="flex items-center gap-2 text-sm">
                {backendConnected ? (
                  <>
                    <CheckCircle className="h-4 w-4 text-emerald-400" />
                    <span className="text-emerald-400 font-medium">Backend подключен</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-red-400" />
                    <span className="text-red-400 font-medium">Backend недоступен</span>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* Статус Яндекса */}
        {yandexConfigured !== null && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="mb-6"
          >
            <div
              className={`p-3 rounded-lg border ${
                yandexConfigured
                  ? "bg-blue-500/10 border-blue-500/20"
                  : "bg-yellow-500/10 border-yellow-500/20"
              }`}
            >
              <div className="flex items-center gap-2 text-sm">
                {yandexConfigured ? (
                  <>
                    <CheckCircle className="h-4 w-4 text-blue-400" />
                    <span className="text-blue-400 font-medium">Яндекс OAuth настроен</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-4 w-4 text-yellow-400" />
                    <span className="text-yellow-400 font-medium">Яндекс не настроен</span>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* Форма входа */}
        <Card className="bg-white/5 backdrop-blur-xl border-white/10 shadow-2xl">
          <CardContent className="p-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
            >
              <h2 className="text-xl font-semibold text-white mb-6 text-center">Войти в систему</h2>

              {/* Кнопка входа через Яндекс */}
              <Button
                onClick={handleYandexLogin}
                disabled={isLoading || !yandexConfigured}
                type="button"
                className="w-full h-12 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold shadow-lg shadow-red-500/25 transition-all duration-300"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                    Перенаправление на Яндекс...
                  </>
                ) : (
                  <>
                    <Mail className="h-5 w-5 mr-2" />
                    Войти через Яндекс.Паспорт
                  </>
                )}
              </Button>

              {/* Сообщение если Яндекс не настроен */}
              {yandexConfigured === false && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.7 }}
                  className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg"
                >
                  <p className="text-sm text-yellow-400 text-center">
                    ⚠️ Яндекс.Паспорт не настроен. Обратитесь к администратору.
                  </p>
                </motion.div>
              )}

              {/* Информация о системе */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="mt-6 p-4 rounded-xl bg-white/5 border border-white/10"
              >
                <p className="text-xs text-slate-400 text-center">
                  Безопасный вход через{" "}
                  <span className="text-slate-300 font-semibold">Яндекс.Паспорт</span>
                </p>
              </motion.div>
            </motion.div>
          </CardContent>
        </Card>

        {/* Информация внизу */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9 }}
          className="mt-6 text-center text-xs text-slate-500"
        >
          <p>B2B Platform v1.0.0</p>
          <p className="mt-1">Powered by Yandex.Passport</p>
        </motion.div>
      </div>
    </div>
  )
}
