/**
 * ActivityChart Component
 * 
 * График активности по дням для дашборда
 */

"use client"

import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TrendingUp } from "lucide-react"

interface ActivityData {
  date: string
  count: number
}

interface ActivityChartProps {
  data: ActivityData[]
}

export function ActivityChart({ data }: ActivityChartProps) {
  // Находим максимальное значение для масштабирования
  const maxCount = Math.max(...data.map(d => d.count), 1)

  return (
    <Card className="bg-gradient-to-br from-white to-blue-50 border-blue-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-blue-600" />
          Активность по дням
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64 flex items-end justify-between gap-2">
          {data.map((item, index) => {
            const height = (item.count / maxCount) * 100
            
            return (
              <motion.div
                key={item.date}
                className="flex-1 relative group cursor-pointer"
                initial={{ height: 0 }}
                animate={{ height: `${height}%` }}
                transition={{ duration: 0.5, delay: index * 0.05 }}
              >
                <div className="absolute inset-0 bg-gradient-to-t from-blue-600 to-blue-400 rounded-t-md hover:from-blue-700 hover:to-blue-500 transition-colors">
                  {/* Tooltip */}
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-neutral-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                    <div className="font-semibold">{item.count} запусков</div>
                    <div className="text-neutral-300">{item.date}</div>
                    {/* Arrow */}
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
                      <div className="border-4 border-transparent border-t-neutral-900"></div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
        
        {/* X-axis labels */}
        <div className="flex justify-between mt-2 text-xs text-neutral-500">
          {data.map((item, index) => {
            // Показываем только каждую 2-ю метку для читаемости
            if (index % 2 === 0) {
              return (
                <span key={item.date} className="flex-1 text-center">
                  {item.date}
                </span>
              )
            }
            return <span key={item.date} className="flex-1"></span>
          })}
        </div>
      </CardContent>
    </Card>
  )
}
