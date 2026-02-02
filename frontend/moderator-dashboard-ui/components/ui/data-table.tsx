"use client"

import { motion } from "framer-motion"
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface DataTableProps {
  children: ReactNode
  className?: string
}

export function DataTable({ children, className }: DataTableProps) {
  return (
    <div className={cn("rounded-xl border border-border/50 bg-card overflow-hidden shadow-lg", className)}>
      {children}
    </div>
  )
}

interface DataTableHeaderProps {
  children: ReactNode
  className?: string
}

export function DataTableHeader({ children, className }: DataTableHeaderProps) {
  return (
    <div
      className={cn("bg-gradient-to-r from-muted/80 to-muted/40 backdrop-blur-sm border-b border-border/50", className)}
    >
      <div className="grid items-center px-4 py-3 text-sm font-semibold text-muted-foreground">{children}</div>
    </div>
  )
}

interface DataTableRowProps {
  children: ReactNode
  onClick?: () => void
  className?: string
  index?: number
  isSelected?: boolean
}

export function DataTableRow({ children, onClick, className, index = 0, isSelected }: DataTableRowProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -50 }}
      transition={{ duration: 0.2, delay: index * 0.03 }}
      onClick={onClick}
      className={cn(
        "grid items-center px-4 py-3 border-b border-border/30 last:border-b-0",
        "transition-all duration-200 ease-out",
        "hover:bg-accent/50 hover:shadow-md hover:-translate-y-[1px]",
        onClick && "cursor-pointer",
        isSelected && "bg-primary/5 border-l-2 border-l-primary",
        className,
      )}
    >
      {children}
    </motion.div>
  )
}

interface DataTableCellProps {
  children: ReactNode
  className?: string
}

export function DataTableCell({ children, className }: DataTableCellProps) {
  return <div className={cn("min-w-0", className)}>{children}</div>
}

interface DataTableEmptyProps {
  icon?: ReactNode
  title: string
  description?: string
}

export function DataTableEmpty({ icon, title, description }: DataTableEmptyProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center justify-center py-16 px-4 text-center"
    >
      {icon && <div className="h-16 w-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4">{icon}</div>}
      <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
      {description && <p className="text-sm text-muted-foreground max-w-sm">{description}</p>}
    </motion.div>
  )
}

interface DataTableSkeletonProps {
  rows?: number
  columns?: number
}

export function DataTableSkeleton({ rows = 5, columns = 4 }: DataTableSkeletonProps) {
  const widths = [66, 74, 82, 90, 70, 86, 78, 92]
  return (
    <div className="space-y-1">
      {[...Array(rows)].map((_, i) => (
        <div
          key={i}
          className="grid gap-4 px-4 py-3 animate-pulse"
          style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
        >
          {[...Array(columns)].map((_, j) => (
            <div
              key={j}
              className="h-4 bg-muted rounded"
              style={{ width: `${widths[(i + j) % widths.length]}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
