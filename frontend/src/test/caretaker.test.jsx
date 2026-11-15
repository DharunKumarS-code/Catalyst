import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as careApi from '../api/care'
import * as linkingApi from '../api/linking'
import * as medApi from '../api/medications'
import { setToken } from '../auth/tokenStorage'
import ConnectionList from '../components/linking/ConnectionList'
import AuthProvider from '../context/AuthProvider'

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(), registerUser: vi.fn(), fetchCurrentUser: vi.fn(), fetchDemoAccounts: vi.fn(async () => []),
}))
vi.mock('../api/portal', () => ({ fetchPortal: vi.fn(async (area) => ({ area, message: 'ok' })) }))
vi.mock('../api/health', () => ({ fetchHealth: vi.fn(() => new Promise(() => {})) }))
vi.mock('../api/care', () => ({ getCareDashboard: vi.fn() }))
vi.mock('../api/medications', () => ({ setDoseStatus: vi.fn() }))
vi.mock('../api/linking', () => ({ revokeConnection: vi.fn(), setDosePermission: vi.fn() }))
vi.mock('../api/notifications', async (orig) => ({ ...(await orig()), getUnreadCount: vi.fn(async () => ({ unread: 0 })) }))

const at = '2026-11-16T12:00:00+00:00'
const CARER = { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker', is_demo: false, created_at: at }
const dose = (over) => ({
  id: 'd1', medication_id: 'm1', medication_name: 'Metformin', dosage: '500 mg', scheduled_at: at, local_date: '2026-11-16',
  local_time: '08:00', status: 'pending', status_changed_at: null, taken_at: null, is_due: true,
  can_mark_taken: false, can_mark_missed: false, recorded_by_name: null, recorded_by_role: null, ...over,
})
const card = (over) => ({
  profile_id: 'p1', relationship_id: 'r1', role: 'caretaker', connected_at: at, can_record_doses: false,
  full_name: 'Alice Adams', date_of_birth: null, phone: null, emergency_contact_name: 'Tom', emergency_contact_phone: '07700 900123',
  timezone: 'Europe/London', local_date: '2026-11-16', is_demo: false, active_medications: 1,
  today: { start_date: '2026-11-16', end_date: '2026-11-16', total: 1, taken: 0, missed: 0, pending: 1, adherence_percent: 0 },
  today_doses: [dose()], next_dose: null, upcoming_appointments: [], upcoming_appointment_count: 0, recent_activity: [], ...over,
})

function fakeToken() {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64({ exp: Math.floor(Date.now() / 1000) + 1800 })}.sig`
}

function renderCare() {
  setToken(fakeToken())
  authApi.fetchCurrentUser.mockResolvedValue(CARER)
  const user = userEvent.setup()
  render(<MemoryRouter initialEntries={['/care']}><AuthProvider><App /></AuthProvider></MemoryRouter>)
  return user
}

beforeEach(() => vi.clearAllMocks())

describe('caretaker dose recording on the care dashboard', () => {
  it('is view-only without permission', async () => {
    careApi.getCareDashboard.mockResolvedValue({ generated_at: at, profiles: [card()] })
    renderCare()
    expect(await screen.findByText(/You can view only/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /as taken/ })).toBeNull()
  })

  it('records a dose through the linked-profile endpoint when permitted', async () => {
    careApi.getCareDashboard.mockResolvedValue({
      generated_at: at,
      profiles: [card({ can_record_doses: true, today_doses: [dose({ can_mark_taken: true, can_mark_missed: true })] })],
    })
    medApi.setDoseStatus.mockResolvedValue(dose({ status: 'taken', recorded_by_name: 'Carl Carer', recorded_by_role: 'caretaker' }))
    const user = renderCare()
    expect(await screen.findByText(/has allowed you to record doses/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Mark Metformin at 8:00 AM as taken' }))
    expect(medApi.setDoseStatus).toHaveBeenCalledWith('d1', 'taken', 'pending', { profileId: 'p1' })
    expect(await screen.findByText(/recorded as taken/)).toBeTruthy()
    await waitFor(() => expect(careApi.getCareDashboard).toHaveBeenCalledTimes(2)) // refreshed after recording
  })

  it('shows who recorded a dose', async () => {
    careApi.getCareDashboard.mockResolvedValue({
      generated_at: at,
      profiles: [card({ today_doses: [dose({ status: 'taken', recorded_by_name: 'Carl Carer', recorded_by_role: 'caretaker' })] })],
    })
    renderCare()
    expect((await screen.findByTestId('recorded-by')).textContent).toBe('Recorded by Carl Carer (caretaker)')
  })
})

describe('elderly user controls the permission', () => {
  const conn = (over) => ({
    id: 'r1', role: 'caretaker', connected_at: at, can_record_doses: false,
    member: { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker' }, ...over,
  })

  it('offers the permission for caretakers only, and toggles it', async () => {
    const onChanged = vi.fn()
    linkingApi.setDosePermission.mockResolvedValue(conn({ can_record_doses: true }))
    const family = conn({ id: 'r2', role: 'family_member', member: { id: 'f1', name: 'Fay Family', email: 'f@example.org', role: 'family_member' } })
    const user = userEvent.setup()
    render(<MemoryRouter><ConnectionList connections={[conn(), family]} onChanged={onChanged} /></MemoryRouter>)

    const items = screen.getAllByRole('listitem')
    expect(within(items[1]).queryByRole('button', { name: /recording doses/ })).toBeNull()
    await user.click(within(items[0]).getByRole('button', { name: 'Allow recording doses' }))
    expect(linkingApi.setDosePermission).toHaveBeenCalledWith('r1', true)
    expect(await screen.findByText('Carl Carer can now record doses they give you.')).toBeTruthy()
    expect(onChanged).toHaveBeenCalled()
  })
})
