import SystemStatus from '../components/dashboard/SystemStatus'
import FeatureCard from '../components/ui/FeatureCard'

const iconProps = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, className: 'h-6 w-6' }

const features = [
  {
    title: 'Elderly individuals',
    description: 'A simple, readable view of daily routines, reminders and who is helping today.',
    icon: (
      <svg {...iconProps}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" strokeLinecap="round" /></svg>
    ),
  },
  {
    title: 'Family members',
    description: 'Stay informed about a loved one’s wellbeing and coordinate with caretakers.',
    icon: (
      <svg {...iconProps}><circle cx="8" cy="9" r="3" /><circle cx="17" cy="10" r="2.5" /><path d="M2 20a6 6 0 0 1 12 0M14 20a4 4 0 0 1 8 0" strokeLinecap="round" /></svg>
    ),
  },
  {
    title: 'Caretakers',
    description: 'Organise care tasks and keep a clear record of support provided.',
    icon: (
      <svg {...iconProps}><path d="M12 21s-8-4.9-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.1-8 11-8 11z" strokeLinejoin="round" /></svg>
    ),
  },
]

export default function Dashboard() {
  return (
    <div className="flex flex-col gap-10">
      <section className="rounded-3xl bg-gradient-to-br from-teal-700 to-teal-900 px-6 py-10 text-white shadow-sm sm:px-10 sm:py-14">
        <p className="text-sm font-medium uppercase tracking-wider text-teal-100">Welcome</p>
        <h1 className="mt-2 max-w-2xl text-3xl font-semibold leading-tight sm:text-4xl">
          Care that keeps everyone connected.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-teal-50">
          ElderCare Connect brings elderly individuals, their families and caretakers together on one calm,
          dependable platform for everyday care and medication management.
        </p>
      </section>

      <SystemStatus />

      <section aria-labelledby="who-heading">
        <h2 id="who-heading" className="mb-4 text-xl font-semibold text-slate-900">Who it’s for</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </section>
    </div>
  )
}
