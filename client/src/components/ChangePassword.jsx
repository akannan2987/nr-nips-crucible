import { useState } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { changePassword } from '../services/api'

// SH-3b: a signed-in person changes their own password (docs/13-authentication.md).
//
// The operator hands out a first, temporary password out of band; this
// dialog is where the person replaces it with one only they know. The
// server checks the current password, applies the one rule (length),
// and signs every OTHER browser of theirs out; this one stays in.

export default function ChangePassword({ onClose }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (next !== again) {
      setError('The two new passwords differ.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await changePassword(current, next)
      toast.success('Password changed. Any other browser signed in as you is signed out within a minute.')
      onClose()
    } catch (err) {
      const status = err?.response?.status
      const message = err?.response?.data?.error
      if (status === 400 && message) {
        setError(message)
      } else if (status === 401) {
        setError('You are no longer signed in. Reload the page and sign in again.')
      } else {
        setError('The server could not be reached. Try again in a moment.')
      }
    } finally {
      setBusy(false)
    }
  }

  const field = (label, value, setValue, autoComplete, testId) => (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input
        type="password"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoComplete={autoComplete}
        required
        className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm focus:border-pandora-500 focus:ring-pandora-500"
        data-testid={testId}
      />
    </label>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-gray-600 bg-opacity-50 px-4 pt-24" data-testid="change-password-dialog">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Change your password</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          At least eight characters; a phrase you can remember beats a short scramble. Every other browser
          signed in as you is signed out within a minute; this one stays in.
        </p>
        <form onSubmit={submit} className="space-y-3">
          {field('Current password', current, setCurrent, 'current-password', 'current-password')}
          {field('New password', next, setNext, 'new-password', 'new-password')}
          {field('New password, again', again, setAgain, 'new-password', 'new-password-again')}
          {error && (
            <p className="text-sm text-red-600" role="alert" data-testid="change-password-error">
              {error}
            </p>
          )}
          <div className="flex justify-end space-x-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-pandora-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-pandora-700 disabled:opacity-60"
              data-testid="change-password-submit"
            >
              {busy ? 'Saving…' : 'Change password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
