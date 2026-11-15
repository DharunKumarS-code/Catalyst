import { apiClient } from './client'

export async function listNotifications(signal) {
  const { data } = await apiClient.get('/api/notifications', { params: { limit: 50 }, signal })
  return data
}

export async function getNotificationPreferences(signal) {
  const { data } = await apiClient.get('/api/notifications/preferences', { signal })
  return data
}

export async function updateNotificationPreferences(prefs) {
  const { data } = await apiClient.put('/api/notifications/preferences', prefs)
  return data
}

export async function getNotificationStatus(signal) {
  const { data } = await apiClient.get('/api/notifications/status', { signal })
  return data
}

/** Queues a test message to yourself; the server delivers it after responding. */
export async function sendTestNotification() {
  const { data } = await apiClient.post('/api/notifications/test')
  return data
}
