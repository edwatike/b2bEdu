/**
 * DashboardStats Component
 * 
 * KPI карточки для главного дашборда
 */

"use client"

import { motion } from "framer-motion"
import { Building2, Ban, Activity, TrendingUp, Users, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { colors } from "@/lib/design-system"

interface DashboardStatsProps {
  suppliersCount: number
  resellersCount: number
  blacklistCount: number
  activeParsingCount: number
  todayParsingCount: number
  successRate: number
}

export function DashboardStats({
  suppliersCount,
  resellersCount,
  blacklistCount,
  activeParsingCount,
  todayParsingCount,
  successRate
}: DashboardStatsProps) {
  const stats = [
    {
      title: "Поставщики",
      value: suppliersCount,
      icon: Building2,
      color: "blue",
      gradient: "from-blue-500 to-cyan-500",
      bgGradient: "from-blue-50 to-cyan-50",
      borderColor: "border-blue-200"
    },
    {
      title: "Реселлеры",
      value: resellersCount,
      icon: Users,
      color: "purple",
      gradient: "from-purple-500 to-indigo-500",
      bgGradient: "from-purple-50 to-indigo-50",
      borderColor: "border-purple-200"
    },
    {
      title: "В Blacklist",
      value: blacklistCount,
      icon: Ban,
      color: "red",
      gradient: "from-red-500 to-orange-500",
      bgGradient: "from-red-50 to-orange-50",
      borderColor: "border-red-200"
    },
    {
      title: "Активные парсинги",
      value: activeParsingCount,
      icon: Activity,
      color: "green",
      gradient: "from-green-500 to-emerald-500",
      bgGradient: "from-green-50 to-emerald-50",
      borderColor: "border-green-200"
    },
    {
      title: "Парсингов сегодня",
      value: todayParsingCount,
      icon: Clock,
      color: "orange",
      gradient: "from-orange-500 to-amber-500",
      bgGradient: "from-orange-50 to-amber-50",
      borderColor: "border-orange-200"
    },
    {
      title: "Успешность",
      value: `${successRate}%`,
      icon: TrendingUp,
      color: "teal",
      gradient: "from-teal-500 to-cyan-500",
      bgGradient: "from-teal-50 to-cyan-50",
      borderColor: "border-teal-200"
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {stats.map((stat, index) => (
        <motion.div
          key={stat.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: index * 0.1 }}
        >
          <Card className={`bg-gradient-to-br ${stat.bgGradient} ${stat.borderColor} hover:shadow-lg transition-shadow cursor-pointer`}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-neutral-600 mb-1">{stat.title}</p>
                  <motion.p 
                    className="text-3xl font-bold"
                    style={{ color: colors[stat.color as keyof typeof colors]?.[600] || colors.neutral[900] }}
                    initial={{ scale: 0.5 }}
                    animate={{ scale: 1 }}
                    transition={{ duration: 0.5, delay: index * 0.1 + 0.2 }}
                  >
                    {stat.value}
                  </motion.p>
                </div>
                <motion.div 
                  className={`h-14 w-14 rounded-xl bg-gradient-to-br ${stat.gradient} flex items-center justify-center shadow-lg`}
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  transition={{ duration: 0.2 }}
                >
                  <stat.icon className="h-7 w-7 text-white" />
                </motion.div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  )
}
