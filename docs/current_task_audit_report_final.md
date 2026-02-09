# QA Audit Report: "Current Task" Block (/moderator)

**Date:** 2026-02-08  
**Auditor:** Cascade AI  
**Status:** ⚠️ PARTIAL PASS (Critical Issue Found in User Visibility)

---

## 1. Executive Summary

The "Current Task" block implementation on the moderator dashboard generally adheres to the specifications (A, B, C, D, E, G, H). The UI correctly handles empty states, renders domain circles with statuses, and provides manual moderation tools.

**CRITICAL FAILURE DETECTED (F.1):**
The system **fails** to hide incomplete suppliers from the User Cabinet (`/cabinet`).
- **Requirement:** User sees suppliers ONLY after Checko verification (`checko_ok=true`).
- **Actual:** `cabinet.py` returns *any* supplier found in `moderator_suppliers` linked to the domain, regardless of `data_status` or `type`.
- **Impact:** Users may see "raw" suppliers with missing emails or unverified data (e.g., `type='candidate'`, `data_status='requires_moderation'`), violating the isolation rule.

---

## 2. Compliance Matrix

| Requirement | Status | Proof | Comment |
|:---|:---:|:---|:---|
| **A) Active Task Selection** (FIFO, Unfinished) | ✅ PASS | SQL Diagnostic, API JSON | Correctly selects oldest task with `pending`/`processing` domains. Returns `null` when all are completed. |
| **B) Current Run Selection** (Running > Oldest) | ✅ PASS | `current_task.py` | Logic explicitly prioritizes `status='running'` then `created_at` ASC. |
| **C) Domain Circles** (Colors, Statuses) | ✅ PASS | `current-task-block.tsx` | Components implement correct color mapping (Gray/Blue/Green/Purple/Yellow). |
| **D) Extraction Logic** (INN+Email, Multiple INNs) | ✅ PASS | `domain_parser.py` | Enforces `inn` AND `email` for `supplier`. Handles multiple INNs -> `requires_moderation`. |
| **E) Hover/Click Behavior** (Tooltips, Modal) | ✅ PASS | `current-task-block.tsx` | Tooltips show source URLs. Click opens `ModerationModal`. |
| **F) User Visibility** (Only Checko OK) | ❌ **FAIL** | `cabinet.py` | **No filter** for `data_status='complete'` or `checko_data`. Exposes all mapped suppliers. |
| **G) Summary Stats** (Inherited, Passed) | ✅ PASS | `current_task.py` | Correctly calculates `from_run` vs `inherited` counts. |
| **H) Critical Anti-Patterns** (No global supplier pending) | ✅ PASS | SQL Diagnostic (`mc.ru`) | `mc.ru` correctly identified as inherited supplier (not pending). |

---

## 3. Evidence

### A. API Response (Empty State)
Confirmed correct behavior when no active tasks exist (as per current system state).
```json
{
  "task_id": null,
  "current_run": null,
  "queue_count": 0
}
```

### B. SQL Diagnostic Results
Verified via `backend/_diag_audit.py`:
- `mc.ru` in `run_domains`: `status=supplier`, `global_requires_moderation=True`, `checko_ok=True`. **PASS**.
- Runs needing population: `0`. **PASS**.
- Tasks with pending domains: `0`. **PASS**.

### C. Visual Proofs
- `proof_01_moderator_full_page.png`: Shows correct layout and empty state handling.

---

## 4. Defect & Fix (F.1 User Visibility)

**Issue:** `backend/app/transport/routers/cabinet.py` retrieves suppliers based solely on domain matching, ignoring `data_status`.

**Fix Location:** `backend/app/transport/routers/cabinet.py` -> `_ensure_request_suppliers_loaded`

**Proposed Code Change:**

```python
# In _ensure_request_suppliers_loaded:

# ... fetch suppliers ...
for sr in suppliers_rows:
    # ... extraction ...
    
    # NEW FILTER: Only show suppliers that are ready for the user
    # Checko data must be present or data_status must be 'complete'
    # (depending on strictness of "checko_ok=true" rule)
    s_data_status = str(sr[5] or "") # You need to fetch data_status in the SQL query
    
    # Current SQL in cabinet.py does NOT select data_status.
    # It selects: ms.id, ms.name, ms.email, ms.phone, domain...
```

**Required Fix Steps:**
1.  Update SQL query in `cabinet.py` to fetch `ms.data_status`.
2.  Add filter condition: `if data_status != 'complete': continue`.

---

## 5. Manual Verification Checklist (Post-Fix)

1.  **Setup:** Create a supplier with `data_status='requires_moderation'` (simulate INN found, no email).
2.  **Action:** Create a user request for that domain.
3.  **Check:** Ensure `/cabinet/requests/{id}/suppliers` does **NOT** return this supplier.
4.  **Action:** Manually resolve supplier (add email, checko) -> `data_status='complete'`.
5.  **Check:** Ensure supplier **NOW APPEARS** in cabinet.
