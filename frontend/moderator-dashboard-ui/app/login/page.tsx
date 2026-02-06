"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { toast } from "sonner"
import { ShoppingCart, DollarSign, Truck, Brain, Shield, Zap, Mail } from "lucide-react"

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
      </motion.div>

      {/* Иконка */}
      <div className="absolute inset-0 flex items-center justify-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            initial={{ scale: 0, rotate: -180, opacity: 0 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            exit={{ scale: 0, rotate: 180, opacity: 0 }}
            transition={{
              duration: 0.6,
              type: "spring",
              stiffness: 180,
              damping: 12,
            }}
          >
            <current.Icon className="h-10 w-10 text-white drop-shadow-lg" />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Орбитальные частицы */}
      {[...Array(6)].map((_, i) => (
        <motion.div
          key={i}
          className={`absolute h-2 w-2 rounded-full bg-gradient-to-r ${current.gradient}`}
          style={{
            top: "50%",
            left: "50%",
          }}
          animate={{
            x: [0, Math.cos((i * Math.PI) / 3) * 50, 0],
            y: [0, Math.sin((i * Math.PI) / 3) * 50, 0],
            opacity: [0, 1, 0],
            scale: [0, 1.5, 0],
          }}
          transition={{
            duration: 2.5,
            repeat: Number.POSITIVE_INFINITY,
            delay: i * 0.4,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

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

  useEffect(() => {
    setMounted(true)
    // Проверяем, авторизован ли пользователь через серверную проверку
    checkAuthStatus()
    
    // Проверяем OAuth ошибки от Яндекса
    checkOAuthErrors()
  }, [])

  async function checkAuthStatus() {
    try {
      const response = await fetch("/api/auth/status")
      const data = await response.json().catch(() => ({ authenticated: false }))
      if (response.ok && data.authenticated) {
        router.push("/")
      }
    } catch (error) {
      // Пользователь не авторизован, остаемся на странице логина
    }
  }

  function checkOAuthErrors() {
    const urlParams = new URLSearchParams(window.location.search)
    const error = urlParams.get("error")
    const message = urlParams.get("message")
    const details = urlParams.get("details")
    
    if (error === "yandex_oauth_failed" && message) {
      // Показываем ошибку OAuth
      toast.error(message, {
        description: details || "",
        duration: 5000
      })
      
      // Очищаем URL от параметров ошибки
      const cleanUrl = window.location.pathname
      window.history.replaceState({}, "", cleanUrl)
    }
  }

  async function handleYandexLogin() {
    try {
      window.location.href = "/api/yandex/login"
    } catch (error) {
      toast.error("Ошибка при переходе к авторизации Яндекса")
    }
  }

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
            <AnimatedCenterLogo />
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="mt-6 text-3xl font-bold text-white"
            >
              Модератор
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="mt-2 text-slate-400 text-sm"
            >
              Система управления поставщиками
            </motion.p>
          </motion.div>

          {/* Форма */}
          <Card className="bg-white/5 backdrop-blur-xl border-white/10 shadow-2xl">
            <CardContent className="p-8">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                <Button
                  type="button"
                  onClick={handleYandexLogin}
                  className="w-full h-12 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-semibold shadow-lg shadow-red-500/25 transition-all duration-300"
                >
                  <span className="flex items-center justify-center gap-2">
                    <Mail className="h-5 w-5" />
                    Войти через Яндекс
                  </span>
                </Button>
              </motion.div>
            </CardContent>
          </Card>

          {/* Футер */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="mt-6 text-center text-xs text-slate-500"
          >
            © 2026 Moderator System. Все права защищены.
          </motion.p>
        </motion.div>
      </div>
    </div>
  )
}
