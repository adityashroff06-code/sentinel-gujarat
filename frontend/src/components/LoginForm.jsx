import { useState } from 'react'
import { api } from '../lib/api.js'

// The login form: username + password, ONE error message that never says
// which half was wrong (frontend/CLAUDE.md; decision F41).
export default function LoginForm({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const me = await api.login(username.trim(), password)
      onSuccess?.(me)
    } catch (err) {
      if (err.status === 429) {
        setError('Too many failed attempts — try again in 15 minutes.')
      } else if (err.kind === 'network') {
        setError('Cannot reach the platform. Check the connection and retry.')
      } else {
        // 401 and anything else: one unspecific message.
        setError('Sign-in failed. Check the username and password.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      {error && (
        <div className="login-error" role="alert">
          {error}
        </div>
      )}
      <div className="field">
        <label htmlFor="login-username">Username</label>
        <input
          id="login-username"
          name="username"
          autoComplete="username"
          autoFocus
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <button className="primary" type="submit" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}
