const YEAR = new Date().getFullYear()

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-5 text-sm text-slate-500 sm:flex-row sm:justify-between sm:px-6 lg:px-8">
        <p>&copy; {YEAR} ElderCare Connect</p>
        <p>Phase 7 &middot; Reminders &amp; notifications</p>
      </div>
    </footer>
  )
}
