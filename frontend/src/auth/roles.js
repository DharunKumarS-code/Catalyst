// Role values must match the backend `Role` enum. The frontend uses roles only for
// display and navigation; the backend enforces access from the verified token.
export const ROLES = Object.freeze({
  ELDERLY: 'elderly',
  CARETAKER: 'caretaker',
  FAMILY_MEMBER: 'family_member',
})

export const ROLE_OPTIONS = [
  { value: ROLES.ELDERLY, label: 'Elderly individual', description: 'I am receiving care and support.' },
  { value: ROLES.CARETAKER, label: 'Caretaker', description: 'I provide care professionally or as a helper.' },
  { value: ROLES.FAMILY_MEMBER, label: 'Family member', description: 'I want to stay informed about a loved one.' },
]

export const ROLE_LABELS = Object.freeze({
  [ROLES.ELDERLY]: 'Elderly individual',
  [ROLES.CARETAKER]: 'Caretaker',
  [ROLES.FAMILY_MEMBER]: 'Family member',
})

// Backend portal area each role may access (GET /api/portal/{area}).
export const ROLE_PORTAL = Object.freeze({
  [ROLES.ELDERLY]: 'elderly',
  [ROLES.CARETAKER]: 'caretaker',
  [ROLES.FAMILY_MEMBER]: 'family',
})
