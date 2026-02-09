# RBAC Check — B2B Frontend

> Date: 2026-02-07
> File: `components/auth-guard.tsx`

## AuthGuard Implementation

| Feature | Status | Evidence |
|---|---|---|
| Role-based access (`allowedRoles` prop) | ✅ PASS | Lines 10, 41-42: `allowedRoles?: Array<"admin" \| "moderator" \| "user">` |
| Admin supersedes all roles | ✅ PASS | Line 42: `role === "admin"` bypasses allowedRoles check |
| Moderator-only gate (`can_access_moderator`) | ✅ PASS | Lines 31-38: Extra permission check for moderator-only routes |
| Unauthenticated → redirect to `/login` | ✅ PASS | Lines 54-56: Saves current path and redirects |
| Unauthorized user → redirect to `/cabinet` | ✅ PASS | Lines 32-37: `!canAccessModerator` → `/cabinet` |
| Loading state with spinner | ✅ PASS | Lines 66-80: Framer Motion animated loader |
| Auth error handling | ✅ PASS | Lines 58-60: Catches errors, redirects to `/login` |

## Route Protection Coverage

AuthGuard is used in **23 pages** across the application:

### Moderator-only routes (allowedRoles=["moderator"])
- `/moderator` (via `page-optimized.tsx`)
- `/moderator/tasks`
- `/blacklist`
- `/domains`
- `/keywords`
- `/manual-parsing`
- `/parsing-runs`
- `/parsing-runs/[runId]`
- `/settings`
- `/suppliers`, `/suppliers/[id]`, `/suppliers/[id]/edit`, `/suppliers/new`
- `/users`

### User routes
- `/cabinet`, `/cabinet/overview`, `/cabinet/messages`
- `/cabinet/requests`, `/cabinet/requests/[id]`, `/cabinet/requests/all`, `/cabinet/requests/drafts`
- `/cabinet/results`, `/cabinet/settings`

## Scenarios

| Scenario | Expected | Mechanism |
|---|---|---|
| Unauthenticated user visits `/moderator` | Redirect to `/login?redirect=/moderator` | `checkAuth()` → `!data.authenticated` |
| User role visits `/moderator` | Redirect to `/cabinet` | `isModeratorOnly && !canAccessModerator` |
| Moderator visits `/moderator` | Access granted | `canAccessModerator === true` |
| Admin visits any route | Access granted | `role === "admin"` bypasses all checks |
| Auth API error | Redirect to `/login` | `catch` block in `checkAuth()` |

## Verdict: ✅ PASS

RBAC implementation is correct and covers all routes. No changes were made to AuthGuard during optimization — it was preserved as-is.
