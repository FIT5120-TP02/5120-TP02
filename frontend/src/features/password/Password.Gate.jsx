import { useState } from 'react'
import styles from './PasswordGate.module.css'

export default function PasswordGate({ children }) {
    const [password, setPassword] = useState('')
    const [authenticated, setAuthenticated] = useState(false)
    const [error, setError] = useState('')

    const sitePassword = import.meta.env.VITE_SITE_PASSWORD

    function handleSubmit(e) {
        e.preventDefault()

        if (password === sitePassword) {
            setAuthenticated(true)
            setError('')
            sessionStorage.setItem('senseway_authenticated', 'true')
        } else {
            setError('Incorrect password')
        }
    }

    if (
        authenticated ||
        sessionStorage.getItem('senseway_authenticated') === 'true'
    ) {
        return children
    }

    return (
        <div className={styles.container}>
            <div className={styles.card}>
                <h1>SenseWay</h1>
                <p className={styles.subtitle}>
                    Enter the password to access SenseWay.
                </p>

                <form onSubmit={handleSubmit}>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => {
                            setPassword(e.target.value)
                            setError('')
                        }}
                        placeholder="Enter password"
                        autoFocus
                    />

                    <button type="submit">
                        Continue
                    </button>
                </form>

                {error && (
                    <p className={styles.error}>
                        {error}
                    </p>
                )}
            </div>
        </div>
    )
}