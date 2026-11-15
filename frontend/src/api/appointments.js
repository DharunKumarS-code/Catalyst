import { apiClient } from './client'

// Owner calls use /api/appointments; caretakers/family pass `profileId` for the read-only
// /api/linked-profiles/{id}/appointments endpoints. The server authorizes every request.
const base = (profileId) =>
  profileId ? `/api/linked-profiles/${encodeURIComponent(profileId)}/appointments` : '/api/appointments'
const id = (value) => encodeURIComponent(value)

/** view: 'upcoming' (scheduled, still ahead) or 'history' (past, completed or cancelled). */
export async function listAppointments({ profileId, view = 'upcoming' } = {}, signal) {
  const { data } = await apiClient.get(base(profileId), { params: { view }, signal })
  return data
}

export async function getAppointment(appointmentId, { profileId } = {}, signal) {
  const { data } = await apiClient.get(`${base(profileId)}/${id(appointmentId)}`, { signal })
  return data
}

export async function createAppointment(payload) {
  const { data } = await apiClient.post('/api/appointments', payload)
  return data
}

export async function updateAppointment(appointmentId, payload) {
  const { data } = await apiClient.put(`/api/appointments/${id(appointmentId)}`, payload)
  return data
}

export async function cancelAppointment(appointmentId) {
  const { data } = await apiClient.post(`/api/appointments/${id(appointmentId)}/cancel`)
  return data
}

export async function completeAppointment(appointmentId) {
  const { data } = await apiClient.post(`/api/appointments/${id(appointmentId)}/complete`)
  return data
}
