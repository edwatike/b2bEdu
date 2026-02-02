"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { getSuppliers } from "@/lib/api"
import { SupplierDTO } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Navigation } from "@/components/navigation"
import { SuppliersTable } from "@/components/supplier/SuppliersTable"
import { SkeletonCard } from "@/components/ui/skeleton"
import { toast } from "sonner"
import { Plus, Building2 } from "lucide-react"

export function SuppliersClient() {
  const router = useRouter()
  const [suppliers, setSuppliers] = useState<SupplierDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadSuppliers()
  }, [])

  async function loadSuppliers() {
    try {
      setLoading(true)
      const data = await getSuppliers({ limit: 100, offset: 0 })
      setSuppliers(data.suppliers)
      setError(null)
    } catch (err) {
      toast.error("Ошибка загрузки поставщиков")
      setError("Ошибка загрузки поставщиков")
      console.error("Error loading suppliers:", err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
        <Navigation />
        <motion.main 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="container mx-auto px-6 py-6 max-w-7xl"
        >
          <div className="space-y-6">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </motion.main>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-red-50/30">
        <Navigation />
        <motion.main 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="container mx-auto px-6 py-6 max-w-7xl"
        >
          <div className="text-center py-12">
            <div className="text-6xl mb-4">⚠️</div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-2">Ошибка загрузки</h2>
            <p className="text-neutral-600 mb-4">{error}</p>
            <Button onClick={loadSuppliers}>Попробовать снова</Button>
          </div>
        </motion.main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50">
      <Navigation />
      <motion.main 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container mx-auto px-6 py-6 max-w-7xl"
      >
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex items-center justify-between mb-6"
        >
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-primary-600 to-primary-700 flex items-center justify-center shadow-lg">
              <Building2 className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-primary-600 to-primary-800 bg-clip-text text-transparent">
                Поставщики
              </h1>
              <p className="text-neutral-600 mt-1">Управление поставщиками и реселлерами</p>
            </div>
          </div>
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Button 
              onClick={() => router.push("/suppliers/new")} 
              className="bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 text-white shadow-lg"
            >
              <Plus className="mr-2 h-4 w-4" />
              Добавить поставщика
            </Button>
          </motion.div>
        </motion.div>

        {/* Таблица с новым компонентом */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
        >
          <SuppliersTable suppliers={suppliers} onRefresh={loadSuppliers} />
        </motion.div>
      </motion.main>
    </div>
  )
}
