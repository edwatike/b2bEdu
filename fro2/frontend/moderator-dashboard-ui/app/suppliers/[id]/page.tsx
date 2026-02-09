"use client"

import { useParams } from "next/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { SupplierDetail } from "@/components/supplier/SupplierDetail"

function SupplierDetailPageInner() {
  const params = useParams()
  const supplierId = parseInt(String(params.id || ""), 10)

  if (Number.isNaN(supplierId) || supplierId <= 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-neutral-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold text-neutral-900 mb-2">Неверный ID поставщика</h1>
          <p className="text-neutral-600">Проверьте правильность ссылки</p>
        </div>
      </div>
    )
  }

  return <SupplierDetail supplierId={supplierId} />
}

export default function SupplierDetailPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <SupplierDetailPageInner />
    </AuthGuard>
  )
}
