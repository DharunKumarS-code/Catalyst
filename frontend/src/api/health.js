import { apiClient } from './client'

/**
 * GET /api/health - returns application and database status.
 * @param {AbortSignal} [signal]
 */
export async function fetchHealth(signal) {
  const { data } = await apiClient.get('/api/health', { signal })
  return data
}
