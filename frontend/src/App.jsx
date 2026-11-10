import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import LoginPage from './pages/LoginPage.jsx'
import RegistrationPage from './pages/RegistrationPage.jsx'
import ReportPage from './pages/ReportPage.jsx'
import TrackingPage from './pages/TrackingPage.jsx'
import StaffTasksPage from './pages/StaffTasksPage.jsx'
import AdminPage from './pages/AdminPage.jsx'
import QrCodesPage from './pages/QrCodesPage.jsx'

function readAuth() {
  try {
    return JSON.parse(sessionStorage.getItem('campusfix.auth') ?? 'null')
  } catch {
    return null
  }
}

function ProtectedRoute({ roles, children }) {
  const auth = readAuth()
  const location = useLocation()
  if (!auth?.access_token || !roles.includes(auth.role)) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return children
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegistrationPage />} />
        <Route path="/report" element={<ProtectedRoute roles={['student']}><ReportPage /></ProtectedRoute>} />
        <Route path="/tracking" element={<ProtectedRoute roles={['student']}><TrackingPage /></ProtectedRoute>} />
        <Route path="/staff/tasks" element={<ProtectedRoute roles={['staff']}><StaffTasksPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute roles={['admin']}><AdminPage /></ProtectedRoute>} />
        <Route path="/admin/qr-codes" element={<ProtectedRoute roles={['admin']}><QrCodesPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
