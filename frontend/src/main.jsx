import { StrictMode } from 'react'
import PasswordGate from './features/password/Password.Gate.jsx'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <PasswordGate>
    <App />
  </PasswordGate>,
)
