import { useLocation } from 'react-router-dom'
import { api } from '../lib/api.js'
import { usePolled } from '../lib/poll.js'
import { useSession } from '../lib/session.js'

// Header — live counts from /api/stats through the ONE shared poller, plus
// the session menu (signed-in user, role, sign-out — decision F41).
// Ported from D:\projects\Sentinel_Repo\ui\src\components\Header.jsx (F52);
// rewired off its private setInterval and onto lib/poll.js.

const TITLES = {
  '/command': 'Command',
  '/map': 'GIS Map',
  '/wall': 'Live Wall',
  '/search': 'ANPR Search',
  '/alerts': 'Live Alerts',
  '/cameras': 'Camera Registry',
  '/watchlist': 'Watchlist',
  '/zones': 'Zone Editor',
  '/reports': 'Reports',
}

export default function Header() {
  const location = useLocation()
  const session = useSession()
  const polled = usePolled('stats', api.stats, 5000)
  const s = polled?.data

  const title =
    TITLES[location.pathname] ||
    (location.pathname.startsWith('/route') ? 'Route Reconstruction' : 'Integrated CCTV Command')
  return (
    <div className="header">
      <h1>{title}</h1>
      <span className="spacer" />
      <div className="stat">
        <b>{s ? `${s.cameras_online}/${s.cameras_total}` : '—'}</b>cameras online
      </div>
      <div className="stat">
        <b>{s ? s.departments : '—'}</b>departments
      </div>
      <div className="stat">
        <b>{s ? s.sightings_total : '—'}</b>sightings
      </div>
      <div className="stat">
        <b>{s ? s.plates_unique : '—'}</b>plates
      </div>
      <div className="stat alert">
        <b>{s ? s.alerts_active : '—'}</b>active alerts
      </div>
      {session && (
        <div className="session">
          <div className="who">
            <div className="name">{session.username ?? 'API key'}</div>
            <div className="role">{session.role}</div>
          </div>
          <button className="ghost" onClick={session.signOut}>
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
