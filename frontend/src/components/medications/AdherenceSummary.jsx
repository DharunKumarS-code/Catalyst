import { formatPercent } from '../../medications/display'
import { formatCalendarDate } from '../../utils/format'

function Period({ title, period }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      <p className="mt-1 text-4xl font-bold text-slate-900" data-testid={`adherence-${title.toLowerCase().replace(/\s+/g, '-')}`}>
        {formatPercent(period.adherence_percent)}
      </p>
      <p className="mt-2 text-base text-slate-700">
        {period.taken} taken &middot; {period.missed} missed &middot; {period.pending} not recorded
        <span className="block text-sm text-slate-500">
          {period.total} dose{period.total === 1 ? '' : 's'} counted
        </span>
      </p>
    </div>
  )
}

/** Adherence = taken / eligible doses (due so far or already recorded). Upcoming and cancelled doses are not counted. */
export default function AdherenceSummary({ adherence }) {
  return (
    <section aria-labelledby="adherence-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 id="adherence-heading" className="text-2xl font-semibold text-slate-900">
        How it&rsquo;s going
      </h2>
      <p className="mt-1 text-base text-slate-600">Doses taken, out of the doses that are due so far or already recorded. Upcoming doses are not counted.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Period title="Today" period={adherence.today} />
        <Period title="Last 7 days" period={adherence.week} />
      </div>
      <table className="mt-6 w-full text-left text-base">
        <caption className="sr-only">Daily adherence for the last 7 days</caption>
        <thead>
          <tr className="border-b border-slate-200 text-slate-600">
            <th scope="col" className="py-2 font-medium">Day</th>
            <th scope="col" className="py-2 font-medium">Taken</th>
            <th scope="col" className="py-2 font-medium">Due</th>
            <th scope="col" className="py-2 font-medium">Adherence</th>
          </tr>
        </thead>
        <tbody>
          {[...adherence.days].reverse().map((d) => (
            <tr key={d.start_date} className="border-b border-slate-100 last:border-b-0">
              <th scope="row" className="py-2 font-medium text-slate-900">{formatCalendarDate(d.start_date)}</th>
              <td className="py-2 text-slate-800">{d.taken}</td>
              <td className="py-2 text-slate-800">{d.total}</td>
              <td className="py-2 font-semibold text-slate-900">{formatPercent(d.adherence_percent)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
