import { apiClient } from './client'

/** POST /api/auth/register -> { access_token, token_type, expires_in, user } */
export async function registerUser({ name, email, password, role }) {
  const { data } = await apiClient.post('/api/auth/register', { name, email, password, role })
  return data
}

/** POST /api/auth/login -> { access_token, token_type, expires_in, user } */
export async function loginUser({ email, password }) {
  const { data } = await apiClient.post('/api/auth/login', { email, password })
  return data
}

/**
 * GET /api/auth/demo-accounts -> [{ role, email, password }] (sample credentials).
 * The backend answers 404 when demo mode is disabled; treat that as "no demo accounts".
 */
export async function fetchDemoAccounts(signal) {
  try {
    const { data } = await apiClient.get('/api/auth/demo-accounts', { signal })
    const list = Array.isArray(data) ? data : []
    if (import.meta.env.DEV && list.length === 0) {
      console.info('[demo] Demo accounts section hidden: none provisioned. Run `python -m app.scripts.seed_demo_accounts` in backend/.')
    }
    return list
  } catch (error) {
    if (error.response?.status === 404) {
      if (import.meta.env.DEV) {
        console.info('[demo] Demo accounts section hidden: demo mode is off. Set DEMO_ACCOUNTS_ENABLED=true in backend/.env and restart the API.')
      }
      return []
    }
    throw error
  }
}

/** GET /api/auth/me -> user for the current token */
export async function fetchCurrentUser(signal) {
  const { data } = await apiClient.get('/api/auth/me', { signal })
  return data
}
