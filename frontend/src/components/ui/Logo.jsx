export default function Logo({ className = '' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-teal-700" />
      <path d="M16 24s-7-4.4-7-9.6A3.9 3.9 0 0 1 16 12a3.9 3.9 0 0 1 7 2.4C23 19.6 16 24 16 24z" fill="#fff" />
    </svg>
  )
}
