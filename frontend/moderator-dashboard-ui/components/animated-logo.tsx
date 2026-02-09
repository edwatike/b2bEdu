"use client"

import { motion, AnimatePresence } from "framer-motion"
import { useState, useEffect } from "react"
import { ShoppingCart, DollarSign, Truck, Brain } from "lucide-react"

const icons = [
  { Icon: ShoppingCart, color: "from-blue-500 to-blue-600", label: "Закупки" },
  { Icon: DollarSign, color: "from-emerald-500 to-emerald-600", label: "Деньги" },
  { Icon: Truck, color: "from-orange-500 to-orange-600", label: "Доставка" },
  { Icon: Brain, color: "from-purple-500 to-violet-600", label: "ИИ" },
]

export function AnimatedLogo() {
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const tick = () => {
      if (cancelled) return
      setCurrentIndex((prev) => (prev + 1) % icons.length)
      timeoutId = setTimeout(tick, 2000)
    }

    timeoutId = setTimeout(tick, 2000)

    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [])

  const currentIcon = icons[currentIndex]

  return (
    <div className="relative h-8 w-8">
      {/* Внешнее свечение */}
      <motion.div
        className={`absolute inset-0 rounded-lg bg-gradient-to-br ${currentIcon.color} opacity-30 blur-md`}
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 2,
          repeat: Number.POSITIVE_INFINITY,
          ease: "easeInOut",
        }}
      />

      {/* Основной контейнер с градиентом */}
      <motion.div
        className={`relative h-full w-full rounded-lg bg-gradient-to-br ${currentIcon.color} flex items-center justify-center overflow-hidden`}
        animate={{
          rotate: [0, 360],
        }}
        transition={{
          duration: 8,
          repeat: Number.POSITIVE_INFINITY,
          ease: "linear",
        }}
      >
        {/* Вращающийся блик */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-tr from-white/30 via-transparent to-transparent"
          animate={{
            rotate: [0, 360],
          }}
          transition={{
            duration: 3,
            repeat: Number.POSITIVE_INFINITY,
            ease: "linear",
          }}
        />
      </motion.div>

      {/* Иконка - не вращается с контейнером */}
      <div className="absolute inset-0 flex items-center justify-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            initial={{ scale: 0, rotate: -180, opacity: 0 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            exit={{ scale: 0, rotate: 180, opacity: 0 }}
            transition={{
              duration: 0.5,
              type: "spring",
              stiffness: 200,
              damping: 15,
            }}
          >
            <currentIcon.Icon className="h-4 w-4 text-white drop-shadow-md" />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Частицы вокруг */}
      {[...Array(4)].map((_, i) => (
        <motion.div
          key={i}
          className={`absolute h-1 w-1 rounded-full bg-gradient-to-r ${currentIcon.color}`}
          style={{
            top: "50%",
            left: "50%",
          }}
          animate={{
            x: [0, Math.cos((i * Math.PI) / 2) * 20, 0],
            y: [0, Math.sin((i * Math.PI) / 2) * 20, 0],
            opacity: [0, 1, 0],
            scale: [0, 1, 0],
          }}
          transition={{
            duration: 2,
            repeat: Number.POSITIVE_INFINITY,
            delay: i * 0.5,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}
