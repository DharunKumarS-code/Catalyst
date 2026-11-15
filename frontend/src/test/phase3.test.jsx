import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as linkingApi from '../api/linking'
import * as profileApi from '../api/profile'
import { setToken } from '../auth/tokenStorage'
import AuthProvider from '../context/AuthProvider'

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchDemoAccounts: vi.fn(async () => []),
}))
vi.mock('../api/portal', () => ({ fetchPortal: vi.fn(async (area) => ({ area, message: 'ok' })) }))
vi.mock('../api/health', () => ({ fetchHealth: vi.fn(() => new Promise(() => {})) }))
vi.mock('../api/profile', () => ({
  getMyProfile: vi.fn(),
  createMyProfile: vi.fn(),
  updateMyProfile: vi.fn(),
}))
vi.mock('../api/linking', () => ({
  createInvitation: vi.fn(),
  listInvitations: vi.fn(async () => []),
  cancelInvitation: vi.fn(async () => {}),
  listConnections: vi.fn(async () => []),
  revokeConnection: vi.fn(async () => {}),
  redeemInvitation: vi.fn(),
  listLinkedProfiles: vi.fn(async () => []),
  getLinkedProfile: vi.fn(),
}))

const USERS = {
  elderly: { id: 'e1', name: 'Margaret Smith', email: 'margaret@example.org', role: 'elderly', is_demo: false, created_at: '2026-11-01T00:00:00+00:00' },
  caretaker: { id: 'c1', name: 'Carl Carer', email: 'carl@example.org', role: 'caretaker', is_demo: false, created_at: '2026-11-01T00:00:00+00:00' },
}
const PROFILE = {
  id: 'p1',
  full_name: 'Margaret Smith',
  date_of_birth: '1941-03-12',
  phone: null,
  address: '12 Garden Lane',
  emergency_contact_name: 'Tom Smith',
  emergency_contact_phone: '07700 900123',
  notes: null,
  created_at: '2026-11-01T00:00:00+00:00',
  updated_at: '2026-11-01T00:00:00+00:00',
}
const apiError = (status, detail) => Object.assign(new Error('Request failed'), { response: { status, data: { detail } } })

function fakeToken() {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64({ exp: Math.floor(Date.now() / 1000) + 1800 })}.sig`
}

function renderAs(user, path) {
  setToken(fakeToken())
  authApi.fetchCurrentUser.mockResolvedValue(user)
  const ue = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
  return ue
}

beforeEach(() => {
  vi.clearAllMocks()
  profileApi.getMyProfile.mockResolvedValue(null)
  linkingApi.listInvitations.mockResolvedValue([])
  linkingApi.listConnections.mockResolvedValue([])
  linkingApi.listLinkedProfiles.mockResolvedValue([])
})

describe('elderly profile', () => {
  it('prompts to set up a missing profile', async () => {
    const user = renderAs(USERS.elderly, '/profile')
    await user.click(await screen.findByRole('link', { name: 'Set up my profile' }))
    expect(await screen.findByRole('heading', { name: 'Set up your profile' })).toBeTruthy()
  })

  it('validates required fields before saving', async () => {
    const user = renderAs(USERS.elderly, '/profile/setup')
    await user.click(await screen.findByRole('button', { name: 'Create my profile' }))
    expect(screen.getByText('Enter your full name.')).toBeTruthy()
    expect(screen.getByText('Enter an emergency contact name.')).toBeTruthy()
    expect(screen.getByText('Enter an emergency contact phone number.')).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByLabelText('Full name'))
    expect(screen.getByLabelText('Full name').getAttribute('aria-invalid')).toBe('true')
    expect(profileApi.createMyProfile).not.toHaveBeenCalled()
  })

  it('rejects an invalid phone number', async () => {
    const user = renderAs(USERS.elderly, '/profile/setup')
    await user.type(await screen.findByLabelText('Full name'), 'Margaret Smith')
    await user.type(screen.getByLabelText('Contact name'), 'Tom')
    await user.type(screen.getByLabelText('Contact phone number'), '123')
    await user.click(screen.getByRole('button', { name: 'Create my profile' }))
    expect(screen.getByText('Enter a valid phone number with 7 to 15 digits.')).toBeTruthy()
    expect(profileApi.createMyProfile).not.toHaveBeenCalled()
  })

  it('creates the profile and shows it with a success message', async () => {
    profileApi.createMyProfile.mockResolvedValue(PROFILE)
    const user = renderAs(USERS.elderly, '/profile/setup')
    await user.type(await screen.findByLabelText('Full name'), ' Margaret Smith ')
    await user.type(screen.getByLabelText('Contact name'), 'Tom Smith')
    await user.type(screen.getByLabelText('Contact phone number'), '07700 900123')
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    await user.click(screen.getByRole('button', { name: 'Create my profile' }))

    expect(profileApi.createMyProfile).toHaveBeenCalledWith({
      full_name: 'Margaret Smith',
      date_of_birth: null,
      phone: null,
      address: null,
      emergency_contact_name: 'Tom Smith',
      emergency_contact_phone: '07700 900123',
      notes: null,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
    expect(await screen.findByRole('heading', { name: 'My profile' })).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Your profile has been created.')
    expect(screen.getByText('Tom Smith')).toBeTruthy()
  })

  it('edits an existing profile and maps server field errors', async () => {
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    profileApi.updateMyProfile.mockRejectedValueOnce(
      Object.assign(new Error('422'), {
        response: { status: 422, data: { detail: [{ loc: ['body', 'address'], msg: 'String should have at most 300 characters' }] } },
      }),
    )
    const user = renderAs(USERS.elderly, '/profile/edit')
    const name = await screen.findByLabelText('Full name')
    expect(name.value).toBe('Margaret Smith')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('String should have at most 300 characters')).toBeTruthy()
    expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1)
  })

  it('blocks caretakers from the profile pages', async () => {
    renderAs(USERS.caretaker, '/profile')
    expect(await screen.findByRole('heading', { name: 'Access restricted' })).toBeTruthy()
    expect(profileApi.getMyProfile).not.toHaveBeenCalled()
  })

  it('warns demo users to enter made-up details', async () => {
    renderAs({ ...USERS.elderly, is_demo: true }, '/profile/setup')
    expect((await screen.findByRole('note')).textContent).toContain('made-up details')
  })
})

describe('connections (elderly)', () => {
  it('asks for a profile before allowing invitations', async () => {
    renderAs(USERS.elderly, '/connections')
    expect(await screen.findByRole('heading', { name: 'Create your profile first' })).toBeTruthy()
    expect(linkingApi.listInvitations).not.toHaveBeenCalled()
  })

  it('creates an invitation and shows the one-time code', async () => {
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    linkingApi.createInvitation.mockResolvedValue({
      id: 'i1', role: 'caretaker', status: 'pending', code: 'ABCD-EFGH-JKMN-PQRS',
      expires_at: '2026-11-18T10:00:00+00:00', created_at: '2026-11-15T10:00:00+00:00',
    })
    const user = renderAs(USERS.elderly, '/connections')
    await user.click(await screen.findByRole('radio', { name: /A caretaker/ }))
    await user.click(screen.getByRole('button', { name: 'Create invitation code' }))

    expect(linkingApi.createInvitation).toHaveBeenCalledWith('caretaker')
    const code = await screen.findByTestId('invitation-code')
    expect(code.textContent).toBe('ABCD-EFGH-JKMN-PQRS')
    await waitFor(() => expect(document.activeElement).toBe(code))
    expect(screen.getByText(/will not be shown again/)).toBeTruthy()
    await waitFor(() => expect(linkingApi.listInvitations).toHaveBeenCalledTimes(2)) // list refreshed
  })

  it('shows invitation errors from the server', async () => {
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    linkingApi.createInvitation.mockRejectedValue(apiError(429, 'You already have 10 open invitations. Cancel one before creating another.'))
    const user = renderAs(USERS.elderly, '/connections')
    await user.click(await screen.findByRole('button', { name: 'Create invitation code' }))
    expect((await screen.findByRole('alert')).textContent).toContain('10 open invitations')
  })

  it('removes a connection only after confirmation', async () => {
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    linkingApi.listConnections.mockResolvedValue([
      { id: 'r1', role: 'caretaker', member: { id: 'c1', name: 'Carl Carer', email: 'carl@example.org', role: 'caretaker' }, connected_at: '2026-11-10T00:00:00+00:00' },
    ])
    const user = renderAs(USERS.elderly, '/connections')
    await user.click(await screen.findByRole('button', { name: 'Remove access for Carl Carer' }))
    expect(linkingApi.revokeConnection).not.toHaveBeenCalled()
    const confirm = screen.getByRole('group', { name: 'Confirm removing Carl Carer' })
    linkingApi.listConnections.mockResolvedValue([])
    await user.click(within(confirm).getByRole('button', { name: 'Yes, remove access' }))

    expect(linkingApi.revokeConnection).toHaveBeenCalledWith('r1')
    expect((await screen.findByText('Carl Carer can no longer see your profile.'))).toBeTruthy()
  })

  it('can back out of removing a connection', async () => {
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    linkingApi.listConnections.mockResolvedValue([
      { id: 'r1', role: 'family_member', member: { id: 'f1', name: 'Fay Family', email: 'fay@example.org', role: 'family_member' }, connected_at: '2026-11-10T00:00:00+00:00' },
    ])
    const user = renderAs(USERS.elderly, '/connections')
    await user.click(await screen.findByRole('button', { name: 'Remove access for Fay Family' }))
    await user.click(screen.getByRole('button', { name: 'Keep connected' }))
    expect(screen.queryByRole('group', { name: /Confirm removing/ })).toBeNull()
    expect(linkingApi.revokeConnection).not.toHaveBeenCalled()
  })

  it('cancels a pending invitation', async () => {
    profileApi.getMyProfile.mockResolvedValue(PROFILE)
    linkingApi.listInvitations.mockResolvedValue([
      { id: 'i9', role: 'family_member', status: 'pending', expires_at: '2026-11-18T10:00:00+00:00', created_at: '2026-11-15T10:00:00+00:00' },
      { id: 'i8', role: 'caretaker', status: 'redeemed', expires_at: '2026-11-18T10:00:00+00:00', created_at: '2026-11-14T10:00:00+00:00' },
    ])
    const user = renderAs(USERS.elderly, '/connections')
    const buttons = await screen.findAllByRole('button', { name: /^Cancel family member invitation/ })
    expect(buttons).toHaveLength(1) // only pending invitations can be cancelled
    expect(screen.getByText('Used')).toBeTruthy()
    await user.click(buttons[0])
    expect(linkingApi.cancelInvitation).toHaveBeenCalledWith('i9')
    expect(await screen.findByText(/has been cancelled/)).toBeTruthy()
  })
})

describe('redeeming an invitation (caretaker / family)', () => {
  it('validates the code format locally', async () => {
    const user = renderAs(USERS.caretaker, '/join')
    await user.type(await screen.findByLabelText('Invitation code'), 'abc')
    await user.click(screen.getByRole('button', { name: 'Connect' }))
    expect(screen.getByText(/Invitation codes have 16 letters and numbers/)).toBeTruthy()
    expect(linkingApi.redeemInvitation).not.toHaveBeenCalled()
  })

  it('connects and links to the profile', async () => {
    linkingApi.redeemInvitation.mockResolvedValue({
      message: 'You are now connected to Margaret Smith.',
      linked: { relationship_id: 'r1', profile_id: 'p1', full_name: 'Margaret Smith', role: 'caretaker', connected_at: '2026-11-15T10:00:00+00:00' },
    })
    const user = renderAs(USERS.caretaker, '/join')
    await user.type(await screen.findByLabelText('Invitation code'), 'abcd efgh jkmn pqrs')
    await user.click(screen.getByRole('button', { name: 'Connect' }))

    expect(linkingApi.redeemInvitation).toHaveBeenCalledWith('ABCD EFGH JKMN PQRS')
    const status = await screen.findByRole('status')
    expect(status.textContent).toContain('You are now connected to Margaret Smith.')
    expect(within(status).getByRole('link', { name: 'View Margaret Smith’s profile' }).getAttribute('href')).toBe('/linked/p1')
  })

  it.each([
    [410, 'This invitation has expired. Please ask for a new invitation.'],
    [409, 'This invitation has already been used. Please ask for a new invitation.'],
    [403, 'This invitation is for a family member, but you are signed in as a caretaker.'],
    [429, 'Too many unsuccessful attempts. Please wait 15 minutes and try again.'],
  ])('shows the server message for HTTP %i', async (status, detail) => {
    linkingApi.redeemInvitation.mockRejectedValue(apiError(status, detail))
    const user = renderAs(USERS.caretaker, '/join')
    await user.type(await screen.findByLabelText('Invitation code'), 'ABCD-EFGH-JKMN-PQRS')
    await user.click(screen.getByRole('button', { name: 'Connect' }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain(detail)
    await waitFor(() => expect(document.activeElement).toBe(alert))
  })

  it('is not available to elderly users', async () => {
    renderAs(USERS.elderly, '/join')
    expect(await screen.findByRole('heading', { name: 'Access restricted' })).toBeTruthy()
  })
})

describe('linked profiles (caretaker / family)', () => {
  it('lists linked profiles', async () => {
    linkingApi.listLinkedProfiles.mockResolvedValue([
      { relationship_id: 'r1', profile_id: 'p1', full_name: 'Margaret Smith', role: 'caretaker', connected_at: '2026-11-10T00:00:00+00:00' },
    ])
    renderAs(USERS.caretaker, '/linked')
    expect(await screen.findByRole('heading', { name: 'Margaret Smith' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'View Margaret Smith’s profile' }).getAttribute('href')).toBe('/linked/p1')
  })

  it('shows an empty state with guidance', async () => {
    renderAs(USERS.caretaker, '/linked')
    expect(await screen.findByText('You are not connected to anyone yet.')).toBeTruthy()
  })

  it('shows profile details when authorized', async () => {
    linkingApi.getLinkedProfile.mockResolvedValue({ relationship_id: 'r1', role: 'caretaker', connected_at: '2026-11-10T00:00:00+00:00', profile: PROFILE })
    renderAs(USERS.caretaker, '/linked/p1')
    expect(await screen.findByRole('heading', { name: 'Margaret Smith' })).toBeTruthy()
    expect(linkingApi.getLinkedProfile).toHaveBeenCalledWith('p1', expect.anything())
    expect(screen.getByRole('link', { name: '07700 900123' }).getAttribute('href')).toBe('tel:07700900123')
  })

  it('explains when access has been removed', async () => {
    linkingApi.getLinkedProfile.mockRejectedValue(apiError(404, 'Profile not found or you no longer have access to it.'))
    renderAs(USERS.caretaker, '/linked/p1')
    expect((await screen.findByRole('alert')).textContent).toContain('your access may have been removed')
  })
})
