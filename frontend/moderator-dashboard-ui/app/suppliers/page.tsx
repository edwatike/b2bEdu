"use client"

import { Suspense } from "react"
import { AuthGuard } from "@/components/auth-guard"
import { SuppliersClient } from "./suppliers-client"

export default function SuppliersPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <Suspense fallback={<div className="p-8 text-center text-muted-foreground">Загрузка...</div>}>
        <SuppliersClient />
      </Suspense>
    </AuthGuard>
  )
}
