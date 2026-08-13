import styles from "./Overview.module.css"
import { useState, useEffect } from 'react'
import { fetchConditions } from "./api/fetchConditions";
import { useLiveLocation } from "../../lib/liveLocation";
import { fetchRefuges } from "../quiet-spaces/api/fetchRefuges";
import { resolveLocation } from '../../lib/geocode'
import { KNOWN_LOCATIONS } from '../../lib/geocode'
import NavCard from "./components/NavCard";


const SensoryBadge = ({ level }) => {
    const config = {
        Low: {
            bg: '#f0fdf4',
            text: '#65a30d',
            dot: '#84cc16',
        },
        High: {
            bg: '#fee2e2',
            text: '#ef4444',
            dot: '#ef4444',
        },
    }[level] || {
        bg: '#f0fdf4',
        text: '#65a30d',
        dot: '#84cc16',
    };

    return (
        <span className={styles.SensorDisplay} style={{backgroundColor: config.bg, color: config.text }}>
        <span className={styles.SensoryDot} style={{ backgroundColor: config.dot}} />
            {level} Sensory Load
        </span>
    );
};

export default function Overview({onNavigate}) {
    const now = new Date()
    const currentTime = now.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'})
    const hour = now.getHours() // 0-23, actual number
    
    const [conditions, setConditions] = useState(null)
    const [loading, setLoading] = useState(true)
    const [threshold, setThreshold] = useState(60)
    const [destination, setDestination] = useState('')
    const [refugeCount, setRefugeCount] = useState(null)
    const { userLocation, error: locationError, loading: locationLoading } = useLiveLocation()
    const [hasFetchedConditions, setHasFetchedConditions] = useState(false)

    useEffect(() => {
        if (locationLoading) return // still waiting on GPS, don't fetch yet
        if (hasFetchedConditions) return // fetch once per page load. To fix issue of multiple fetch on Overview

        async function loadConditions() {
            try {
                setLoading(true)
                const originPoint = userLocation ?? KNOWN_LOCATIONS['My Location — Melbourne CBD']
                const data = await fetchConditions(originPoint)
                console.log('Conditions: ', data)
                setConditions(data)
                setHasFetchedConditions(true)
            } catch (err) {
                console.log('[Overview] failed to load conditions:', err)
            } finally {
                setLoading(false)
            }
        }
        async function loadRefugeCount() {
            const cbd = KNOWN_LOCATIONS['My Location — Melbourne CBD']
            const data = await fetchRefuges({ lat: cbd.lat, lng: cbd.lng, radiusKm: 0.5 })
            setRefugeCount(data.length)
        }
        loadConditions()
        loadRefugeCount()
    }, [locationLoading, userLocation?.lat, userLocation?.lng, hasFetchedConditions])

    const sensoryLevel = conditions?.pedestrianPerHour >= 700 ? 'High'
        : conditions?.pedestrianPerHour >= 400 ? 'Medium'
        : 'Low'
    return (
        <>
            <div className="HeaderContainer">
                <div className="FeatureHeader">
                    <div className="FeatureTitle">
                        <h2>Overview</h2>
                        <p>Live conditions</p>
                    </div>
                    <p>SenseWay /
                        <span> Overview</span>
                    </p>
                </div>
            </div>
            <div className={styles.DashboardContainer}>
                <div className={styles.routePlanner}>
                    <p className={styles.routePlannerTitle}>
                        Plan a Sensory-Safe Route
                    </p>

                    <div className={styles.destinationRow}>
                        <div className={styles.destinationInputWrapper}>
                            <span className={styles.destinationIcon}>⊕</span>

                            <input
                                type="text"
                                value={destination}
                                onChange={(e) => setDestination(e.target.value)}
                                placeholder="Enter your destination..."
                                className={styles.destinationInput}
                            />
                        </div>

                        <button
                            onClick={() => 
                                onNavigate('routes', destination)
                            }
                            className={styles.findRoutesButton}
                        >
                            Find Routes →
                        </button>
                    </div>

                    <div className={styles.quickDestinations}>
                        <span className={styles.quickLabel}>Quick:</span>

                        {Object.entries(KNOWN_LOCATIONS).map(([name, coords]) => (
                            <button
                                key={name}
                                onClick={() => {
                                    setDestination(name)
                                    onNavigate('routes', name)
                                }}
                                className={styles.quickButton}
                            >
                                {name}
                            </button>
                        ))}
                    </div>
                </div>
                <div className={styles.DashboardDisplay}>
                    <div className={styles.DashboardLive}>
                        <div></div>
                        <div></div>
                        <div>
                            <p>Current Conditions · Melbourne CBD</p>
                            <div className={styles.DashboardReportBoard}>
                                <div className={styles.DashboardTimeSensor}>
                                    <p>{currentTime}</p>
                                    <SensoryBadge level={sensoryLevel} />
                                </div>
                                {!loading && conditions?.pedestrianPerHour && (
                                    <div className={styles.CrowdContainer}>
                                        <p>Crowd Density</p>
                                        <p>{conditions.pedestrianPerHour}/Hour</p>
                                        <p>{conditions.crowdDensityContext}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                    
                </div>
                
                
            </div>
        </>
    )
}