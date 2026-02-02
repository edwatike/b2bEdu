/**
 * SupplierFinancials Component
 * 
 * Финансовый блок с интерактивными графиками и метриками
 * Включает: выручка, прибыль, уставный капитал, тренды
 */

"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { TrendingUp, TrendingDown, DollarSign, Calendar, BarChart3 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { colors } from "@/lib/design-system"
import type { SupplierDTO } from "@/lib/types"

interface SupplierFinancialsProps {
  supplier: SupplierDTO
}

export function SupplierFinancials({ supplier }: SupplierFinancialsProps) {
  const [selectedYear, setSelectedYear] = useState(supplier.financeYear?.toString() || new Date().getFullYear().toString())
  
  // Форматирование чисел
  const formatCurrency = (value: number | null | undefined) => {
    if (!value) return '—'
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value)
  }

  const formatNumber = (value: number | null | undefined) => {
    if (!value) return '—'
    return new Intl.NumberFormat('ru-RU').format(value)
  }

  // Вычисляем процент изменения (mock data для демонстрации)
  const revenueChange = supplier.revenue ? ((supplier.revenue / 10000000) * 15).toFixed(1) : null
  const profitMargin = supplier.revenue && supplier.profit 
    ? ((supplier.profit / supplier.revenue) * 100).toFixed(1) 
    : null

  return (
    <div className="space-y-6">
      {/* Заголовок с селектором года */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary-600" />
          <h3 className="text-lg font-semibold text-neutral-900">Финансовые показатели</h3>
        </div>
        
        <Select value={selectedYear} onValueChange={setSelectedYear}>
          <SelectTrigger className="w-[140px]">
            <Calendar className="h-4 w-4 mr-2" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[2024, 2023, 2022, 2021].map(year => (
              <SelectItem key={year} value={year.toString()}>
                {year} год
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Ключевые метрики */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Выручка */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200">
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-2">
                <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <DollarSign className="h-5 w-5 text-blue-600" />
                </div>
                {revenueChange && (
                  <div className={`flex items-center gap-1 text-sm font-medium ${
                    parseFloat(revenueChange) > 0 ? 'text-success-600' : 'text-danger-600'
                  }`}>
                    {parseFloat(revenueChange) > 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    {Math.abs(parseFloat(revenueChange))}%
                  </div>
                )}
              </div>
              <p className="text-sm text-neutral-600 mb-1">Выручка</p>
              <p className="text-2xl font-bold text-neutral-900">
                {formatCurrency(supplier.revenue)}
              </p>
              <p className="text-xs text-neutral-500 mt-1">за {selectedYear} год</p>
            </CardContent>
          </Card>
        </motion.div>

        {/* Прибыль */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <Card className={`bg-gradient-to-br ${
            supplier.profit && supplier.profit > 0 
              ? 'from-green-50 to-white border-green-200' 
              : 'from-red-50 to-white border-red-200'
          }`}>
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-2">
                <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                  supplier.profit && supplier.profit > 0 
                    ? 'bg-green-100' 
                    : 'bg-red-100'
                }`}>
                  <TrendingUp className={`h-5 w-5 ${
                    supplier.profit && supplier.profit > 0 
                      ? 'text-green-600' 
                      : 'text-red-600'
                  }`} />
                </div>
                {profitMargin && (
                  <div className="text-sm font-medium text-neutral-600">
                    {profitMargin}% маржа
                  </div>
                )}
              </div>
              <p className="text-sm text-neutral-600 mb-1">Прибыль</p>
              <p className={`text-2xl font-bold ${
                supplier.profit && supplier.profit > 0 
                  ? 'text-green-700' 
                  : 'text-red-700'
              }`}>
                {formatCurrency(supplier.profit)}
              </p>
              <p className="text-xs text-neutral-500 mt-1">чистая прибыль</p>
            </CardContent>
          </Card>
        </motion.div>

        {/* Уставный капитал */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-200">
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-2">
                <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                  <BarChart3 className="h-5 w-5 text-purple-600" />
                </div>
              </div>
              <p className="text-sm text-neutral-600 mb-1">Уставный капитал</p>
              <p className="text-2xl font-bold text-neutral-900">
                {formatCurrency(supplier.authorizedCapital)}
              </p>
              <p className="text-xs text-neutral-500 mt-1">зарегистрированный</p>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* График динамики (упрощенная визуализация) */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Динамика выручки</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48 flex items-end justify-between gap-2">
              {/* Простая bar chart визуализация */}
              {generateMockData(supplier.revenue).map((value, index) => {
                const height = (value / Math.max(...generateMockData(supplier.revenue))) * 100
                return (
                  <motion.div
                    key={index}
                    className="flex-1 bg-gradient-to-t from-primary-600 to-primary-400 rounded-t-md relative group cursor-pointer"
                    initial={{ height: 0 }}
                    animate={{ height: `${height}%` }}
                    transition={{ duration: 0.5, delay: 0.4 + index * 0.1 }}
                    whileHover={{ opacity: 0.8 }}
                  >
                    {/* Tooltip on hover */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-neutral-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {formatCurrency(value)}
                    </div>
                  </motion.div>
                )
              })}
            </div>
            <div className="flex justify-between mt-2 text-xs text-neutral-500">
              {['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'].map(month => (
                <span key={month}>{month}</span>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Дополнительные метрики */}
      {(supplier.legalCasesCount !== null || supplier.legalCasesSum !== null) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <Card className="bg-gradient-to-br from-orange-50 to-white border-orange-200">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-orange-600" />
                Судебные разбирательства
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Всего дел</p>
                  <p className="text-xl font-bold text-neutral-900">
                    {formatNumber(supplier.legalCasesCount)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Сумма исков</p>
                  <p className="text-xl font-bold text-neutral-900">
                    {formatCurrency(supplier.legalCasesSum)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Истец</p>
                  <p className="text-xl font-bold text-blue-600">
                    {formatNumber(supplier.legalCasesAsPlaintiff)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600 mb-1">Ответчик</p>
                  <p className="text-xl font-bold text-red-600">
                    {formatNumber(supplier.legalCasesAsDefendant)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  )
}

// Helper function для генерации mock данных для графика
function generateMockData(baseRevenue: number | null | undefined): number[] {
  if (!baseRevenue) return Array(12).fill(0)
  
  // Генерируем данные с небольшими вариациями
  return Array.from({ length: 12 }, (_, i) => {
    const variation = (Math.random() - 0.5) * 0.3 // ±15% вариация
    return Math.max(0, baseRevenue * (1 + variation) / 12)
  })
}
