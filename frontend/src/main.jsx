import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css' // bundled, never a CDN (offline venue)
import './styles/tokens.css'
import './styles/app.css'
import Shell from './components/Shell.jsx'
import Alerts from './pages/Alerts.jsx'
import Cameras from './pages/Cameras.jsx'
import Command from './pages/Command.jsx'
import LiveWall from './pages/LiveWall.jsx'
import Login from './pages/Login.jsx'
import MapPage from './pages/Map.jsx'
import Reports from './pages/Reports.jsx'
import RoutePage from './pages/Route.jsx'
import Search from './pages/Search.jsx'
import Watchlist from './pages/Watchlist.jsx'
import Zones from './pages/Zones.jsx'

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
          <Route path="/" element={<Navigate to="/map" replace />} />
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
          <Route path="*" element={<Navigate to="/map" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
