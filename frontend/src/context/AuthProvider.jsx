import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCurrentUser, loginUser, registerUser } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'
import { clearToken, getToken, getTokenExpiry, isTokenExpired, setToken } from '../auth/tokenStorage'
import { normalizeEmail } from '../auth/validation'
import { AuthContext } from './AuthContext'

const NOTICES = {
  expired: 'Your session has ended. Please sign in again.',
  signedOut: 'You have been signed out.',
}

function initialState() {
  const token = getToken()
  if (token && !isTokenExpired(token)) return { status: 'initializing', user: null, token, notice: null }
  if (token) clearToken()
  return { status: 'anonymous', user: null, token: null, notice: null }
}

export default function AuthProvider({ children }) {
  const [state, setState] = useState(initialState)

  const logout = useCallback((reason = 'signedOut') => {
    clearToken()
    setState({ status: 'anonymous', user: null, token: null, notice: NOTICES[reason] ?? null })
  }, [])

  const startSession = useCallback(({ access_token: token, user }) => {
    setToken(token)
    setState({ status: 'authenticated', user, token, notice: null })
    return user
  }, [])

  // Restore a stored session by asking the backend who the token belongs to.
  const restoringToken = state.status === 'initializing' ? state.token : null
  useEffect(() => {
    if (!restoringToken) return undefined
    const controller = new AbortController()
    fetchCurrentUser(controller.signal).then(
      (user) => setState({ status: 'authenticated', user, token: restoringToken, notice: null }),
      () => {
        if (controller.signal.aborted) return
        clearToken()
        setState({ status: 'anonymous', user: null, token: null, notice: null })
      },
    )
    return () => controller.abort()
  }, [restoringToken])

  // Any authenticated request rejected with 401 ends the session.
  useEffect(() => {
    setUnauthorizedHandler(() => logout('expired'))
    return () => setUnauthorizedHandler(null)
  }, [logout])

  // Sign out automatically when the token expires.
  const activeToken = state.status === 'authenticated' ? state.token : null
  useEffect(() => {
    if (!activeToken) return undefined
    const expiry = getTokenExpiry(activeToken)
    if (expiry === null) return undefined
    // setTimeout max is ~24.8 days; tokens are far shorter-lived.
    const timer = setTimeout(() => logout('expired'), Math.max(0, expiry - Date.now()))
    return () => clearTimeout(timer)
  }, [activeToken, logout])

  const login = useCallback(
    async ({ email, password }) => startSession(await loginUser({ email: normalizeEmail(email), password })),
    [startSession],
  )

  const register = useCallback(
    async ({ name, email, password, role }) =>
      startSession(await registerUser({ name: name.trim(), email: normalizeEmail(email), password, role })),
    [startSession],
  )

  const value = useMemo(
    () => ({ status: state.status, user: state.user, notice: state.notice, login, register, logout }),
    [state.status, state.user, state.notice, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
