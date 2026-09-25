import React, { lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css' // bundled, never a CDN (offline venue)
import './styles/tokens.css'
import './styles/app.css'
import Shell from './components/Shell.jsx'
import Alerts from './pages/Alerts.jsx'
import Cameras from './pages/Cameras.jsx'
import Login from './pages/Login.jsx'
import Reports from './pages/Reports.jsx'
import Search from './pages/Search.jsx'
import Watchlist from './pages/Watchlist.jsx'

// The leaflet- and hls-heavy pages load as route-level chunks (S3.3b:
// the single 993 kB bundle split inside the existing dependencies —
// Vite handles the chunking; Shell's <Suspense> shows a designed
// fallback while a chunk arrives). Login and the light pages stay in
// the entry bundle so first paint needs one file.
const Command = lazy(() => import('./pages/Command.jsx'))
const LiveWall = lazy(() => import('./pages/LiveWall.jsx'))
const MapPage = lazy(() => import('./pages/Map.jsx'))
const RoutePage = lazy(() => import('./pages/Route.jsx'))
const Zones = lazy(() => import('./pages/Zones.jsx'))

// Route skeleton ported from D:\projects\Sentinel_Repo\ui\src\main.jsx
// (F52), rebuilt around the login (decision F41): /login is the only
// public screen; everything else renders inside Shell, which resolves
// the session first. S3.3 added the operations screens: Command, Live
// Wall, Search, Route, Alerts, Zones, Reports.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Shell />}>
          {/* the evaluator's first screen is Command: the F46 Start-here
              panel must be what a judge sees before anything else */}
          <Route path="/" element={<Navigate to="/command" replace />} />
          <Route path="/command" element={<Command />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/wall" element={<LiveWall />} />
          <Route path="/search" element={<Search />} />
          <Route path="/route" element={<RoutePage />} />
          <Route path="/route/:plate" element={<RoutePage />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/cameras" element={<Cameras />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/zones" element={<Zones />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="*" element={<Navigate to="/command" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
