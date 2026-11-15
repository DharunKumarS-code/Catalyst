import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { clearToken } from '../auth/tokenStorage'

afterEach(() => {
  cleanup()
  clearToken()
  window.sessionStorage.clear()
})
