import { forwardRef } from 'react'

const VARIANTS = {
  error: 'border-rose-200 bg-rose-50 text-rose-800',
  info: 'border-teal-200 bg-teal-50 text-teal-900',
  success: 'border-emerald-300 bg-emerald-50 text-emerald-900',
}

// Errors use role="alert" (announced immediately); info uses role="status" (polite).
const Alert = forwardRef(function Alert({ variant = 'info', children }, ref) {
  return (
    <div
      ref={ref}
      tabIndex={-1}
      role={variant === 'error' ? 'alert' : 'status'}
      className={`rounded-lg border px-4 py-3 text-base focus:outline-none ${VARIANTS[variant] ?? VARIANTS.info}`}
    >
      {children}
    </div>
  )
})

export default Alert
