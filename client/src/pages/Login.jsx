import { useEffect, useState } from 'react'
import { BeakerIcon, EyeIcon, EyeSlashIcon, KeyIcon } from '@heroicons/react/24/outline'
import { getInstance, login } from '../services/api'
import { BASE_TITLE, styleFor } from '../components/instanceStyle'

// SH-3a: the login page for the token rung (docs/13-authentication.md).
//
// Shown by AuthGate whenever the server says a login is needed and this
// browser is not signed in. It asks for one thing, the access token, sends
// it once to /api/auth/login, and the server answers with a cookie the
// browser carries from then on. The page says which instance it belongs
// to first (the same pill as the top bar), because a tester with two
// addresses must know where a token is being pasted.

export default function Login({ mode = 'token', onSignedIn }) {
  const [instance, setInstance] = useState(null)
  const [token, setToken] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getInstance()
      .then((r) => {
        setInstance(r.data)
        document.title = `[${r.data.label}] Sign in – ${BASE_TITLE}`
      })
      .catch(() => setInstance(null))
    return () => {
      document.title = BASE_TITLE
    }
  }, [])
  const style = styleFor(instance)

  const submit = async (e) => {
    e.preventDefault()
    const value = token.trim()
    if (!value) {
      setError('Paste the access token first.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const { data } = await login(value)
      onSignedIn && onSignedIn(data.user)
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) {
        setError('That token was not accepted. Check for missing or extra characters and try again.')
      } else if (status === 400) {
        setError('This instance does not log in with a token. Reload the page.')
      } else {
        setError('The server could not be reached. Try again in a moment.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="login-page">
      <div className={`h-16 flex items-center px-4 lg:px-8 shadow-sm ${style.bar}`}>
        <BeakerIcon className="h-8 w-8 text-pandora-600" />
        <span className="ml-2 text-lg font-bold text-gray-800">Crucible</span>
        {instance && (
          <span
            className={`ml-3 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide ${style.pill}`}
            title={style.title}
            data-testid="instance-label"
          >
            {instance.label}
          </span>
        )}
        <span className="ml-auto text-sm text-gray-500">
          Running on port {window.location.port || (window.location.protocol === 'https:' ? '443' : '80')}
        </span>
      </div>

      <div className="flex-1 flex items-start justify-center px-4 pt-16">
        <div className="w-full max-w-md bg-white rounded-xl shadow-md border border-gray-200 p-8">
          <div className="flex items-center mb-4">
            <div className="rounded-full bg-pandora-50 p-2 mr-3">
              <KeyIcon className="h-6 w-6 text-pandora-700" />
            </div>
            <h1 className="text-xl font-semibold text-gray-900">Sign in with the access token</h1>
          </div>

          <p className="text-sm text-gray-600 mb-6">
            This instance asks for an <strong>access token</strong> before it shows any data. The person who
            runs it gives you the token. Paste it once: this browser stays signed in for ten hours, or until
            you sign out.
          </p>

          <form onSubmit={submit} className="space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Access token</span>
              <div className="mt-1 relative">
                <input
                  type={show ? 'text' : 'password'}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  autoFocus
                  placeholder="paste the token here"
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2 pr-11 font-mono text-sm focus:border-pandora-500 focus:ring-pandora-500"
                  data-testid="token-input"
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute inset-y-0 right-0 px-3 text-gray-400 hover:text-gray-600"
                  title={show ? 'Hide the token' : 'Show the token'}
                  aria-label={show ? 'Hide the token' : 'Show the token'}
                >
                  {show ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                </button>
              </div>
            </label>

            {error && (
              <p className="text-sm text-red-600" role="alert" data-testid="login-error">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-pandora-600 px-4 py-2 text-sm font-semibold text-white hover:bg-pandora-700 disabled:opacity-60"
              data-testid="sign-in"
            >
              {busy ? 'Checking…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-6 text-xs text-gray-500">
            A wrong token is refused with the same words as a missing one, on purpose. Scripts and{' '}
            <code>curl</code> send the same token as a header: <code>Authorization: Bearer …</code>.
          </p>
        </div>
      </div>
      <div className="p-4 text-center text-xs text-gray-400">
        Login mode: {mode} · Chemical &amp; Sample Management System
      </div>
    </div>
  )
}
