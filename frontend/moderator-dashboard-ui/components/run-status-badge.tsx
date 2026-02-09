"use client"

import { Badge } from "@/components/ui/badge"
import { CheckCircle, Activity, XCircle } from "lucide-react"

interface RunStatusBadgeProps {
  status: string
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  if (status === "completed") {
    return (
      <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/20">
        <CheckCircle className="h-3 w-3 mr-1" />
        Завершен
      </Badge>
    )
  }
  if (status === "running" || status === "starting") {
    return (
      <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20 hover:bg-blue-500/20">
        <Activity className="h-3 w-3 mr-1 animate-pulse" />
        Выполняется
      </Badge>
    )
  }
  return (
    <Badge className="bg-red-500/10 text-red-600 border-red-500/20 hover:bg-red-500/20">
      <XCircle className="h-3 w-3 mr-1" />
      Ошибка
    </Badge>
  )
}
