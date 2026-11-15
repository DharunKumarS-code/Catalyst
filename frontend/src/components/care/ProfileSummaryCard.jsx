import { formatAppointmentWhen } from '../../appointments/validation'
import { formatClockTime, formatPercent } from '../../medications/display'
import DemoBadge from '../auth/DemoBadge'

function Count({ label, value, tone }) {
  return (
    <div className={`rounded-lg px-3 py-2 ${tone}`}>
      <dt className="text-sm font-medium">{label}</dt>
      <dd className="text-2xl font-bold tabular-nums">{value}</dd>
    </div>
  )
}

/** One linked person at a glance. Acts as the selector for the detail panel below. */
export default function ProfileSummaryCard({ profile, selected, onSelect }) {
  const { today, next_dose: nextDose } = profile
  const nextAppt = profile.upcoming_appointments[0]
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      data-testid="profile-card"
      className={`flex h-full w-full flex-col gap-4 rounded-2xl border-2 bg-white p-5 text-left shadow-sm transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 ${
        selected ? 'border-teal-700 ring-1 ring-teal-700' : 'border-slate-200 hover:border-teal-500'
      }`}
    >
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-xl font-semibold text-slate-900">{profile.full_name}</span>
        {profile.is_demo && <DemoBadge />}
        {selected && <span className="ml-auto text-sm font-semibold text-teal-800">Showing below</span>}
      </span>

      <span className="block">
        <span className="block text-sm font-medium text-slate-600">Today&rsquo;s medicine adherence</span>
        <span className="block text-4xl font-bold text-slate-900" data-testid="card-adherence">
          {formatPercent(today.adherence_percent)}
        </span>
      </span>

      <dl className="grid grid-cols-3 gap-2">
        <Count label="Taken" value={today.taken} tone="bg-emerald-50 text-emerald-900" />
        <Count label="Missed" value={today.missed} tone="bg-rose-50 text-rose-900" />
        <Count label="Not recorded" value={today.pending} tone="bg-amber-50 text-amber-900" />
      </dl>

      <span className="block text-base text-slate-700">
        <strong className="font-semibold">Next medicine: </strong>
        {nextDose
          ? `${nextDose.medication_name} ${nextDose.dosage} at ${formatClockTime(nextDose.local_time)}`
          : 'none left today'}
      </span>
      <span className="block text-base text-slate-700">
        <strong className="font-semibold">Next appointment: </strong>
        {nextAppt ? `${nextAppt.doctor_name}, ${formatAppointmentWhen(nextAppt)}` : 'none scheduled'}
      </span>
    </button>
  )
}
