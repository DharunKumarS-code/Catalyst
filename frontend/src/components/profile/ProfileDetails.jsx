import { formatCalendarDate } from '../../utils/format'
import { timeZoneLabel } from '../../utils/timezones'

const NOT_PROVIDED = <span className="text-slate-400">Not provided</span>

function Item({ label, children }) {
  return (
    <div className="border-b border-slate-100 py-4 last:border-b-0 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-base font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 whitespace-pre-line break-words text-lg text-slate-900 sm:col-span-2 sm:mt-0">{children || NOT_PROVIDED}</dd>
    </div>
  )
}

/** Read-only profile view shared by the owner and authorized family/caretakers. */
export default function ProfileDetails({ profile }) {
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="personal-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="personal-heading" className="text-xl font-semibold text-slate-900">Personal details</h2>
        <dl className="mt-2">
          <Item label="Full name">{profile.full_name}</Item>
          <Item label="Date of birth">{formatCalendarDate(profile.date_of_birth)}</Item>
          <Item label="Phone number">{profile.phone}</Item>
          <Item label="Address">{profile.address}</Item>
          <Item label="Time zone">{timeZoneLabel(profile.timezone)}</Item>
        </dl>
      </section>
      <section aria-labelledby="emergency-heading" className="rounded-2xl border border-amber-200 bg-amber-50/50 p-6 shadow-sm">
        <h2 id="emergency-heading" className="text-xl font-semibold text-slate-900">Emergency contact</h2>
        <dl className="mt-2">
          <Item label="Name">{profile.emergency_contact_name}</Item>
          <Item label="Phone number">
            {profile.emergency_contact_phone && (
              <a href={`tel:${profile.emergency_contact_phone.replace(/[^\d+]/g, '')}`} className="font-medium text-teal-800 underline underline-offset-2">
                {profile.emergency_contact_phone}
              </a>
            )}
          </Item>
        </dl>
      </section>
      <section aria-labelledby="notes-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="notes-heading" className="text-xl font-semibold text-slate-900">Additional notes</h2>
        <p className="mt-3 whitespace-pre-line break-words text-lg text-slate-900">{profile.notes || NOT_PROVIDED}</p>
      </section>
    </div>
  )
}
