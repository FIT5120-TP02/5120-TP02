import { useState } from 'react'
import Header from './components/Header'
import AppShell from './components/AppShell'

export default function App() {
  const [activeButton, setActiveButton] = useState('Overview')
  return (
    <div className="AppContainer">
      <Header activeButton={activeButton} setActiveButton={setActiveButton}/>
      <AppShell activeButton={activeButton} setActiveButton={setActiveButton}/>
    </div>
  )
}
