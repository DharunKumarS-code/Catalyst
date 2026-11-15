import StatusBadge from './StatusBadge'

export default function StatusCard({ title, description, variant, label, detail }) {
  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <StatusBadge variant={variant}>{label}</StatusBadge>
      </div>
      {detail && <p className="text-sm text-slate-600">{detail}</p>}
    </article>
  )
}
