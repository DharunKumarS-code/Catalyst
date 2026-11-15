import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as careApi from '../api/care'
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
vi.mock('../api/care', () => ({ getCareDashboard: vi.fn() }))
vi.mock('../api/medications', () => ({ setDoseStatus: vi.fn() }))

const at = '2026-11-16T12:00:00+00:00'
const USERS = {
  caretaker: { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker', is_demo: false, created_at: at },
  family: { id: 'f1', name: 'Fay Family', email: 'f@example.org', role: 'family_member', is_demo: false, created_at: at },
  elderly: { id: 'e1', name: 'Margaret', email: 'm@example.org', role: 'elderly', is_demo: false, created_at: at },
}
const dose = (over) => ({
  id: 'd1', medication_id: 'm1', medication_name: 'Metformin', dosage: '500 mg', scheduled_at: at, local_date: '2026-11-16',
  local_time: '08:00', status: 'taken', status_changed_at: at, taken_at: at, is_due: true, can_mark_taken: false, can_mark_missed: false, ...over,
})
const period = (over) => ({ start_date: '2026-11-16', end_date: '2026-11-16', total: 2, taken: 1, missed: 1, pending: 0, adherence_percent: 50, ...over })
const profile = (over) => ({
  profile_id: 'p1', relationship_id: 'r1', role: 'caretaker', connected_at: at, full_name: 'Alice Adams', date_of_birth: '1940-01-02',
  phone: null, emergency_contact_name: 'Tom', emergency_contact_phone: '07700 900123', timezone: 'Europe/London',
  local_date: '2026-11-16', is_demo: false, active_medications: 2, today: period(),
  today_doses: [dose(), dose({ id: 'd2', local_time: '09:00', medication_name: 'Aspirin', status: 'missed' }),
    dose({ id: 'd3', local_time: '20:00', status: 'pending', is_due: false })],
  next_dose: dose({ id: 'd3', local_time: '20:00', status: 'pending', is_due: false }),
  upcoming_appointments: [{
    id: 'a1', doctor_name: 'Dr. Shah', specialization: null, clinic_name: 'Heart Clinic', clinic_address: null,
    appointment_date: '2026-11-20', appointment_time: '10:30', timezone: 'Europe/London', scheduled_at: at,
    appointment_type: null, reason: null, notes: null, status: 'scheduled', status_changed_at: null, is_past: false,
    is_demo: false, can_edit: false, can_cancel: false, can_complete: false, created_at: at, updated_at: at,
  }],
  upcoming_appointment_count: 1,
  recent_activity: [
    { kind: 'dose_taken', at, subject: 'Metformin 500 mg', local_date: '2026-11-16', local_time: '08:00', place: null },
    { kind: 'appointment_cancelled', at, subject: 'Dr. Lee', local_date: '2026-11-17', local_time: '09:00', place: 'Eye Clinic' },
  ],
  ...over,
})
const apiError = (status, detail) => Object.assign(new Error('Request failed'), { response: { status, data: { detail } } })

function fakeToken() {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64({ exp: Math.floor(Date.now() / 1000) + 1800 })}.sig`
}

function renderAs(user, path = '/care') {
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
  careApi.getCareDashboard.mockResolvedValue({
    generated_at: at,
    profiles: [
      profile(),
      profile({
        profile_id: 'p2', full_name: 'Bob Brown', today: period({ total: 0, taken: 0, missed: 0, adherence_percent: null }),
        today_doses: [], next_dose: null, upcoming_appointments: [], upcoming_appointment_count: 0, recent_activity: [],
        active_medications: 0,
      }),
    ],
  })
})

describe('care dashboard', () => {
  it('summarises every linked person with real counts', async () => {
    renderAs(USERS.caretaker)
    const cards = await screen.findAllByTestId('profile-card')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByTestId('card-adherence').textContent).toBe('50%')
    expect(within(cards[0]).getByText(/Metformin 500 mg at/)).toBeTruthy()
    expect(within(cards[0]).getByText(/Dr. Shah/)).toBeTruthy()
    expect(within(cards[1]).getByTestId('card-adherence').textContent).toBe('No doses due')
    expect(within(cards[1]).getByText('none left today')).toBeTruthy()
    expect(within(cards[1]).getByText('none scheduled')).toBeTruthy()
  })

  it('shows the selected person read-only, with activity and appointments', async () => {
    renderAs(USERS.caretaker)
    const detail = await screen.findByTestId('profile-detail')
    expect(within(detail).getByRole('heading', { name: 'Alice Adams' })).toBeTruthy()
    expect(within(detail).getAllByTestId('dose-row')).toHaveLength(3)
    expect(within(detail).queryByRole('button', { name: /taken|missed/i })).toBeNull()
    expect(within(detail).getAllByTestId('activity-item').map((li) => li.textContent).join(' ')).toMatch(/Took Metformin 500 mg.*was cancelled/)
    expect(within(detail).getByRole('link', { name: /Dr. Shah/ }).getAttribute('href')).toBe('/linked/p1/appointments/a1')
  })

  it('switches between people', async () => {
    const user = renderAs(USERS.family)
    const cards = await screen.findAllByTestId('profile-card')
    expect(cards[0].getAttribute('aria-pressed')).toBe('true')
    await user.click(cards[1])
    const detail = screen.getByTestId('profile-detail')
    expect(within(detail).getByRole('heading', { name: 'Bob Brown' })).toBeTruthy()
    expect(within(detail).getByText('No medicines have been added yet.')).toBeTruthy()
    expect(within(detail).getByText('Nothing has been recorded in the last 7 days.')).toBeTruthy()
    expect(screen.getAllByTestId('profile-card')[1].getAttribute('aria-pressed')).toBe('true')
  })

  it('shows an empty state when no one is connected', async () => {
    careApi.getCareDashboard.mockResolvedValue({ generated_at: at, profiles: [] })
    renderAs(USERS.caretaker)
    expect(await screen.findByRole('heading', { name: 'No one is connected yet' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Enter an invitation code' }).getAttribute('href')).toBe('/join')
  })

  it('handles API failures and can retry', async () => {
    careApi.getCareDashboard.mockRejectedValueOnce(apiError(503, 'Database is not available.'))
    const user = renderAs(USERS.caretaker)
    expect((await screen.findByRole('alert')).textContent).toContain('Database is not available.')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getAllByTestId('profile-card')).toHaveLength(2))
  })

  it('is not available to elderly users', async () => {
    renderAs(USERS.elderly)
    expect(await screen.findByText(/Access restricted/)).toBeTruthy()
    expect(careApi.getCareDashboard).not.toHaveBeenCalled()
  })
})
