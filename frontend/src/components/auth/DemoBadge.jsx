/** Marks demo (sample-data) accounts wherever the signed-in user is shown. */
export default function DemoBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-sm font-semibold uppercase tracking-wide text-amber-800 ring-1 ring-inset ring-amber-300 ${className}`}
      title="Demo account: sample data only"
    >
      Demo
    </span>
  )
}
