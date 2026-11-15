import { forwardRef } from 'react'
import { Link } from 'react-router-dom'

// Large touch targets (min 48px) and strong contrast for older users.
const BASE =
  'inline-flex min-h-12 items-center justify-center gap-2 rounded-xl px-5 py-3 text-base font-semibold shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60'

const VARIANTS = {
  primary: 'bg-teal-700 text-white hover:bg-teal-800',
  secondary: 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-100',
  danger: 'bg-rose-700 text-white hover:bg-rose-800',
  // For dark (teal) backgrounds. Colors must come from a variant, never from className:
  // conflicting utilities resolve by stylesheet order, not by class order.
  onDark: 'bg-white text-teal-900 hover:bg-teal-50 focus-visible:outline-white',
  onDarkOutline: 'border-2 border-white bg-transparent text-white hover:bg-teal-800 focus-visible:outline-white',
}

function buttonClass(variant = 'primary', extra = '') {
  return `${BASE} ${VARIANTS[variant] ?? VARIANTS.primary} ${extra}`
}

const Button = forwardRef(function Button({ variant = 'primary', className = '', type = 'button', ...props }, ref) {
  return <button ref={ref} type={type} className={buttonClass(variant, className)} {...props} />
})

export function ButtonLink({ variant = 'primary', className = '', ...props }) {
  return <Link className={buttonClass(variant, className)} {...props} />
}

export default Button
