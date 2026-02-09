"use client"

import { AuthGuard } from "@/components/auth-guard"
import { SupplierEditClient } from "../[id]/edit/supplier-edit-client"

export default function SupplierCreatePage() {
  // Для создания нового поставщика передаем 0 или null
  // SupplierEditClient должен обрабатывать это как режим создания
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <SupplierEditClient supplierId={0} />
    </AuthGuard>
  )
}
