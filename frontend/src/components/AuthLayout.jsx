import { Link } from 'react-router-dom'

function AuthLayout({ children, pageClassName = '' }) {
  return (
    <main className={`auth-shell ${pageClassName}`}>
      <section className="auth-brand" aria-label="CampusFix">
        <Link className="brand-lockup" to="/login" aria-label="CampusFix home">
          <span className="brand-mark">CF</span>
          <span className="brand-name">CampusFix</span>
        </Link>

        <div className="brand-message">
          <h1>
            A better campus
            <br />
            <span>starts with every fix.</span>
          </h1>
          <p>
            Smarter maintenance. Faster fixes. A better campus experience for
            everyone.
          </p>
        </div>

        <div className="brand-footer">
          <span className="brand-tagline">ONE PLATFORM · FASTER RESOLUTION</span>
          <p>© 2026 CampusFix. Campus operations, simplified.</p>
        </div>
      </section>

      <section className="auth-content">{children}</section>
    </main>
  )
}

export default AuthLayout
