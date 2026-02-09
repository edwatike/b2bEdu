"use client"

import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface SectionCardProps {
  children: React.ReactNode
  title?: string
  description?: string
  className?: string
  delay?: number
}

export function SectionCard({ 
  children, 
  title, 
  description, 
  className,
  delay = 0
}: SectionCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
    >
      <Card className={cn("", className)}>
        {(title || description) && (
          <CardHeader>
            {title && <CardTitle>{title}</CardTitle>}
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </CardHeader>
        )}
        <CardContent>
          {children}
        </CardContent>
      </Card>
    </motion.div>
  )
}
