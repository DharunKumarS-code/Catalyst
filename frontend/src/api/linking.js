import { apiClient } from './client'

// ---- Elderly: invitations and connections ----

/** POST /api/invitations -> includes the one-time `code`. */
export async function createInvitation(role) {
  const { data } = await apiClient.post('/api/invitations', { role })
  return data
}

export async function listInvitations(signal) {
  const { data } = await apiClient.get('/api/invitations', { signal })
  return data
}

export async function cancelInvitation(id) {
  await apiClient.delete(`/api/invitations/${encodeURIComponent(id)}`)
}

export async function listConnections(signal) {
  const { data } = await apiClient.get('/api/relationships', { signal })
  return data
}

export async function revokeConnection(id) {
  await apiClient.delete(`/api/relationships/${encodeURIComponent(id)}`)
}

// ---- Caretakers / family members ----

/** POST /api/invitations/redeem -> { message, linked } */
export async function redeemInvitation(code) {
  const { data } = await apiClient.post('/api/invitations/redeem', { code })
  return data
}

export async function listLinkedProfiles(signal) {
  const { data } = await apiClient.get('/api/linked-profiles', { signal })
  return data
}

export async function getLinkedProfile(profileId, signal) {
  const { data } = await apiClient.get(`/api/linked-profiles/${encodeURIComponent(profileId)}`, { signal })
  return data
}
