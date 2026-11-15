// Centralised, validated access to Vite environment variables.
const DEFAULT_API_BASE_URL = 'http://localhost:8000'
const DEFAULT_TIMEOUT_MS = 8000

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
const rawTimeout = Number.parseInt(import.meta.env.VITE_API_TIMEOUT_MS, 10)

if (!rawBaseUrl && import.meta.env.PROD) {
  console.warn('[config] VITE_API_BASE_URL is not set; falling back to', DEFAULT_API_BASE_URL)
}

export const env = Object.freeze({
  apiBaseUrl: (rawBaseUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, ''),
  apiTimeoutMs: Number.isFinite(rawTimeout) && rawTimeout > 0 ? rawTimeout : DEFAULT_TIMEOUT_MS,
})
