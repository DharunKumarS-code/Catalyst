import { apiClient } from './client'

// Owner calls use /api/...; caretaker/family calls pass `profileId` and use the read-only
// /api/linked-profiles/{id}/... endpoints. The server authorizes every request.
const base = (profileId) => (profileId ? `/api/linked-profiles/${encodeURIComponent(profileId)}` : '/api')
const id = (value) => encodeURIComponent(value)

export async function listMedications({ profileId, status } = {}, signal) {
  const { data } = await apiClient.get(`${base(profileId)}/medications`, { params: status ? { status } : {}, signal })
  return data
}

export async function getMedication(medicationId, { profileId } = {}, signal) {
  const { data } = await apiClient.get(`${base(profileId)}/medications/${id(medicationId)}`, { signal })
  return data
}

export async function createMedication(payload) {
  const { data } = await apiClient.post('/api/medications', payload)
  return data
}

export async function updateMedication(medicationId, payload) {
  const { data } = await apiClient.put(`/api/medications/${id(medicationId)}`, payload)
  return data
}

export async function discontinueMedication(medicationId) {
  const { data } = await apiClient.post(`/api/medications/${id(medicationId)}/discontinue`)
  return data
}

export async function deleteMedication(medicationId) {
  await apiClient.delete(`/api/medications/${id(medicationId)}`)
}

/** Today's doses, adherence and all medications in one request: `{ today, adherence, medications }`. */
export async function getMedicationOverview({ profileId } = {}, signal) {
  const { data } = await apiClient.get(`${base(profileId)}/medications/overview`, { signal })
  return data
}

export async function getTodaySchedule({ profileId } = {}, signal) {
  const { data } = await apiClient.get(`${base(profileId)}/doses/today`, { signal })
  return data
}

export async function getDoseHistory({ profileId, days = 7, medicationId } = {}, signal) {
  const params = { days }
  if (medicationId) params.medication_id = medicationId
  const { data } = await apiClient.get(`${base(profileId)}/doses/history`, { params, signal })
  return data
}

/** `expectedStatus` is the status currently shown; the server rejects stale or repeated updates (409). */
/** Records a dose. With `profileId`, a caretaker records it for a linked person (needs their permission). */
export async function setDoseStatus(doseId, status, expectedStatus, { profileId } = {}) {
  const base = profileId ? `/api/linked-profiles/${id(profileId)}/doses` : '/api/doses'
  const { data } = await apiClient.patch(`${base}/${id(doseId)}/status`, {
    status,
    expected_status: expectedStatus,
  })
  return data
}

export async function getAdherence({ profileId, medicationId } = {}, signal) {
  const params = medicationId ? { medication_id: medicationId } : {}
  const { data } = await apiClient.get(`${base(profileId)}/adherence`, { params, signal })
  return data
}
