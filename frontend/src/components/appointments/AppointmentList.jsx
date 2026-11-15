import { Link } from 'react-router-dom'
import { formatAppointmentDate } from '../../appointments/validation'
import { formatClockTime } from '../../medications/display'
import DemoBadge from '../auth/DemoBadge'
import AppointmentStatusBadge from './AppointmentStatusBadge'

/** Appointment cards with a large, clear date and time. `linkTo(appt)` gives the detail URL. */
export default function AppointmentList({ appointments, linkTo, emptyText }) {
  if (appointments.length === 0) return <p className="text-lg text-slate-600">{emptyText}</p>
  return (
    <ul className="flex flex-col gap-4">
      {appointments.map((a) => (
        <li key={a.id} data-testid="appointment-row">
          <Link
            to={linkTo(a)}
            className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-teal-600 hover:bg-teal-50 sm:flex-row sm:items-center"
          >
            <span className="shrink-0 sm:w-64">
              <span className="block text-lg font-semibold text-slate-900">{formatAppointmentDate(a.appointment_date)}</span>
              <span className="block text-2xl font-bold tabular-nums text-teal-800">{formatClockTime(a.appointment_time)}</span>
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="break-words text-xl font-semibold text-slate-900">{a.doctor_name}</span>
                {a.is_demo && <DemoBadge />}
              </span>
              {a.specialization && <span className="block text-base text-slate-600">{a.specialization}</span>}
              <span className="block break-words text-lg text-slate-700">{a.clinic_name}</span>
            </span>
            <AppointmentStatusBadge appointment={a} />
          </Link>
        </li>
      ))}
    </ul>
  )
}
