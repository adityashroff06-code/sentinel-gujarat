// Session context: who is signed in and what their role allows.
// The role comes from GET /api/auth/me; actions above the role are
// HIDDEN, not just refused (frontend/CLAUDE.md, decision F41).

import { createContext, useContext } from 'react'

export const SessionContext = createContext(null)

/** {username, role, expires_at, signOut} — provided by Shell. */
export function useSession() {
  return useContext(SessionContext)
}

const ROLE_ORDER = { viewer: 0, evaluator: 1, admin: 2 }

/** True when `role` is at least `minimum` (viewer < evaluator < admin). */
export function roleAtLeast(role, minimum) {
  return (ROLE_ORDER[role] ?? -1) >= (ROLE_ORDER[minimum] ?? Infinity)
}
