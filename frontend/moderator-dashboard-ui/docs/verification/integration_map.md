# ⚠️ DEPRECATED — см. docs/PROJECT_PLAYBOOK.md (раздел 9)

# Integration Map — Оптимизации B2B Frontend

> Дата: 2026-02-07
> Branch: `perf/refactor-2025-07`

## Таблица интеграции: Page → Optimized Component → Evidence

| Route | File | Optimized Component | Evidence |
|---|---|---|---|
| `/moderator` | `app/moderator/page.tsx` | Re-exports `page-optimized.tsx` (React Query hooks: `useModeratorStats`, `useParsingRuns`, `AuthGuard`) | `export { default } from "./page-optimized"` (line 3) |
| `/suppliers` | `app/suppliers/suppliers-client.tsx` | `SuppliersTableVirtualized` (виртуализация @tanstack/react-virtual) | `import { SuppliersTableVirtualized } from "@/components/supplier/SuppliersTableVirtualized"` (line 10) |
| `/suppliers/[id]` | `app/suppliers/[id]/supplier-detail-client.tsx` | Dynamic `SupplierCard` (code-splitting via `next/dynamic`) | `import { SupplierCard } from "@/components/dynamic/SupplierCard"` (line 11) |

## Dynamic Imports (Code Splitting)

| Wrapper | Source | Technique |
|---|---|---|
| `components/dynamic/SupplierCard.tsx` | `components/supplier-card.tsx` → `SupplierCard` | `next/dynamic` with loading spinner |
| `components/dynamic/ChartSection.tsx` | `components/supplier-card.tsx` → `ChartSection` | `next/dynamic` with loading spinner |

## React Query Hooks (Data Fetching)

| Hook | File | Used By |
|---|---|---|
| `useModeratorStats` | `hooks/queries/parsing.ts` | `app/moderator/page-optimized.tsx` |
| `useParsingRuns` | `hooks/queries/parsing.ts` | `app/moderator/page-optimized.tsx` |
| `useSuppliers` | `hooks/queries/suppliers.ts` | Available for future use |

## setInterval Removal

| File | Before | After |
|---|---|---|
| `components/animated-logo.tsx` | `setInterval(…, 2000)` | Recursive `setTimeout` with cleanup |
| `app/login/page.tsx` | `setInterval(…, 2000)` (AnimatedCenterLogo) | Recursive `setTimeout` with cleanup |
| `app/keywords/page.tsx` | `setInterval(loadKeywords, 30000)` | Recursive `setTimeout` with cleanup |
| `app/moderator/tasks/page.tsx` | `setInterval(load, 30000)` | Recursive `setTimeout` with cleanup |
| `app/cabinet/requests/[id]/page.tsx` | `window.setInterval(tick, 10000)` | Recursive `setTimeout` with cleanup |
| `app/parsing-runs/[runId]/page.tsx` | `setInterval(poll, 8000)` ×2 | Recursive `setTimeout` with cleanup ×2 |

**Total setInterval in prod code after fix: 0** (verified via `grep_setinterval_after.txt`)

## Unified UI Components

| Component | File | Purpose |
|---|---|---|
| `PageShell` | `components/ui/PageShell.tsx` | Consistent page layout with title/description/actions |
| `SectionCard` | `components/ui/SectionCard.tsx` | Consistent card sections |
| `LoadingState` | `components/ui/loading-state.tsx` | Unified loading indicators |
| `EmptyState` | `components/ui/empty-state.tsx` | Unified empty state displays |

## RBAC

| Component | File | Mechanism |
|---|---|---|
| `AuthGuard` | `components/auth-guard.tsx` | `allowedRoles` array; moderator-only routes redirect unauthorized to `/cabinet`; admin supersedes |
