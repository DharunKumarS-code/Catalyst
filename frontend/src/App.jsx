import { Route, Routes } from 'react-router-dom'
import { ROLES } from './auth/roles'
import ProtectedRoute from './components/auth/ProtectedRoute'
import PublicOnlyRoute from './components/auth/PublicOnlyRoute'
import Layout from './components/layout/Layout'
import AppointmentDetail from './pages/AppointmentDetail'
import AppointmentEditor from './pages/AppointmentEditor'
import AppointmentsDashboard from './pages/AppointmentsDashboard'
import CareDashboard from './pages/CareDashboard'
import Connections from './pages/Connections'
import Dashboard from './pages/Dashboard'
import LinkedProfileDetail from './pages/LinkedProfileDetail'
import LinkedAppointments from './pages/LinkedAppointments'
import LinkedMedications from './pages/LinkedMedications'
import LinkedProfiles from './pages/LinkedProfiles'
import Login from './pages/Login'
import MedicationDetail from './pages/MedicationDetail'
import MedicationEditor from './pages/MedicationEditor'
import MedicationHistory from './pages/MedicationHistory'
import MedicationsDashboard from './pages/MedicationsDashboard'
import MyDashboard from './pages/MyDashboard'
import NotFound from './pages/NotFound'
import NotificationsPage from './pages/NotificationsPage'
import ProfileEditor from './pages/ProfileEditor'
import ProfilePage from './pages/ProfilePage'
import RedeemInvitation from './pages/RedeemInvitation'
import Register from './pages/Register'

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
