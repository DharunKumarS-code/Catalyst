import { ButtonLink } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'

const iconProps = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, className: 'h-7 w-7' }

const roles = [
  {
    title: 'Elderly individuals',
    summary: 'Stay in charge of your own care.',
    points: [
      'See today’s medicines in large, clear text and record each dose with one tap.',
      'Keep track of doctor and clinic appointments.',
      'Decide who can see your information, and remove access at any time.',
    ],
    icon: (
      <svg {...iconProps}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" strokeLinecap="round" /></svg>
    ),
  },
  {
    title: 'Caretakers',
    summary: 'Support the people you look after.',
    points: [
      'One care dashboard for everyone you support: today’s doses, adherence and upcoming appointments.',
      'Record doses you give, when the person you care for allows it.',
      'Get an alert when a dose has not been recorded.',
    ],
    icon: (
      <svg {...iconProps}><path d="M12 21s-8-4.9-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.1-8 11-8 11z" strokeLinejoin="round" /></svg>
    ),
  },
  {
    title: 'Family members',
    summary: 'Stay informed, even from far away.',
    points: [
      'See how a loved one is doing with their medicines and appointments.',
      'Read-only access: nothing changes without them.',
      'Optional email alerts about missed doses.',
    ],
    icon: (
      <svg {...iconProps}><circle cx="8" cy="9" r="3" /><circle cx="17" cy="10" r="2.5" /><path d="M2 20a6 6 0 0 1 12 0M14 20a4 4 0 0 1 8 0" strokeLinecap="round" /></svg>
    ),
  },
]

const steps = [
  { title: 'Create an account', text: 'Choose whether you are the elderly person, a caretaker or a family member.' },
  { title: 'Add medicines and appointments', text: 'The elderly person sets up their profile, medicine times and appointments.' },
  { title: 'Invite your care circle', text: 'Share a one-time invitation code with a caretaker or family member.' },
]

export default function Dashboard() {
  const { status } = useAuth()
  const signedIn = status === 'authenticated'

  return (
    <div className="flex flex-col gap-12">
      <section className="rounded-3xl bg-gradient-to-br from-teal-700 to-teal-900 px-6 py-10 text-white shadow-sm sm:px-10 sm:py-14">
        <h1 className="max-w-2xl text-3xl font-bold leading-tight sm:text-4xl">
          Medicines, appointments and family care in one calm place.
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-relaxed text-teal-50">
          ElderCare Connect helps older people take their medicines on time and keep their appointments,
          while the caretakers and family they choose can follow along and help.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          {signedIn ? (
            <ButtonLink to="/dashboard" variant="onDark" className="min-h-14 text-lg">
              Go to my dashboard
            </ButtonLink>
          ) : (
            <>
              <ButtonLink to="/register" variant="onDark" className="min-h-14 text-lg">
                Create an account
              </ButtonLink>
              <ButtonLink to="/login" variant="onDarkOutline" className="min-h-14 text-lg">
                Sign in
              </ButtonLink>
            </>
          )}
        </div>
      </section>

      <section aria-labelledby="who-heading">
        <h2 id="who-heading" className="mb-4 text-2xl font-semibold text-slate-900">Who it’s for</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {roles.map((r) => (
            <article key={r.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50 text-teal-700" aria-hidden="true">
                {r.icon}
              </div>
              <h3 className="text-xl font-semibold text-slate-900">{r.title}</h3>
              <p className="mt-1 font-medium text-slate-700">{r.summary}</p>
              <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed text-slate-700">
                {r.points.map((p) => <li key={p}>{p}</li>)}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="how-heading">
        <h2 id="how-heading" className="mb-4 text-2xl font-semibold text-slate-900">How it works</h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {steps.map((s, i) => (
            <li key={s.title} className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-700 text-lg font-bold text-white" aria-hidden="true">
                {i + 1}
              </span>
              <div>
                <h3 className="text-lg font-semibold text-slate-900">{s.title}</h3>
                <p className="mt-1 leading-relaxed text-slate-700">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="privacy-heading" className="rounded-2xl border border-teal-200 bg-teal-50 p-6">
        <h2 id="privacy-heading" className="text-xl font-semibold text-teal-900">Private by design</h2>
        <p className="mt-2 leading-relaxed text-teal-900">
          Only people the elderly person invites can see their information, and they can remove anyone at any
          time. Reminder emails never include medicine names.
        </p>
      </section>
    </div>
  )
}
