"use client"

import { AuthGuard } from "@/components/auth-guard"
import { SuppliersClient } from "./suppliers-client"

export default function SuppliersPage() {
  return (
    <AuthGuard allowedRoles={["moderator"]}>
      <SuppliersClient />
    </AuthGuard>
  )
}
