import { useState, useEffect } from 'react'
import Overview from '../features/overview/Overview';
import PlanRoute from '../features/plan-route/PlanRoute';
import LiveAlerts from '../features/live-alerts/LiveAlerts';
import QuietSpaces from '../features/quiet-spaces/QuietSpaces';

const API_BASE_URL = 'https://five120-tp02.onrender.com'

export default function MainContent(props) {
    const { activeButton, setActiveButton } = props;
    const [plannedDestination, setPlannedDestination] = useState('')
    const [plannedDestinationCoords, setPlannedDestinationCoords] = useState(null)


    useEffect(() => {
        fetch(`${API_BASE_URL}/health`).catch(() => {})
    }, [])

    function handleNavigate(tab, destination, destinationCoords) {
        const tabToButtonLabel = {
            home: 'Overview',
            routes: 'Plan Route',
            alerts: 'Live Alerts',
            refuges: 'Quiet Spaces',
        }
        if (destination !== undefined) {
            setPlannedDestination(destination)
        }
        if(destinationCoords !== undefined) {
            setPlannedDestinationCoords(destinationCoords ?? null)
        }
        setActiveButton(tabToButtonLabel[tab])
    }
    return (
        <main>
            {activeButton === 'Overview' && <Overview onNavigate={handleNavigate}/>}
            {activeButton === 'Plan Route' && <PlanRoute initialDestination={plannedDestination} initialDestinationCoords={plannedDestinationCoords}/>}
            {activeButton === 'Live Alerts' && <LiveAlerts />}
            {activeButton === 'Quiet Spaces' && <QuietSpaces onNavigate={handleNavigate}/>}
        </main>
    )
}