"use client"

import type React from "react"

import { useCallback, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { toast } from "sonner"
import { ShoppingCart, DollarSign, Truck, Brain, Shield, Zap } from "lucide-react"
import { YandexLoginCircle } from "@/components/yandex-login-circle"

// Плавающие иконки для фона
const floatingIcons = [
  { Icon: ShoppingCart, color: "text-blue-400", delay: 0 },
  { Icon: DollarSign, color: "text-emerald-400", delay: 0.5 },
  { Icon: Truck, color: "text-orange-400", delay: 1 },
  { Icon: Brain, color: "text-purple-400", delay: 1.5 },
  { Icon: Shield, color: "text-cyan-400", delay: 2 },
  { Icon: Zap, color: "text-yellow-400", delay: 2.5 },
]

// Плавающая иконка на фоне
function FloatingIcon({ Icon, color, delay, index }: { Icon: any; color: string; delay: number; index: number }) {
  const randomX = 10 + (index % 3) * 30
  const randomY = 10 + Math.floor(index / 3) * 40

  return (
    <motion.div
      className={`absolute ${color} opacity-20`}
      style={{
        left: `${randomX}%`,
        top: `${randomY}%`,
      }}
      initial={{ opacity: 0, scale: 0 }}
      animate={{
        opacity: [0.1, 0.3, 0.1],
        scale: [0.8, 1.2, 0.8],
        y: [0, -30, 0],
        rotate: [0, 10, -10, 0],
      }}
      transition={{
        duration: 6,
        repeat: Number.POSITIVE_INFINITY,
        delay,
        ease: "easeInOut",
      }}
    >
      <Icon className="h-12 w-12" />
    </motion.div>
  )
}

export default function LoginPage() {
  const router = useRouter()
  const [mounted, setMounted] = useState(false)

  const checkAuthStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/auth/status")
      const data = await response.json().catch(() => ({ authenticated: false }))
      if (response.ok && data.authenticated) {
        router.push("/")
      }
    } catch {
      // Пользователь не авторизован, остаемся на странице логина
    }
  }, [router])

  const checkOAuthErrors = useCallback(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const error = urlParams.get("error")
    const message = urlParams.get("message")
    const details = urlParams.get("details")

    if (error === "yandex_oauth_failed" && message) {
      // Показываем ошибку OAuth
      toast.error(message, {
        description: details || "",
        duration: 5000,
      })

      // Очищаем URL от параметров ошибки
      const cleanUrl = window.location.pathname
      window.history.replaceState({}, "", cleanUrl)
    }
  }, [])

  useEffect(() => {
    setMounted(true)
    // Проверяем, авторизован ли пользователь через серверную проверку
    void checkAuthStatus()
    
    // Проверяем OAuth ошибки от Яндекса
    checkOAuthErrors()
  }, [checkAuthStatus, checkOAuthErrors])

  const handleYandexLogin = useCallback(() => {
    window.location.href = "/api/yandex/login"
  }, [])

  if (!mounted) return null

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Анимированный фон */}
      <div className="absolute inset-0">
        {/* Сетка */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)
            `,
            backgroundSize: "50px 50px",
          }}
        />

        {/* Градиентные пятна */}
        <motion.div
          className="absolute top-0 left-0 w-[600px] h-[600px] bg-blue-500/20 rounded-full blur-[120px]"
          animate={{
            x: [0, 100, 0],
            y: [0, 50, 0],
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 15,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        />
        <motion.div
          className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-purple-500/20 rounded-full blur-[100px]"
          animate={{
            x: [0, -80, 0],
            y: [0, -60, 0],
            scale: [1, 1.3, 1],
          }}
          transition={{
            duration: 12,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        />
        <motion.div
          className="absolute top-1/2 left-1/3 w-[400px] h-[400px] bg-cyan-500/10 rounded-full blur-[80px]"
          animate={{
            x: [0, 60, 0],
            y: [0, -40, 0],
          }}
          transition={{
            duration: 10,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
          }}
        />

        {/* Плавающие иконки */}
        {floatingIcons.map((item, index) => (
          <FloatingIcon key={index} {...item} index={index} />
        ))}
      </div>

      {/* Контент */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="w-full max-w-md"
        >
          {/* Логотип */}
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="flex flex-col items-center mb-8"
          >
                      </motion.div>

          {/* Вход */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <div className="mx-auto flex max-w-sm flex-col items-center gap-6">
              <YandexLoginCircle onClick={handleYandexLogin} />
            </div>
          </motion.div>

        </motion.div>
      </div>
    </div>
  )
}
