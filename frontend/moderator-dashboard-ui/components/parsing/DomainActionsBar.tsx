"use client"

import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Copy, FileSearch } from "lucide-react"
import { toast } from "sonner"

interface DomainActionsBarProps {
  selectedDomains: Set<string>
  parserLoading: boolean
  onSelectAll: () => void
  onDeselectAll: () => void
  onStartParser: () => void
}

export function DomainActionsBar({
  selectedDomains,
  parserLoading,
  onSelectAll,
  onDeselectAll,
  onStartParser,
}: DomainActionsBarProps) {
  const copySelectedDomains = () => {
    if (selectedDomains.size === 0) {
      toast.error("Выберите хотя бы один домен")
      return
    }
    const domainsText = Array.from(selectedDomains).join("\n")
    navigator.clipboard.writeText(domainsText)
    toast.success(`Скопировано ${selectedDomains.size} доменов`)
  }

  return (
    <div className="space-y-3">
      {/* Кнопки выбора всех/снятия выбора */}
      <div className="flex items-center gap-2">
        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
          <Button
            size="sm"
            variant="outline"
            onClick={onSelectAll}
            className="h-7 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
          >
            Выбрать все
          </Button>
        </motion.div>
        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
          <Button
            size="sm"
            variant="outline"
            onClick={onDeselectAll}
            className="h-7 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
          >
            Снять выбор
          </Button>
        </motion.div>
        {selectedDomains.size > 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            <Badge variant="outline" className="bg-purple-50 border-purple-200 text-purple-700">
              Выбрано: {selectedDomains.size}
            </Badge>
          </motion.div>
        )}
      </div>

      {/* Кнопки действий */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center gap-2 flex-wrap"
      >
        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
          <Button
            size="sm"
            variant="outline"
            onClick={copySelectedDomains}
            disabled={selectedDomains.size === 0}
            className="h-8 text-xs border-purple-300 text-purple-700 hover:bg-purple-50 bg-transparent"
          >
            <Copy className="h-3 w-3 mr-1" />
            Копировать ({selectedDomains.size})
          </Button>
        </motion.div>
        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
          <Button
            size="sm"
            onClick={onStartParser}
            disabled={parserLoading || selectedDomains.size === 0}
            className="h-8 text-xs bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white"
          >
            <FileSearch className="h-3 w-3 mr-1" />
            Получить данные ({selectedDomains.size})
          </Button>
        </motion.div>
      </motion.div>
    </div>
  )
}
