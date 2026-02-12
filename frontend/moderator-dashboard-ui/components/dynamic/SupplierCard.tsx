"use client"

import dynamic from "next/dynamic"
import { Loader2 } from "lucide-react"
import type { SupplierDTO } from "@/lib/types"

const SupplierCardImpl = dynamic(() => import("../company-card/supplier-company-card").then(mod => ({ default: mod.SupplierCompanyCard })), {
  loading: () => (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="h-8 w-8 animate-spin" />
    </div>
  ),
  ssr: false,
})

interface SupplierCardProps {
  supplier: SupplierDTO
  onSupplierUpdate?: (supplier: SupplierDTO) => void
}

export function SupplierCard({ supplier, onSupplierUpdate }: SupplierCardProps) {
  return <SupplierCardImpl supplier={supplier} onSupplierUpdate={onSupplierUpdate} />
}
