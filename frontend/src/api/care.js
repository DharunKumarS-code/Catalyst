import { apiClient } from './client'

/** GET /api/care-dashboard: read-only summary of every profile actively linked to the signed-in member. */
export async function getCareDashboard(signal) {
  const { data } = await apiClient.get('/api/care-dashboard', { signal })
  return data
}
