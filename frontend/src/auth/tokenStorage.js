// Access-token storage.
//
// Strategy: the token is held in memory and mirrored to sessionStorage so a page
// reload in the same tab keeps the user signed in. sessionStorage is scoped to one
// tab and cleared when it closes (unlike localStorage). Tradeoff: any script running
// on the page (XSS) can read it, so tokens are short-lived (30 min default), never
// put in URLs, and always re-verified by the backend. See README "Token storage".
const KEY = 'ecc.accessToken'

let memoryToken = null

function safeSession() {
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked (privacy mode, sandboxed iframe)
  }
}

export function getToken() {
  if (memoryToken) return memoryToken
  try {
    memoryToken = safeSession()?.getItem(KEY) ?? null
  } catch {
    memoryToken = null
  }
  return memoryToken
}

export function setToken(token) {
  memoryToken = token
  try {
    safeSession()?.setItem(KEY, token)
  } catch {
    /* in-memory only */
  }
}

export function clearToken() {
  memoryToken = null
  try {
    safeSession()?.removeItem(KEY)
  } catch {
    /* ignore */
  }
}

/**
 * Read the `exp` claim (ms since epoch) for UX purposes only (scheduling sign-out).
 * This does NOT verify the token - the backend does that on every request.
 */
export function getTokenExpiry(token) {
  try {
    const part = token.split('.')[1]
    const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'))
    const { exp } = JSON.parse(json)
    return typeof exp === 'number' ? exp * 1000 : null
  } catch {
    return null
  }
}

export function isTokenExpired(token, now = Date.now()) {
  const exp = getTokenExpiry(token)
  return exp === null || exp <= now
}
