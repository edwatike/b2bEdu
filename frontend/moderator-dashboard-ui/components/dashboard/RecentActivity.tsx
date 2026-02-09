/**
 * RecentActivity Component
 * 
 * Лента недавних действий для дашборда
 */

"use client"

import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { History, Plus, Trash2, Edit, Ban, CheckCircle } from "lucide-react"

interface ActivityItem {
  id: string
  type: "create" | "delete" | "edit" | "blacklist" | "parsing"
  entity: string
  description: string
  timestamp: string
}

interface RecentActivityProps {
  activities: ActivityItem[]
}

export function RecentActivity({ activities }: RecentActivityProps) {
  const getIcon = (type: string) => {
    switch (type) {
      case "create":
        return <Plus className="h-4 w-4 text-green-600" />
      case "delete":
        return <Trash2 className="h-4 w-4 text-red-600" />
      case "edit":
        return <Edit className="h-4 w-4 text-blue-600" />
      case "blacklist":
        return <Ban className="h-4 w-4 text-orange-600" />
      case "parsing":
        return <CheckCircle className="h-4 w-4 text-purple-600" />
      default:
        return <History className="h-4 w-4 text-neutral-600" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case "create":
        return "bg-green-100 text-green-700 border-green-200"
      case "delete":
        return "bg-red-100 text-red-700 border-red-200"
      case "edit":
        return "bg-blue-100 text-blue-700 border-blue-200"
      case "blacklist":
        return "bg-orange-100 text-orange-700 border-orange-200"
      case "parsing":
        return "bg-purple-100 text-purple-700 border-purple-200"
      default:
        return "bg-neutral-100 text-neutral-700 border-neutral-200"
    }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      
      if (diffMins < 1) return "только что"
      if (diffMins < 60) return `${diffMins} мин назад`
      
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours} ч назад`
      
      const diffDays = Math.floor(diffHours / 24)
      return `${diffDays} дн назад`
    } catch {
      return timestamp
    }
  }

  return (
    <Card className="bg-gradient-to-br from-white to-neutral-50 border-neutral-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5 text-neutral-600" />
          Недавние действия
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {activities.length === 0 ? (
            <div className="text-center py-8 text-neutral-500">
              <History className="h-8 w-8 mx-auto mb-2 text-neutral-300" />
              <p className="text-sm">Нет недавних действий</p>
            </div>
          ) : (
            activities.map((activity, index) => (
              <motion.div
                key={activity.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                className="flex items-start gap-3 p-3 rounded-lg hover:bg-neutral-50 transition-colors"
              >
                <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${getTypeColor(activity.type)}`}>
                  {getIcon(activity.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-xs">
                      {activity.entity}
                    </Badge>
                    <span className="text-xs text-neutral-500">
                      {formatTimestamp(activity.timestamp)}
                    </span>
                  </div>
                  <p className="text-sm text-neutral-700">{activity.description}</p>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
