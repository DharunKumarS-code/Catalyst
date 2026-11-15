import { Suspense, useRef } from 'react'
import { Outlet } from 'react-router-dom'
import PageLoader from '../ui/PageLoader'
import Footer from './Footer'
import Header from './Header'
import RouteAnnouncer from './RouteAnnouncer'

export default function Layout() {
  const mainRef = useRef(null)
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <RouteAnnouncer mainRef={mainRef} />
      <Header />
      <main
        id="main"
        ref={mainRef}
        tabIndex={-1}
        className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 focus:outline-none sm:px-6 lg:px-8"
      >
        {/* Lazy pages show the standard loader (an accessible status message) while their code loads. */}
        <Suspense fallback={<PageLoader label="Loading page…" />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
    </div>
  )
}
