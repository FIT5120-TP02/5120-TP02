import styles from "./Overview.module.css"
import { useState, useEffect } from 'react'
import { fetchConditions } from "./api/fetchConditions";
import { fetchForecast} from './api/fetchForecast'
import { fetchRefuges } from "../quiet-spaces/api/fetchRefuges";
import CrowdForecastChart from "./components/CrowdForecastChart";
import { KNOWN_LOCATIONS } from '../../lib/geocode'
import NavCard from "./components/NavCard";


const SensoryBadge = ({ level }) => {
    const config = {
        Low: {
            bg: '#f0fdf4',
            text: '#65a30d',
            dot: '#84cc16',
        },
        Medium: {
            bg: '#fef3c7',
            text: '#f59e0b',
            dot: '#f59e0b',
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
    const sensoryLevel = hour >= 7 && hour <= 9 ? 'High'
        : hour >= 11 && hour <= 14 ? 'Medium'
        : 'Low'
    const [conditions, setConditions] = useState(null)
    const [loading, setLoading] = useState(true)
    const [threshold, setThreshold] = useState(60)
    const [destination, setDestination] = useState('')
    const [forecast, setForecast] = useState([])
    const [refugeCount, setRefugeCount] = useState(null)
    useEffect(() => {
        async function loadConditions() {
            const data = await fetchConditions()
            setConditions(data)
            setLoading(false)
        }
        async function loadForecast() {
            const data = await fetchForecast()
            setForecast(data)
        }
        async function loadRefugeCount() {
            const cbd = KNOWN_LOCATIONS['My Location — Melbourne CBD']
            const data = await fetchRefuges({ lat: cbd.lat, lng: cbd.lng, radiusKm: 0.5 })
            setRefugeCount(data.length)
        }
        loadConditions()
        loadForecast()
        loadRefugeCount()
    }, [])

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
                                {!loading && conditions && (
                                    <div className={styles.DashboardCrowdDensityAlert}>
                                        <div className={styles.CrowdContainer}>
                                            <p>Crowd Density</p>
                                            <p>{conditions.crowdDensityPct}%</p>
                                            <p>{conditions.crowdDensityContext}</p>
                                        </div>
                                        <div className={styles.AlertContainer}>
                                            <p>Active Alerts</p>
                                            <p>{conditions.activeAlertsCount}</p>
                                            <p>{conditions.activeAlertsContext}</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                    {/* <div className={styles.SensoryThreshold}>
                        <div>
                            <p className={styles.ThresholdTitle}>
                            My Sensory Threshold
                            </p>

                            <p className={styles.ThresholdSubtitle}>
                            Alert me when crowd density exceeds this level
                            </p>
                        </div>

                        <div>
                            <div className={styles.ThresholdHeader}>
                                <span className={styles.ThresholdValue}>
                                    {threshold}%
                                </span>

                                <span
                                    className={
                                    threshold <= 40
                                        ? styles.Sensitive
                                        : threshold <= 65
                                        ? styles.Balanced
                                        : styles.Relaxed
                                    }
                                >
                                    {threshold <= 40
                                    ? 'Very sensitive'
                                    : threshold <= 65
                                        ? 'Balanced'
                                        : 'Relaxed'}
                                </span>
                                </div>

                                <input
                                type="range"
                                min={20}
                                max={90}
                                value={threshold}
                                onChange={(e) => setThreshold(Number(e.target.value))}
                                className={styles.ThresholdSlider}
                                />

                                <div className={styles.ThresholdRange}>
                                <span>20%</span>
                                <span>90%</span>
                            </div>

                            <p className={styles.ThresholdDescription}>
                            {threshold <= 40
                                ? 'Early warnings and frequent rerouting suggestions.'
                                : threshold <= 65
                                ? 'Balanced alerts for moderate crowd sensitivity.'
                                : 'Only alerted during very high-density situations.'}
                            </p>
                        </div>
                    </div> */}
                </div>
                
                {/* <div className={styles.ForecastNavContainer}>
                    <div className={styles.forecastChart}>
                        <CrowdForecastChart forecast={forecast}/>
                    </div>
                    <div className={styles.navCards}>
                        <NavCard
                            variant={'alerts'}
                            icon={'◎'}
                            title={'Live Alerts'}
                            subtitle={
                                conditions ? `${conditions.activeAlertsCount} high-severity stressors active near you` : 'Loading...'
                            }
                            onClick={() => onNavigate('alerts')}
                        />
                        <NavCard
                            variant={'refuges'}
                            icon={'♡'}
                            title={'Quiet Spaces'}
                            subtitle={
                                refugeCount != null
                                    ? `${refugeCount} sensory refuge${refugeCount === 1 ? '' : 's'} nearby` : 'Loading...'
                            }
                            onClick={() => onNavigate('refuges')}
                        />
                    </div>
                </div> */}
            </div>
        </>
    )
}