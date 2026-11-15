import axios from 'axios'
import { getToken } from '../auth/tokenStorage'
import { env } from '../config/env'

// Shared Axios instance for all backend calls.
export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: env.apiTimeoutMs,
  headers: { Accept: 'application/json' },
})

// Attach the access token (if any) to every request.
apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Notify the auth layer when an authenticated request is rejected (expired/revoked token).
let unauthorizedHandler = null
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const sentToken = Boolean(error.config?.headers?.Authorization)
    if (error.response?.status === 401 && sentToken) unauthorizedHandler?.()
    return Promise.reject(error)
  },
)

/** Prefer the backend's `detail` string when present; otherwise a generic message. */
export function getApiErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (error?.response?.status === 422) return fallback ?? 'Please check the highlighted fields.'
  return error?.response ? (fallback ?? describeApiError(error)) : describeApiError(error)
}

/** Map FastAPI 422 errors to { fieldName: message }. */
export function getFieldErrors(error) {
  const detail = error?.response?.data?.detail
  if (!Array.isArray(detail)) return {}
  return detail.reduce((acc, item) => {
    const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null
    if (typeof field === 'string' && !acc[field]) acc[field] = String(item.msg).replace(/^Value error, /, '')
    return acc
  }, {})
}

/**
 * Convert any Axios error into a short, user-safe message.
 */
export function describeApiError(error) {
  if (axios.isCancel(error)) return 'Request was cancelled.'
  if (error.code === 'ECONNABORTED') return 'The server took too long to respond.'
  if (error.response) return `Server responded with status ${error.response.status}.`
  if (error.request) return 'Unable to reach the server. Check that the backend is running.'
  return 'An unexpected error occurred.'
}
