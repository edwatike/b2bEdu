/**
 * SupplierHero Component
 * 
 * Hero Section для страницы детализации поставщика
 * Включает: название компании, ИНН, статус, город, рейтинг риска
 */

"use client"

import { motion } from "framer-motion"
import { Building2, MapPin, Hash, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { colors, getRiskColor, getRiskLabel } from "@/lib/design-system"
import type { SupplierDTO } from "@/lib/types"

interface SupplierHeroProps {
  supplier: SupplierDTO
}

export function SupplierHero({ supplier }: SupplierHeroProps) {
  // Вычисляем risk score на основе данных компании
  const riskScore = calculateRiskScore(supplier)
  const riskColor = getRiskColor(riskScore)
  const riskLabel = getRiskLabel(riskScore)
  
  // Определяем цвет вердикта
  const verdictColor = riskScore <= 30 ? 'success' : riskScore <= 60 ? 'warning' : 'danger'
  
  return (
    <div className="space-y-6">
      {/* Основная информация + Рейтинг */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Левая часть - Основная информация */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-2"
        >
          <Card className="p-6 bg-gradient-to-br from-white to-neutral-50 border-neutral-200">
            <div className="space-y-4">
              {/* Название компании */}
              <div>
                <div className="flex items-start justify-between gap-4">
                  <h1 className="text-3xl font-bold text-neutral-900 flex items-center gap-3">
                    <Building2 className="h-8 w-8 text-primary-600" />
                    {supplier.name}
                  </h1>
                  <Badge 
                    variant={supplier.type === 'supplier' ? 'default' : 'secondary'}
                    className="text-sm px-3 py-1"
                  >
                    {supplier.type === 'supplier' ? 'Поставщик' : 'Реселлер'}
                  </Badge>
                </div>
              </div>

              {/* Метаданные */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                {/* ИНН */}
                {supplier.inn && (
                  <div className="flex items-center gap-2 text-neutral-600">
                    <Hash className="h-4 w-4 text-neutral-400" />
                    <span className="text-sm font-medium">ИНН:</span>
                    <span className="font-mono text-sm font-semibold text-neutral-900">
                      {supplier.inn}
                    </span>
                  </div>
                )}

                {/* Город */}
                {supplier.legalAddress && (
                  <div className="flex items-center gap-2 text-neutral-600">
                    <MapPin className="h-4 w-4 text-neutral-400" />
                    <span className="text-sm font-medium">Адрес:</span>
                    <span className="text-sm text-neutral-900 truncate">
                      {extractCity(supplier.legalAddress)}
                    </span>
                  </div>
                )}
              </div>

              {/* Дополнительная информация */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-neutral-200">
                {supplier.email && (
                  <div>
                    <p className="text-xs text-neutral-500 mb-1">Email</p>
                    <p className="text-sm font-medium text-neutral-900 truncate">{supplier.email}</p>
                  </div>
                )}
                {supplier.phone && (
                  <div>
                    <p className="text-xs text-neutral-500 mb-1">Телефон</p>
                    <p className="text-sm font-medium text-neutral-900">{supplier.phone}</p>
                  </div>
                )}
                {supplier.domain && (
                  <div>
                    <p className="text-xs text-neutral-500 mb-1">Домен</p>
                    <p className="text-sm font-medium text-primary-600 truncate">{supplier.domain}</p>
                  </div>
                )}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Правая часть - Рейтинг риска */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Card className="p-6 bg-gradient-to-br from-white to-neutral-50 border-neutral-200 h-full flex flex-col justify-center items-center">
            <div className="text-center space-y-4">
              <p className="text-sm font-medium text-neutral-600">Оценка риска</p>
              
              {/* Круговой индикатор */}
              <div className="relative">
                <svg className="w-32 h-32 transform -rotate-90">
                  {/* Background circle */}
                  <circle
                    cx="64"
                    cy="64"
                    r="56"
                    stroke={colors.neutral[200]}
                    strokeWidth="8"
                    fill="none"
                  />
                  {/* Progress circle */}
                  <motion.circle
                    cx="64"
                    cy="64"
                    r="56"
                    stroke={riskColor}
                    strokeWidth="8"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 56}`}
                    initial={{ strokeDashoffset: 2 * Math.PI * 56 }}
                    animate={{ strokeDashoffset: 2 * Math.PI * 56 * (1 - riskScore / 100) }}
                    transition={{ duration: 1, ease: "easeOut" }}
                  />
                </svg>
                
                {/* Score text */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <motion.span 
                    className="text-4xl font-bold"
                    style={{ color: riskColor }}
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                  >
                    {riskScore}
                  </motion.span>
                  <span className="text-xs text-neutral-500">из 100</span>
                </div>
              </div>

              {/* Лейбл риска */}
              <div>
                <Badge 
                  className="text-sm px-4 py-1"
                  style={{ 
                    backgroundColor: `${riskColor}15`,
                    color: riskColor,
                    borderColor: riskColor
                  }}
                >
                  {riskLabel}
                </Badge>
              </div>

              {/* Тренд */}
              {supplier.revenue && supplier.profit && (
                <div className="flex items-center justify-center gap-2 text-sm">
                  {supplier.profit > 0 ? (
                    <>
                      <TrendingUp className="h-4 w-4 text-success-600" />
                      <span className="text-success-600 font-medium">Позитивная динамика</span>
                    </>
                  ) : (
                    <>
                      <TrendingDown className="h-4 w-4 text-danger-600" />
                      <span className="text-danger-600 font-medium">Негативная динамика</span>
                    </>
                  )}
                </div>
              )}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Вердикт-баннер */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <Card 
          className={`p-4 border-l-4 ${
            verdictColor === 'success' 
              ? 'bg-success-50 border-success-500' 
              : verdictColor === 'warning'
              ? 'bg-warning-50 border-warning-500'
              : 'bg-danger-50 border-danger-500'
          }`}
        >
          <div className="flex items-center gap-3">
            <AlertTriangle 
              className={`h-5 w-5 ${
                verdictColor === 'success' 
                  ? 'text-success-600' 
                  : verdictColor === 'warning'
                  ? 'text-warning-600'
                  : 'text-danger-600'
              }`}
            />
            <div>
              <p className={`font-semibold ${
                verdictColor === 'success' 
                  ? 'text-success-900' 
                  : verdictColor === 'warning'
                  ? 'text-warning-900'
                  : 'text-danger-900'
              }`}>
                {getVerdictText(riskScore, supplier)}
              </p>
              <p className={`text-sm ${
                verdictColor === 'success' 
                  ? 'text-success-700' 
                  : verdictColor === 'warning'
                  ? 'text-warning-700'
                  : 'text-danger-700'
              }`}>
                {getVerdictDescription(riskScore, supplier)}
              </p>
            </div>
          </div>
        </Card>
      </motion.div>
    </div>
  )
}

// Helper functions

function calculateRiskScore(supplier: SupplierDTO): number {
  let score = 50 // Базовый средний риск
  
  // Позитивные факторы (снижают риск)
  if (supplier.revenue && supplier.revenue > 10000000) score -= 10
  if (supplier.profit && supplier.profit > 0) score -= 10
  if (supplier.authorizedCapital && supplier.authorizedCapital > 100000) score -= 5
  if (supplier.legalCasesCount === 0) score -= 15
  if (supplier.email && supplier.phone) score -= 5
  
  // Негативные факторы (повышают риск)
  if (supplier.legalCasesCount && supplier.legalCasesCount > 5) score += 20
  if (supplier.profit && supplier.profit < 0) score += 15
  if (!supplier.email || !supplier.phone) score += 10
  if (supplier.companyStatus && supplier.companyStatus.includes('ликвидац')) score += 30
  
  // Ограничиваем диапазон 0-100
  return Math.max(0, Math.min(100, score))
}

function extractCity(address: string): string {
  // Простое извлечение города из адреса
  const cityMatch = address.match(/г\.\s*([^,]+)/)
  return cityMatch ? cityMatch[1].trim() : address.substring(0, 50)
}

function getVerdictText(score: number, supplier: SupplierDTO): string {
  if (score <= 30) return '✓ Компания рекомендована для сотрудничества'
  if (score <= 60) return '⚠ Требуется дополнительная проверка'
  return '✗ Высокий риск - сотрудничество не рекомендуется'
}

function getVerdictDescription(score: number, supplier: SupplierDTO): string {
  if (score <= 30) {
    return 'Финансовые показатели стабильны, судебных разбирательств не выявлено'
  }
  if (score <= 60) {
    return 'Обнаружены факторы риска, рекомендуется углубленная проверка'
  }
  return 'Выявлены критические факторы риска, требуется особое внимание'
}
