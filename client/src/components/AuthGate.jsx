import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getAuthMe, logout as apiLogout, UNAUTHENTICATED_EVENT } from '../services/api'
import Login from '../pages/Login'

// SH-3a: the gate in front of the whole page (docs/13-authentication.md).
//
// On load it asks the server one open question, /api/auth/me: which login
// mode is on, and is this browser signed in? With the login off, or once
// signed in, it renders the application; otherwise it renders the login
// page and nothing else. Any later 401 from any call (the API layer raises
// an event for it) puts the login page back; after a successful login the
// routes mount again, so whatever page was open asks for its data again.
// That is the whole 401 handler: nothing else in the client changed.

const AuthContext = createContext({ mode: 'off', user: null, signOut: () => {} })

export const useAuth = () => useContext(AuthContext)

export default function AuthGate({ children }) {
  const [state, setState] = useState({ loading: true, mode: 'off', authenticated: false, user: null })

  const refresh = useCallback(() => {
    getAuthMe()
      .then(({ data }) => {
        // A server without this route (there is none since v2.22.0, but a
        // page is only as careful as its worst day) answers the HTML shell
        // instead of JSON: treat that as "no login".
        const mode = data && typeof data === 'object' && data.mode ? data.mode : 'off'
        setState({ loading: false, mode, authenticated: mode === 'off' || !!data.authenticated, user: data?.user || null })
      })
      .catch(() => setState({ loading: false, mode: 'off', authenticated: true, user: null }))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const onUnauthenticated = () => setState((s) => ({ ...s, authenticated: false, user: null }))
    window.addEventListener(UNAUTHENTICATED_EVENT, onUnauthenticated)
    return () => window.removeEventListener(UNAUTHENTICATED_EVENT, onUnauthenticated)
  }, [])

  const signOut = useCallback(() => {
    apiLogout()
      .catch(() => {})
      .then(() => setState((s) => ({ ...s, authenticated: false, user: null })))
  }, [])

  if (state.loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50" data-testid="auth-loading">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pandora-600"></div>
      </div>
    )
  }

  if (state.mode !== 'off' && !state.authenticated) {
    return (
      <Login
        mode={state.mode}
        onSignedIn={(user) => setState((s) => ({ ...s, authenticated: true, user }))}
      />
    )
  }

  return (
    <AuthContext.Provider value={{ mode: state.mode, user: state.user, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}
