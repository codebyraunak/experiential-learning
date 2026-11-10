import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import { getApiErrorMessage, registerStudent } from '../services/api.js'

function RegistrationPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    usn: '',
    password: '',
    confirmPassword: '',
  })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField(event) {
    const { name, value } = event.target
    setForm((currentForm) => ({ ...currentForm, [name]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      const { data } = await registerStudent({
        usn: form.usn,
        password: form.password,
      })
      navigate('/login', {
        replace: true,
        state: { success: `Account created for ${data.name}. Please sign in.` },
      })
    } catch (requestError) {
      setError(
        getApiErrorMessage(requestError, 'Unable to create your account. Try again.'),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout pageClassName="registration-page">
      <div className="auth-card auth-card--registration">
        <header className="auth-heading">
          <h2>Create your account</h2>
          <p>Use your admission USN to create your account</p>
        </header>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="form-field">
            <span>Student ID (USN)</span>
            <input
              autoComplete="username"
              name="usn"
              onChange={updateField}
              placeholder="Enter student ID"
              required
              value={form.usn}
            />
          </label>

          <label className="form-field">
            <span>Password</span>
            <input
              autoComplete="new-password"
              name="password"
              onChange={updateField}
              placeholder="Enter password"
              required
              type="password"
              value={form.password}
            />
          </label>

          <label className="form-field">
            <span>Confirm password</span>
            <input
              autoComplete="new-password"
              name="confirmPassword"
              onChange={updateField}
              placeholder="Enter confirm password"
              required
              type="password"
              value={form.confirmPassword}
            />
          </label>

          {error && (
            <p className="form-message form-message--error" role="alert">
              {error}
            </p>
          )}

          <button className="auth-submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="auth-terms">
          By continuing, you agree to the campus digital policy.
        </p>
        <p className="auth-switch">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </AuthLayout>
  )
}

export default RegistrationPage
