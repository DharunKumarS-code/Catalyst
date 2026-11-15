import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import { getToken, setToken } from '../auth/tokenStorage'
import { validateRegistration } from '../auth/validation'
import AuthProvider from '../context/AuthProvider'

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchDemoAccounts: vi.fn(async () => []),
}))
vi.mock('../api/portal', () => ({
  fetchPortal: vi.fn(async (area) => ({ area, message: `Welcome to the ${area} area.` })),
}))
vi.mock('../api/health', () => ({
  fetchHealth: vi.fn(() => new Promise(() => {})),
}))

// Unsigned test token: the frontend only reads `exp`; the backend verifies signatures.
function fakeToken(expSecondsFromNow = 1800) {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ sub: 'u1', exp: Math.floor(Date.now() / 1000) + expSecondsFromNow })}.sig`
}

const USER = { id: 'u1', name: 'Jane Doe', email: 'jane@example.com', role: 'caretaker', created_at: '2026-01-15T10:00:00Z' }
const session = (user = USER) => ({ access_token: fakeToken(), token_type: 'bearer', expires_in: 1800, user })
const apiError = (status, detail) => Object.assign(new Error('Request failed'), { response: { status, data: { detail } } })

function renderApp(path = '/') {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
  return user
}

beforeEach(() => vi.clearAllMocks())

describe('protected routes', () => {
  it('redirects anonymous users from /dashboard to the sign-in page', async () => {
    renderApp('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
  })

  it('restores a stored session via /me', async () => {
    setToken(fakeToken())
    authApi.fetchCurrentUser.mockResolvedValue(USER)
    renderApp('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Hello, Jane Doe' })).toBeTruthy()
    expect(authApi.fetchCurrentUser).toHaveBeenCalledTimes(1)
  })

  it('discards a stored token the backend rejects', async () => {
    setToken(fakeToken())
    authApi.fetchCurrentUser.mockRejectedValue(apiError(401, 'Invalid authentication token.'))
    renderApp('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(getToken()).toBeNull()
  })

  it('does not use an expired stored token', async () => {
    setToken(fakeToken(-60))
    renderApp('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(authApi.fetchCurrentUser).not.toHaveBeenCalled()
    expect(getToken()).toBeNull()
  })
})

describe('login', () => {
  it('signs in, shows user info and role, and stores the token', async () => {
    const issued = session()
    authApi.loginUser.mockResolvedValue(issued)
    const user = renderApp('/login')
    await user.type(screen.getByLabelText('Email address'), '  Jane@Example.com ')
    await user.type(screen.getByLabelText('Password'), 'SafePassword123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Hello, Jane Doe' })).toBeTruthy()
    expect(authApi.loginUser).toHaveBeenCalledWith({ email: 'jane@example.com', password: 'SafePassword123' })
    expect(screen.getAllByText('Caretaker').length).toBeGreaterThan(0)
    expect(await screen.findByText('Welcome to the caretaker area.')).toBeTruthy()
    expect(getToken()).toBe(issued.access_token)
    expect(window.sessionStorage.getItem('ecc.accessToken')).toBe(issued.access_token)
  })

  it('returns to the originally requested page after sign-in', async () => {
    authApi.loginUser.mockResolvedValue(session())
    const user = renderApp('/dashboard')
    await user.type(await screen.findByLabelText('Email address'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'SafePassword123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Hello, Jane Doe' })).toBeTruthy()
  })

  it('shows a generic error for wrong credentials and stays signed out', async () => {
    authApi.loginUser.mockRejectedValue(apiError(401, 'Invalid email or password.'))
    const user = renderApp('/login')
    await user.type(screen.getByLabelText('Email address'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'WrongPassword1')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Invalid email or password.')
    await waitFor(() => expect(document.activeElement).toBe(alert))
    expect(getToken()).toBeNull()
  })

  it('validates fields before calling the API', async () => {
    const user = renderApp('/login')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Enter your email address.')).toBeTruthy()
    expect(screen.getByText('Enter your password.')).toBeTruthy()
    expect(screen.getByLabelText('Email address').getAttribute('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(screen.getByLabelText('Email address'))
    expect(authApi.loginUser).not.toHaveBeenCalled()
  })
})

describe('registration', () => {
  async function fillForm(user, { role = 'Caretaker', password = 'SafePassword123', confirm = password } = {}) {
    await user.click(screen.getByRole('radio', { name: new RegExp(`^${role}`) }))
    await user.type(screen.getByLabelText('Full name'), 'Jane Doe')
    await user.type(screen.getByLabelText('Email address'), 'Jane@Example.com')
    await user.type(screen.getByLabelText('Password', { selector: 'input[name="password"]' }), password)
    await user.type(screen.getByLabelText('Confirm password'), confirm)
  }

  it('registers with the selected role and lands on the dashboard', async () => {
    authApi.registerUser.mockResolvedValue(session())
    const user = renderApp('/register')
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Hello, Jane Doe' })).toBeTruthy()
    expect(authApi.registerUser).toHaveBeenCalledWith({
      name: 'Jane Doe',
      email: 'jane@example.com',
      password: 'SafePassword123',
      role: 'caretaker',
    })
  })

  it('blocks weak passwords and mismatched confirmation client-side', async () => {
    const user = renderApp('/register')
    await fillForm(user, { password: 'weakpass' })
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText(/Password needs at least 12 characters/)).toBeTruthy()
    expect(authApi.registerUser).not.toHaveBeenCalled()
  })

  it('requires a role', async () => {
    const user = renderApp('/register')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Choose how you will use ElderCare Connect.')).toBeTruthy()
    expect(authApi.registerUser).not.toHaveBeenCalled()
  })

  it('shows the server message for a duplicate email', async () => {
    authApi.registerUser.mockRejectedValue(apiError(409, 'An account with this email already exists.'))
    const user = renderApp('/register')
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect((await screen.findByRole('alert')).textContent).toContain('An account with this email already exists.')
  })

  it('validateRegistration rejects mismatched passwords', () => {
    const errors = validateRegistration({
      name: 'Jane', email: 'jane@example.com', password: 'SafePassword123', confirmPassword: 'Different123A', role: 'elderly',
    })
    expect(errors).toEqual({ confirmPassword: 'Passwords do not match.' })
  })
})

describe('logout', () => {
  it('clears the session and blocks the dashboard again', async () => {
    setToken(fakeToken())
    authApi.fetchCurrentUser.mockResolvedValue(USER)
    const user = renderApp('/dashboard')
    await screen.findByRole('heading', { name: 'Hello, Jane Doe' })

    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('You have been signed out.')
    expect(getToken()).toBeNull()
    expect(window.sessionStorage.getItem('ecc.accessToken')).toBeNull()
    expect(screen.queryByRole('link', { name: 'My dashboard' })).toBeNull()
  })
})
