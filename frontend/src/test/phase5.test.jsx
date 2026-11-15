import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as apptApi from '../api/appointments'
import * as authApi from '../api/auth'
import * as linkingApi from '../api/linking'
import { toAppointmentPayload, validateAppointment } from '../appointments/validation'
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
vi.mock('../api/profile', () => ({ getMyProfile: vi.fn(async () => null), createMyProfile: vi.fn(), updateMyProfile: vi.fn() }))
vi.mock('../api/linking', () => ({
  createInvitation: vi.fn(),
  listInvitations: vi.fn(async () => []),
  cancelInvitation: vi.fn(),
  listConnections: vi.fn(async () => []),
  revokeConnection: vi.fn(),
  redeemInvitation: vi.fn(),
  listLinkedProfiles: vi.fn(async () => []),
  getLinkedProfile: vi.fn(),
}))
vi.mock('../api/appointments', () => ({
  listAppointments: vi.fn(),
  getAppointment: vi.fn(),
  createAppointment: vi.fn(),
  updateAppointment: vi.fn(),
  cancelAppointment: vi.fn(),
  completeAppointment: vi.fn(),
}))

const at = '2026-11-01T00:00:00+00:00'
const USERS = {
  elderly: { id: 'e1', name: 'Margaret Smith', email: 'm@example.org', role: 'elderly', is_demo: false, created_at: at },
  caretaker: { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker', is_demo: false, created_at: at },
}
const appt = (over) => ({
  id: 'a1',
  doctor_name: 'Dr. Priya Shah',
  specialization: 'Cardiology',
  clinic_name: 'City Heart Clinic',
  clinic_address: null,
  appointment_date: '2030-11-20',
  appointment_time: '10:30',
  timezone: 'Europe/London',
  scheduled_at: '2030-11-20T10:30:00+00:00',
  appointment_type: 'Check-up',
  reason: null,
  notes: null,
  status: 'scheduled',
  status_changed_at: null,
  is_past: false,
  is_demo: false,
  can_edit: true,
  can_cancel: true,
  can_complete: false,
  created_at: at,
  updated_at: at,
  ...over,
})
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
  apptApi.listAppointments.mockImplementation(async ({ view }) =>
    view === 'upcoming'
      ? [appt()]
      : [appt({ id: 'a2', doctor_name: 'Dr. Old Visit', status: 'completed', is_past: true, can_edit: false, can_cancel: false })],
  )
  apptApi.getAppointment.mockResolvedValue(appt())
})

describe('appointment validation', () => {
  const valid = {
    doctor_name: 'Dr. Lee', specialization: '', clinic_name: 'Clinic', clinic_address: '', appointment_date: '2030-01-05',
    appointment_time: '09:15', appointment_type: '', reason: '', notes: '',
  }
  it('accepts a valid form and nulls empty optional fields', () => {
    expect(validateAppointment(valid)).toEqual({})
    expect(toAppointmentPayload({ ...valid, notes: '  ' })).toMatchObject({ doctor_name: 'Dr. Lee', notes: null, specialization: null })
  })
  it('rejects missing required fields and past or invalid dates', () => {
    const e = validateAppointment({ ...valid, doctor_name: ' ', clinic_name: '', appointment_date: '2001-01-01', appointment_time: '' })
    expect(Object.keys(e).sort()).toEqual(['appointment_date', 'appointment_time', 'clinic_name', 'doctor_name'])
    expect(validateAppointment({ ...valid, appointment_date: 'garbage' }).appointment_date).toBeTruthy()
  })
})

describe('elderly appointments', () => {
  it('shows upcoming and past appointments with text status labels', async () => {
    renderAs(USERS.elderly, '/appointments')
    const rows = await screen.findAllByTestId('appointment-row')
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByTestId('appointment-status').textContent).toContain('Scheduled')
    expect(within(rows[1]).getByTestId('appointment-status').textContent).toContain('Completed')
    expect(screen.getByRole('heading', { name: 'Upcoming appointments' })).toBeTruthy()
  })

  it('creates an appointment and shows it', async () => {
    apptApi.createAppointment.mockResolvedValue(appt())
    const user = renderAs(USERS.elderly, '/appointments/new')
    await user.type(await screen.findByLabelText('Doctor’s name'), 'Dr. Priya Shah')
    await user.type(screen.getByLabelText('Hospital or clinic name'), 'City Heart Clinic')
    await user.type(screen.getByLabelText('Date'), '2030-11-20')
    await user.type(screen.getByLabelText('Time'), '10:30')
    await user.click(screen.getByRole('button', { name: 'Add appointment' }))
    expect(apptApi.createAppointment).toHaveBeenCalledWith(
      expect.objectContaining({ doctor_name: 'Dr. Priya Shah', clinic_name: 'City Heart Clinic', appointment_date: '2030-11-20', appointment_time: '10:30', reason: null }),
    )
    expect(await screen.findByText(/Appointment added/)).toBeTruthy()
  })

  it('does not submit an incomplete form', async () => {
    const user = renderAs(USERS.elderly, '/appointments/new')
    await user.click(await screen.findByRole('button', { name: 'Add appointment' }))
    expect(screen.getByText('Enter the doctor’s name.')).toBeTruthy()
    expect(apptApi.createAppointment).not.toHaveBeenCalled()
  })

  it('shows a server field error next to the field', async () => {
    apptApi.createAppointment.mockRejectedValue(
      apiError(422, [{ loc: ['body', 'appointment_time'], msg: 'This time does not exist on that day in your time zone.' }]),
    )
    const user = renderAs(USERS.elderly, '/appointments/new')
    await user.type(await screen.findByLabelText('Doctor’s name'), 'Dr. A')
    await user.type(screen.getByLabelText('Hospital or clinic name'), 'Clinic')
    await user.type(screen.getByLabelText('Date'), '2030-03-31')
    await user.type(screen.getByLabelText('Time'), '02:30')
    await user.click(screen.getByRole('button', { name: 'Add appointment' }))
    expect(await screen.findByText('This time does not exist on that day in your time zone.')).toBeTruthy()
  })

  it('cancels only after confirmation', async () => {
    apptApi.cancelAppointment.mockResolvedValue(appt({ status: 'cancelled' }))
    const user = renderAs(USERS.elderly, '/appointments/a1')
    await user.click(await screen.findByRole('button', { name: /Cancel appointment/ }))
    expect(apptApi.cancelAppointment).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Yes, cancel it' }))
    expect(apptApi.cancelAppointment).toHaveBeenCalledWith('a1')
    expect(await screen.findByText('The appointment was cancelled.')).toBeTruthy()
  })

  it('offers "mark completed" only for a past scheduled appointment', async () => {
    apptApi.getAppointment.mockResolvedValue(appt({ is_past: true, can_edit: false, can_complete: true }))
    apptApi.completeAppointment.mockResolvedValue(appt({ status: 'completed' }))
    const user = renderAs(USERS.elderly, '/appointments/a1')
    expect((await screen.findByTestId('appointment-status')).textContent).toContain('Needs update')
    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull()
    await user.click(screen.getByRole('button', { name: /Mark as completed/ }))
    expect(apptApi.completeAppointment).toHaveBeenCalledWith('a1')
  })
})

describe('caretaker read-only appointments', () => {
  it('lists appointments for a linked profile without actions', async () => {
    linkingApi.getLinkedProfile.mockResolvedValue({ relationship_id: 'r1', role: 'caretaker', connected_at: at, profile: { id: 'p1', full_name: 'Margaret Smith' } })
    renderAs(USERS.caretaker, '/linked/p1/appointments')
    expect(await screen.findByRole('heading', { name: "Margaret Smith's appointments" })).toBeTruthy()
    expect(await screen.findAllByTestId('appointment-row')).toHaveLength(2)
    expect(apptApi.listAppointments).toHaveBeenCalledWith({ profileId: 'p1', view: 'upcoming' }, expect.anything())
    expect(screen.queryByRole('link', { name: 'Add appointment' })).toBeNull()
  })

  it('shows no edit or cancel controls on the detail page', async () => {
    apptApi.getAppointment.mockResolvedValue(appt({ can_edit: false, can_cancel: false }))
    renderAs(USERS.caretaker, '/linked/p1/appointments/a1')
    expect(await screen.findByRole('heading', { name: /Dr. Priya Shah/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Cancel/ })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull()
    expect(apptApi.getAppointment).toHaveBeenCalledWith('a1', { profileId: 'p1' }, expect.anything())
  })

  it('shows a clear message when access is revoked', async () => {
    apptApi.getAppointment.mockRejectedValue(apiError(404, 'Profile not found or you no longer have access to it.'))
    renderAs(USERS.caretaker, '/linked/p1/appointments/a1')
    expect((await screen.findByRole('alert')).textContent).toMatch(/access may have been removed/)
  })

  it('blocks members from the owner appointment pages', async () => {
    renderAs(USERS.caretaker, '/appointments')
    expect(await screen.findByText(/Access restricted/)).toBeTruthy()
    expect(apptApi.listAppointments).not.toHaveBeenCalled()
  })
})
