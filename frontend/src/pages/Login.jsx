import { useNavigate, useSearchParams } from 'react-router-dom'
import LoginForm from '../components/LoginForm.jsx'

// /login — a HERO screen (decision F53): the first thing a judge sees.
// Sign-in succeeds -> continue to the page the visitor was heading for.
export default function Login() {
  const navigate = useNavigate()
  const [params] = useSearchParams()

  function target() {
    const next = params.get('next') || '/map'
    // same-app paths only — never an open redirect
    return next.startsWith('/') && !next.startsWith('//') ? next : '/map'
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-brand">
          <span className="dot" aria-hidden="true" />
          <h1>SENTINEL</h1>
        </div>
        <p className="login-sub">
          Integrated Video Management &amp; Analytics Platform — camera
          registry, live viewing, ANPR search and vehicle route
          reconstruction across departmental CCTV networks.
        </p>
        <LoginForm onSuccess={() => navigate(target(), { replace: true })} />
        <p className="login-foot">
          Gujarat Police Innovation Challenge 2026 · Authorised users only ·
          All activity is audited
        </p>
      </div>
    </div>
  )
}
