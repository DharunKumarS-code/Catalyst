import { createContext } from 'react'

/**
 * value: {
 *   status: 'initializing' | 'authenticated' | 'anonymous',
 *   user: { id, name, email, role, created_at } | null,
 *   notice: string | null,           // e.g. "Your session has expired."
 *   login({ email, password }), register({ name, email, password, role }), logout(reason?)
 * }
 */
export const AuthContext = createContext(null)
