"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface EmptyStateProps {
  title: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export function EmptyState({ 
  title, 
  description, 
  icon, 
  action,
  className 
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className={cn("text-center py-8", className)}
    >
      {icon && (
        <div className="flex justify-center mb-4">
          <div className="text-muted-foreground">
            {icon}
          </div>
        </div>
      )}
      <h3 className="text-lg font-medium mb-2">{title}</h3>
      {description && (
        <p className="text-muted-foreground mb-4">{description}</p>
      )}
      {action && <div>{action}</div>}
    </motion.div>
  )
}
