import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section className="mx-auto max-w-md py-16 text-center">
      <p className="text-base font-semibold text-teal-700">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-slate-600">The page you are looking for doesn’t exist.</p>
      <Link to="/" className="mt-6 inline-block rounded-lg bg-teal-700 px-4 py-2 text-base font-medium text-white hover:bg-teal-800">
        Back to dashboard
      </Link>
    </section>
  )
}
