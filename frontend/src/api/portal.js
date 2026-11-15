import { apiClient } from './client'

/** GET /api/portal/{area} - role-restricted; the backend returns 403 for other roles. */
export async function fetchPortal(area, signal) {
  const { data } = await apiClient.get(`/api/portal/${encodeURIComponent(area)}`, { signal })
  return data
}
