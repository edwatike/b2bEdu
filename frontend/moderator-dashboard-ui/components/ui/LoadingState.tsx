"use client"

import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface LoadingStateProps {
  message?: string
  className?: string
  size?: "sm" | "md" | "lg"
}

export function LoadingState({ 
  message = "Загрузка...", 
  className,
  size = "md"
}: LoadingStateProps) {
  const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-8 w-8", 
    lg: "h-12 w-12"
  }

  return (
    <div className={cn("flex items-center justify-center py-8", className)}>
      <div className="flex items-center gap-2">
        <Loader2 className={cn("animate-spin", sizeClasses[size])} />
        {message && <span className="text-muted-foreground">{message}</span>}
      </div>
    </div>
  )
}
