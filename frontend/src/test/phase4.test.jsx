import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as linkingApi from '../api/linking'
import * as medApi from '../api/medications'
import { setToken } from '../auth/tokenStorage'
import AuthProvider from '../context/AuthProvider'
import { timesForFrequency, toMedicationPayload, validateMedication } from '../medications/validation'

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
vi.mock('../api/medications', () => {
  const api = {
  listMedications: vi.fn(),
  getMedication: vi.fn(),
  createMedication: vi.fn(),
  updateMedication: vi.fn(),
  discontinueMedication: vi.fn(),
  deleteMedication: vi.fn(),
  getTodaySchedule: vi.fn(),
  getDoseHistory: vi.fn(),
  setDoseStatus: vi.fn(),
  getAdherence: vi.fn(),
  }
  // The page now loads everything in one request; compose it from the per-part mocks so the
  // existing per-part fixtures and assertions keep working.
  api.getMedicationOverview = vi.fn(async (opts, signal) => ({
    today: await api.getTodaySchedule(opts, signal),
    adherence: await api.getAdherence(opts, signal),
    medications: await api.listMedications(opts, signal),
  }))
  return api
})

const at = '2026-11-01T00:00:00+00:00'
const USERS = {
  elderly: { id: 'e1', name: 'Margaret Smith', email: 'm@example.org', role: 'elderly', is_demo: false, created_at: at },
  caretaker: { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker', is_demo: false, created_at: at },
}
const MED = {
  id: 'm1',
  name: 'Metformin',
  dosage: '500 mg',
  frequency: 'twice_daily',
  times: ['08:00', '20:00'],
  start_date: '2026-11-16',
  end_date: null,
  instructions: 'Take with food.',
  prescribing_doctor: null,
  status: 'active',
  discontinued_at: null,
  is_demo: false,
  created_at: at,
  updated_at: at,
}
const dose = (over) => ({
  id: 'd1',
  medication_id: 'm1',
  medication_name: 'Metformin',
  dosage: '500 mg',
  scheduled_at: '2026-11-16T08:00:00+00:00',
  local_date: '2026-11-16',
  local_time: '08:00',
  status: 'pending',
  status_changed_at: null,
  taken_at: null,
  is_due: true,
  can_mark_taken: true,
  can_mark_missed: true,
  ...over,
})
const period = (over) => ({ start_date: '2026-11-16', end_date: '2026-11-16', total: 1, taken: 0, missed: 0, pending: 1, adherence_percent: 0, ...over })
const ADHERENCE = { timezone: 'UTC', today: period(), week: period({ start_date: '2026-11-10' }), days: [period()] }
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
  medApi.listMedications.mockResolvedValue([MED])
  medApi.getMedication.mockResolvedValue(MED)
  medApi.getAdherence.mockResolvedValue(ADHERENCE)
  medApi.getDoseHistory.mockResolvedValue([])
  medApi.getTodaySchedule.mockResolvedValue({
    date: '2026-11-16',
    timezone: 'Europe/London',
    doses: [dose(), dose({ id: 'd2', local_time: '20:00', is_due: false, can_mark_missed: false, can_mark_taken: false })],
  })
})

describe('medication validation', () => {
  const valid = { name: 'Aspirin', dosage: '75 mg', frequency: 'once_daily', times: ['09:00'], start_date: '2026-11-16', end_date: '', instructions: '', prescribing_doctor: '' }

  it('accepts a valid form and builds a clean payload', () => {
    expect(validateMedication(valid)).toEqual({})
    expect(toMedicationPayload({ ...valid, instructions: '  ' })).toEqual({
      name: 'Aspirin', dosage: '75 mg', frequency: 'once_daily', times: ['09:00'], start_date: '2026-11-16',
      end_date: null, instructions: null, prescribing_doctor: null,
    })
  })

  it('rejects bad names, duplicate times, and an end date before the start', () => {
    expect(validateMedication({ ...valid, name: '123' }).name).toMatch(/letter/)
    expect(validateMedication({ ...valid, frequency: 'twice_daily', times: ['09:00', '09:00'] }).times).toMatch(/different/)
    expect(validateMedication({ ...valid, end_date: '2026-11-01' }).end_date).toMatch(/before the start/)
    expect(validateMedication({ ...valid, dosage: ' ' }).dosage).toBeTruthy()
  })

  it('keeps entered times when the frequency changes', () => {
    expect(timesForFrequency('three_times_daily', ['07:30'])).toEqual(['07:30', '14:00', '20:00'])
    expect(timesForFrequency('once_daily', ['07:30', '19:00'])).toEqual(['07:30'])
  })
})

describe('elderly medication dashboard', () => {
  it("shows today's doses with text status labels and records a dose", async () => {
    medApi.setDoseStatus.mockResolvedValue(dose({ status: 'taken', can_mark_taken: false }))
    const user = renderAs(USERS.elderly, '/medications')
    const rows = await screen.findAllByTestId('dose-row')
    expect(within(rows[0]).getByTestId('dose-status').textContent).toContain('Not recorded')
    expect(within(rows[1]).getByTestId('dose-status').textContent).toContain('Upcoming')
    expect(within(rows[1]).queryByRole('button')).toBeNull() // not due yet: no controls

    await user.click(within(rows[0]).getByRole('button', { name: /as taken/ }))
    expect(medApi.setDoseStatus).toHaveBeenCalledWith('d1', 'taken', 'pending', { profileId: undefined })
    expect(await screen.findByText(/Metformin at .* recorded as taken./)).toBeTruthy()
    await waitFor(() => expect(medApi.getTodaySchedule).toHaveBeenCalledTimes(2)) // refreshed
    expect(medApi.getAdherence).toHaveBeenCalledTimes(2)
  })

  it('shows a conflict from the server instead of recording twice', async () => {
    medApi.setDoseStatus.mockRejectedValue(apiError(409, 'This dose was already updated. Refresh to see its current status.'))
    const user = renderAs(USERS.elderly, '/medications')
    const rows = await screen.findAllByTestId('dose-row')
    await user.click(within(rows[0]).getByRole('button', { name: /as missed/ }))
    expect((await screen.findByRole('alert')).textContent).toContain('already updated')
  })

  it('shows adherence and no-dose periods without dividing by zero', async () => {
    medApi.getAdherence.mockResolvedValue({ ...ADHERENCE, today: period({ total: 0, pending: 0, adherence_percent: null }) })
    renderAs(USERS.elderly, '/medications')
    expect((await screen.findByTestId('adherence-today')).textContent).toBe('No doses due')
    expect(screen.getByTestId('adherence-last-7-days').textContent).toBe('0%')
  })

  it('asks for a profile first when the server requires one', async () => {
    medApi.getTodaySchedule.mockRejectedValue(apiError(409, 'Create your profile before managing medications.'))
    renderAs(USERS.elderly, '/medications')
    expect(await screen.findByRole('link', { name: 'Set up my profile' })).toBeTruthy()
  })

  it('adds a medication with one time input per dose', async () => {
    medApi.createMedication.mockResolvedValue(MED)
    const user = renderAs(USERS.elderly, '/medications/new')
    await user.type(await screen.findByLabelText('Medication name'), 'Metformin')
    await user.type(screen.getByLabelText(/^Dosage/), '500 mg')
    await user.selectOptions(screen.getByLabelText('How often'), 'twice_daily')
    expect(screen.getByLabelText('Dose 2')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Add medication' }))
    expect(medApi.createMedication).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Metformin', dosage: '500 mg', frequency: 'twice_daily', times: ['08:00', '20:00'] }),
    )
    expect(await screen.findByText('Metformin was added to your medicines.')).toBeTruthy()
  })

  it('does not submit an invalid medication', async () => {
    const user = renderAs(USERS.elderly, '/medications/new')
    await user.click(await screen.findByRole('button', { name: 'Add medication' }))
    expect(screen.getByText('Enter the medication name.')).toBeTruthy()
    expect(medApi.createMedication).not.toHaveBeenCalled()
  })

  it('stops a medication only after confirmation', async () => {
    medApi.discontinueMedication.mockResolvedValue({ ...MED, status: 'discontinued' })
    const user = renderAs(USERS.elderly, '/medications/m1')
    await user.click(await screen.findByRole('button', { name: 'Stop taking this medicine' }))
    expect(medApi.discontinueMedication).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Yes, stop it' }))
    expect(medApi.discontinueMedication).toHaveBeenCalledWith('m1')
  })
})

describe('caretaker read-only view', () => {
  it('shows medicines without any dose or edit controls', async () => {
    linkingApi.getLinkedProfile.mockResolvedValue({
      relationship_id: 'r1', role: 'caretaker', connected_at: at, profile: { id: 'p1', full_name: 'Margaret Smith' },
    })
    medApi.getTodaySchedule.mockResolvedValue({
      date: '2026-11-16', timezone: 'UTC', doses: [dose({ can_mark_taken: false, can_mark_missed: false })],
    })
    renderAs(USERS.caretaker, '/linked/p1/medications')
    expect(await screen.findByRole('heading', { name: "Margaret Smith's medicines" })).toBeTruthy()
    const rows = await screen.findAllByTestId('dose-row')
    expect(within(rows[0]).queryByRole('button')).toBeNull()
    expect(medApi.getTodaySchedule).toHaveBeenCalledWith({ profileId: 'p1' }, expect.anything())
    expect(screen.queryByRole('link', { name: 'Add medication' })).toBeNull()
  })

  it('hides medication detail actions for members', async () => {
    renderAs(USERS.caretaker, '/linked/p1/medications/m1')
    expect(await screen.findByRole('heading', { name: /Metformin/ })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Delete/ })).toBeNull()
    expect(medApi.getMedication).toHaveBeenCalledWith('m1', { profileId: 'p1' }, expect.anything())
  })

  it('shows a clear message when access was revoked', async () => {
    linkingApi.getLinkedProfile.mockRejectedValue(apiError(404, 'Profile not found or you no longer have access to it.'))
    renderAs(USERS.caretaker, '/linked/p1/medications')
    expect((await screen.findByRole('alert')).textContent).toMatch(/access may have been removed/)
  })

  it('blocks members from the owner medication pages', async () => {
    renderAs(USERS.caretaker, '/medications')
    expect(await screen.findByText(/Access restricted/)).toBeTruthy()
    expect(medApi.getTodaySchedule).not.toHaveBeenCalled()
  })
})
