"use client"

import { useParams } from "next/navigation"
import { AuthGuard } from "@/components/auth-guard"
import { SupplierEditClient } from "./supplier-edit-client"

function SupplierEditPageInner() {
  const params = useParams()
  const supplierId = parseInt(String(params.id || ""), 10)

  if (Number.isNaN(supplierId) || supplierId <= 0) {
    return <div className="text-red-500 p-4">Ошибка: Неверный ID поставщика</div>
  }

  return <SupplierEditClient supplierId={supplierId} />
}

export default function SupplierEditPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <SupplierEditPageInner />
    </AuthGuard>
  )
}
