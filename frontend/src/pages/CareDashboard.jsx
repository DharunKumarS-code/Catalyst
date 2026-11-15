import { useSearchParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getCareDashboard } from '../api/care'
import AppointmentList from '../components/appointments/AppointmentList'
import RoleBadge from '../components/auth/RoleBadge'
import ProfileSummaryCard from '../components/care/ProfileSummaryCard'
import RecentActivity from '../components/care/RecentActivity'
import TodaySchedule from '../components/medications/TodaySchedule'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useAuth } from '../hooks/useAuth'
import { useResource } from '../hooks/useResource'
import { formatCalendarDate, formatDateTime } from '../utils/format'
import { timeZoneLabel } from '../utils/timezones'

function Section({ id, title, action, children }) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 id={id} className="text-2xl font-semibold text-slate-900">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  )
}

function ProfileDetail({ p }) {
  const base = `/linked/${p.profile_id}`
  return (
    <div className="flex flex-col gap-6" data-testid="profile-detail">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-semibold text-slate-900">{p.full_name}</h2>
          <p className="mt-1 inline-flex flex-wrap items-center gap-2 text-base text-slate-600">
            You are connected as <RoleBadge role={p.role} />
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink to={base} variant="secondary">Full profile</ButtonLink>
          <ButtonLink to={`${base}/medications`} variant="secondary">All medicines</ButtonLink>
          <ButtonLink to={`${base}/appointments`} variant="secondary">All appointments</ButtonLink>
        </div>
      </div>

      <TodaySchedule
        schedule={{ date: p.local_date, timezone: p.timezone, doses: p.today_doses }}
        canModify={false}
        emptyText={p.active_medications === 0 ? 'No medicines have been added yet.' : undefined}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          id={`appts-${p.profile_id}`}
          title="Upcoming appointments"
          action={p.upcoming_appointment_count > p.upcoming_appointments.length && (
            <span className="text-base text-slate-600">{p.upcoming_appointment_count} in total</span>
          )}
        >
          <AppointmentList
            appointments={p.upcoming_appointments}
            linkTo={(a) => `${base}/appointments/${a.id}`}
            emptyText="No upcoming appointments."
          />
        </Section>
        <Section id={`activity-${p.profile_id}`} title="Recent activity">
          <RecentActivity items={p.recent_activity} />
        </Section>
      </div>

      <Section id={`about-${p.profile_id}`} title="About">
        <dl className="grid gap-4 text-lg sm:grid-cols-2">
          <div>
            <dt className="text-base font-medium text-slate-500">Date of birth</dt>
            <dd className="text-slate-900">{p.date_of_birth ? formatCalendarDate(p.date_of_birth) : 'Not provided'}</dd>
          </div>
          <div>
            <dt className="text-base font-medium text-slate-500">Phone</dt>
            <dd className="text-slate-900">{p.phone || 'Not provided'}</dd>
          </div>
          <div>
            <dt className="text-base font-medium text-slate-500">Emergency contact</dt>
            <dd className="text-slate-900">
              {p.emergency_contact_name},{' '}
              <a href={`tel:${p.emergency_contact_phone.replace(/[^\d+]/g, '')}`} className="font-medium text-teal-800 underline underline-offset-2">
                {p.emergency_contact_phone}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-base font-medium text-slate-500">Time zone</dt>
            <dd className="text-slate-900">{timeZoneLabel(p.timezone)}</dd>
          </div>
        </dl>
      </Section>
    </div>
  )
}

/** /care: monitoring dashboard for caretakers and family members (read-only). */
export default function CareDashboard() {
  const { user } = useAuth()
  const { loading, data, error, reload } = useResource(getCareDashboard)
  const [params, setParams] = useSearchParams()

  const header = (
    <PageHeader
      title="Care dashboard"
      description="How the people you support are doing today. Only they can record doses or change details."
      actions={
        <Button variant="secondary" onClick={reload} disabled={loading}>
          {loading && data ? 'Refreshing…' : 'Refresh'}
        </Button>
      }
    />
  )

  if (error && !data) {
    return (
      <div className="mx-auto max-w-6xl">
        {header}
        <Alert variant="error">{getApiErrorMessage(error, 'We could not load the care dashboard.')}</Alert>
        <Button className="mt-4" onClick={reload}>Try again</Button>
      </div>
    )
  }
  if (!data) return <PageLoader label="Loading the care dashboard…" />

  if (data.profiles.length === 0) {
    return (
      <div className="mx-auto max-w-6xl">
        {header}
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <h2 className="text-2xl font-semibold text-slate-900">No one is connected yet</h2>
          <p className="mx-auto mt-2 max-w-xl text-lg text-slate-600">
            When an elderly person invites you, enter their invitation code to see their medicines and appointments here.
          </p>
          <ButtonLink to="/join" className="mt-6">Enter an invitation code</ButtonLink>
        </div>
      </div>
    )
  }

  const requested = params.get('profile')
  const selected = data.profiles.find((p) => p.profile_id === requested) ?? data.profiles[0]

  return (
    <div className="mx-auto max-w-6xl">
      {header}
      {user.is_demo && (
        <div role="note" className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-base text-amber-900">
          <strong>Demo account:</strong> everything here is sample data.
        </div>
      )}
      {error && (
        <div className="mb-6">
          <Alert variant="error">{getApiErrorMessage(error, 'Refreshing failed. Showing the last loaded information.')}</Alert>
        </div>
      )}
      <p className="mb-4 text-sm text-slate-500" aria-live="polite">
        Updated {formatDateTime(data.generated_at)}
      </p>

      <section aria-labelledby="people-heading" className="mb-10">
        <h2 id="people-heading" className="mb-4 text-xl font-semibold text-slate-900">
          People you support ({data.profiles.length})
        </h2>
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.profiles.map((p) => (
            <li key={p.profile_id}>
              <ProfileSummaryCard
                profile={p}
                selected={p.profile_id === selected.profile_id}
                onSelect={() => setParams({ profile: p.profile_id }, { replace: true })}
              />
            </li>
          ))}
        </ul>
      </section>

      <ProfileDetail key={selected.profile_id} p={selected} />
    </div>
  )
}
