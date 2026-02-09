"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

interface PageShellProps {
  children: React.ReactNode
  title?: string
  description?: string
  className?: string
  actions?: React.ReactNode
  icon?: LucideIcon
  gradientFrom?: string
  gradientTo?: string
}

export function PageShell({ 
  children, 
  title, 
  description, 
  className,
  actions,
  icon: Icon,
  gradientFrom = "from-indigo-600",
  gradientTo = "to-purple-600",
}: PageShellProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={cn("container mx-auto px-6 py-8 max-w-7xl space-y-6", className)}
    >
      {(title || description || actions) && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="flex items-center justify-between"
        >
          <div className="flex items-center gap-4">
            {Icon && (
              <div className={cn(
                "h-12 w-12 rounded-2xl bg-gradient-to-br flex items-center justify-center shadow-lg",
                gradientFrom, gradientTo,
                "shadow-indigo-500/25"
              )}>
                <Icon className="h-6 w-6 text-white" />
              </div>
            )}
            <div>
              {title && (
                <h1 className={cn(
                  "text-3xl font-bold tracking-tight",
                  Icon && "bg-gradient-to-r bg-clip-text text-transparent",
                  Icon && gradientFrom,
                  Icon && gradientTo,
                )}>
                  {title}
                </h1>
              )}
              {description && (
                <p className="text-muted-foreground">{description}</p>
              )}
            </div>
          </div>
          {actions && <div>{actions}</div>}
        </motion.div>
      )}
      {children}
    </motion.div>
  )
}
