import { lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import { ROLES } from './auth/roles'
import ProtectedRoute from './components/auth/ProtectedRoute'
import PublicOnlyRoute from './components/auth/PublicOnlyRoute'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Register from './pages/Register'

// First-visit pages load with the app; signed-in pages are fetched on demand (route-level code splitting).
const AppointmentDetail = lazy(() => import('./pages/AppointmentDetail'))
const AppointmentEditor = lazy(() => import('./pages/AppointmentEditor'))
const AppointmentsDashboard = lazy(() => import('./pages/AppointmentsDashboard'))
const CareDashboard = lazy(() => import('./pages/CareDashboard'))
const Connections = lazy(() => import('./pages/Connections'))
const LinkedProfileDetail = lazy(() => import('./pages/LinkedProfileDetail'))
const LinkedAppointments = lazy(() => import('./pages/LinkedAppointments'))
const LinkedMedications = lazy(() => import('./pages/LinkedMedications'))
const LinkedProfiles = lazy(() => import('./pages/LinkedProfiles'))
const MedicationDetail = lazy(() => import('./pages/MedicationDetail'))
const MedicationEditor = lazy(() => import('./pages/MedicationEditor'))
const MedicationHistory = lazy(() => import('./pages/MedicationHistory'))
const MedicationsDashboard = lazy(() => import('./pages/MedicationsDashboard'))
const MyDashboard = lazy(() => import('./pages/MyDashboard'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const ProfileEditor = lazy(() => import('./pages/ProfileEditor'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const RedeemInvitation = lazy(() => import('./pages/RedeemInvitation'))

const ELDERLY_ONLY = [ROLES.ELDERLY]
const SUPPORTERS = [ROLES.CARETAKER, ROLES.FAMILY_MEMBER]

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route element={<PublicOnlyRoute />}>
          <Route path="login" element={<Login />} />
          <Route path="register" element={<Register />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route path="dashboard" element={<MyDashboard />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>
        <Route element={<ProtectedRoute roles={ELDERLY_ONLY} />}>
          <Route path="profile" element={<ProfilePage />} />
          <Route path="profile/setup" element={<ProfileEditor />} />
          <Route path="profile/edit" element={<ProfileEditor />} />
          <Route path="connections" element={<Connections />} />
          <Route path="medications" element={<MedicationsDashboard />} />
          <Route path="medications/new" element={<MedicationEditor />} />
          <Route path="medications/history" element={<MedicationHistory />} />
          <Route path="medications/:medicationId" element={<MedicationDetail />} />
          <Route path="medications/:medicationId/edit" element={<MedicationEditor />} />
          <Route path="appointments" element={<AppointmentsDashboard />} />
          <Route path="appointments/new" element={<AppointmentEditor />} />
          <Route path="appointments/:appointmentId" element={<AppointmentDetail />} />
          <Route path="appointments/:appointmentId/edit" element={<AppointmentEditor />} />
        </Route>
        <Route element={<ProtectedRoute roles={SUPPORTERS} />}>
          <Route path="care" element={<CareDashboard />} />
          <Route path="join" element={<RedeemInvitation />} />
          <Route path="linked" element={<LinkedProfiles />} />
          <Route path="linked/:profileId" element={<LinkedProfileDetail />} />
          <Route path="linked/:profileId/medications" element={<LinkedMedications />} />
          <Route path="linked/:profileId/medications/history" element={<MedicationHistory />} />
          <Route path="linked/:profileId/medications/:medicationId" element={<MedicationDetail />} />
          <Route path="linked/:profileId/appointments" element={<LinkedAppointments />} />
          <Route path="linked/:profileId/appointments/:appointmentId" element={<AppointmentDetail />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
