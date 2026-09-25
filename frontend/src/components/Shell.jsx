import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../lib/api.js'
import { roleAtLeast, SessionContext } from '../lib/session.js'
import Header from './Header.jsx'
import StatusStrip from './StatusStrip.jsx'

// App shell: nav + header + status strip around every signed-in screen.
// Resolves the session from GET /api/auth/me before rendering anything;
// an unauthenticated visitor is sent to /login with a next param.
// Nav layout ported from D:\projects\Sentinel_Repo\ui\src\main.jsx (F52);
// S3.3 adds Command, Live Wall, Search, Route, Alerts, Zones, Reports.
export default function Shell() {
  const location = useLocation()
  const [state, setState] = useState({ status: 'loading', user: null })

  useEffect(() => {
    let alive = true
    api
      .me()
      .then((user) => alive && setState({ status: 'ready', user }))
      .catch((err) =>
        alive &&
        setState({ status: err.kind === 'auth' ? 'anonymous' : 'error', user: null })
      )
    return () => {
      alive = false
    }
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      window.location.replace('/login')
    }
  }, [])

  const session = useMemo(
    () => (state.user ? { ...state.user, signOut } : null),
    [state.user, signOut]
  )

  if (state.status === 'loading') {
    return <div className="screen-center">Checking session…</div>
  }
  if (state.status === 'anonymous') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (state.status === 'error') {
    return (
      <div className="screen-center">
        <div className="state-error">
          API unreachable — is the backend running?
        </div>
      </div>
    )
  }

  const link = ({ isActive }) => (isActive ? 'active' : '')
  // Actions above the role are HIDDEN, not just refused (decision F41):
  // reports are evaluator+, zone/tier edits admin-only (docs/api.md §7).
  const role = state.user?.role
  return (
    <SessionContext.Provider value={session}>
      <div className="app">
        <nav className="nav" aria-label="Main">
          <div className="brand">
            <span className="dot" aria-hidden="true" /> SENTINEL
          </div>
          <NavLink to="/command" className={link}>Command</NavLink>
          <NavLink to="/map" className={link}>Map</NavLink>
          <NavLink to="/wall" className={link}>Live Wall</NavLink>
          <NavLink to="/search" className={link}>Search</NavLink>
          <NavLink to="/route" className={link}>Route</NavLink>
          <NavLink to="/alerts" className={link}>Alerts</NavLink>
          <NavLink to="/cameras" className={link}>Cameras</NavLink>
          <NavLink to="/watchlist" className={link}>Watchlist</NavLink>
          {roleAtLeast(role, 'admin') && (
            <NavLink to="/zones" className={link}>Zones</NavLink>
          )}
          {roleAtLeast(role, 'evaluator') && (
            <NavLink to="/reports" className={link}>Reports</NavLink>
          )}
          <div className="nav-foot">
            Gujarat Police
            <br />
            Innovation Challenge 2026
          </div>
        </nav>
        <div className="main">
          <Header />
          <StatusStrip />
          <div className="content">
            <Outlet />
          </div>
        </div>
      </div>
    </SessionContext.Provider>
  )
}
