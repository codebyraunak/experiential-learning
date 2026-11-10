import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import {
  getApiErrorMessage,
  loginStaffOrAdmin,
  loginStudent,
} from '../services/api.js'

function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [role, setRole] = useState('student')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(location.state?.success ?? '')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSuccess('')
    setIsSubmitting(true)

    try {
      const { data } = role === 'student'
        ? await loginStudent({ usn: username, password })
        : await loginStaffOrAdmin({ role, username, password })
      const user = data.student ?? data.user
      const auth = {
        access_token: data.access_token,
        role: user.role ?? role,
        id: user.id,
        name: user.name,
      }
      sessionStorage.setItem('campusfix.auth', JSON.stringify(auth))
      if (auth.role === 'student') {
        sessionStorage.setItem('campusfix.student', JSON.stringify(user))
      }
      setSuccess(`Welcome back, ${user.name}.`)
      const defaultPath = auth.role === 'admin'
        ? '/admin'
        : auth.role === 'staff' ? '/staff/tasks' : '/report'
      const returnTo = location.state?.from
      navigate(returnTo ? `${returnTo.pathname}${returnTo.search}` : defaultPath, { replace: true })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to sign in. Try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout pageClassName="login-page">
      <div className="auth-card">
        <header className="auth-heading">
          <h2>Sign in to CampusFix</h2>
          <p>Access your campus maintenance workspace</p>
        </header>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="form-field">
            <span>Sign in as</span>
            <select
              name="role"
              onChange={(event) => {
                setRole(event.target.value)
                setUsername('')
              }}
              value={role}
            >
              <option value="student">Student</option>
              <option value="staff">Maintenance staff</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <label className="form-field">
            <span>{role === 'student' ? 'Student ID (USN)' : role === 'admin' ? 'Admin username' : 'Employee ID'}</span>
            <input
              autoComplete="username"
              name="username"
              onChange={(event) => setUsername(event.target.value)}
              placeholder={role === 'student' ? 'Enter your student ID' : 'Enter your username'}
              required
              value={username}
            />
          </label>

          <label className="form-field">
            <span>Password</span>
            <input
              autoComplete="current-password"
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter password"
              required
              type="password"
              value={password}
            />
          </label>

          {error && (
            <p className="form-message form-message--error" role="alert">
              {error}
            </p>
          )}
          {success && (
            <p className="form-message form-message--success" role="status">
              {success}
            </p>
          )}

          <button className="auth-submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="auth-switch">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </AuthLayout>
  )
}

export default LoginPage
