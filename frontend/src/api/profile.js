import { apiClient } from './client'

/** GET /api/profiles/me -> profile, or null if the user has not created one yet. */
export async function getMyProfile(signal) {
  try {
    const { data } = await apiClient.get('/api/profiles/me', { signal })
    return data
  } catch (error) {
    if (error.response?.status === 404) return null
    throw error
  }
}

export async function createMyProfile(profile) {
  const { data } = await apiClient.post('/api/profiles/me', profile)
  return data
}

export async function updateMyProfile(profile) {
  const { data } = await apiClient.put('/api/profiles/me', profile)
  return data
}
