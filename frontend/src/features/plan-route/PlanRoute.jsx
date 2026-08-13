import styles from './PlanRoute.module.css'
import { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Polyline } from 'react-leaflet'
import { fetchRoutes } from './api/fetchRoutes'
import { resolveLocation, isWithinCBD } from '../../lib/geocode'
import { useLiveLocation } from '../../lib/liveLocation'
import RouteList from './components/RouteList'
import RouteDetail from './components/RouteDetail'
import RouteBreakdown from './components/RouteBreakdown'
import RouteMap from './components/RouteMap'

const MY_LOCATION_DEFAULT = 'My Location — Melbourne CBD'

export default function PlanRoute({ initialDestination = '', initialDestinationCoords = null }) {
    const { userLocation, error: locationError, loading: locationLoading } = useLiveLocation()
    const [from, setFrom] = useState(MY_LOCATION_DEFAULT)
    const [to, setTo] = useState(initialDestination)
    const [routes, setRoutes] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [selectedRouteId, setSelectedRouteId] = useState(null)
    const [resolvedOrigin, setResolvedOrigin] = useState(null)
    const [resolvedDestination, setResolvedDestination] = useState(null)
    const [useMyLocation, setUseMyLocation] = useState(true)
    const selectedRoute = routes.find((r) => r.id === selectedRouteId) ?? null
    const resultsRef = useRef(null)
    const [maxSensoryLevel, setMaxSensoryLevel] = useState('high')

    const LOAD_RANK = { low: 1, high: 2 }

    const visibleRoutes = routes.filter((route) => {
        if (!route.loadLevel) return true // NO DATA routes always shown
        return LOAD_RANK[route.loadLevel] <= LOAD_RANK[maxSensoryLevel]
    })

    function handleSelectRoute(routeID) {
        setSelectedRouteId(routeID)
        if(resultsRef.current) {
            const y = resultsRef.current.getBoundingClientRect().top + window.scrollY - 100
            window.scrollTo({
                top: y,
                behavior: 'smooth',
            })
        }
    }

    async function handleSearch(fromText, toText, destinationOverride = null) {
        setLoading(true)
        setError(null)
        setMaxSensoryLevel('high')
        try {
            const origin = (useMyLocation && userLocation)
                ? { name: 'My Location', ...userLocation }
                : await resolveLocation(fromText)
            const destination = destinationOverride ?? await resolveLocation(toText)

            if (!isWithinCBD(origin) || !isWithinCBD(destination)) {
                setError('Senseway currently supports routes within our Melbourne CBD coverage area.')
                setRoutes([])
                setLoading(false)
                return
            }

            setResolvedOrigin(origin)
            setResolvedDestination(destination)

            const results = await fetchRoutes({ origin, destination })
            setRoutes(results)
            setSelectedRouteId(results[0]?.id ?? null)
        } catch (err) {
            setError(err.message || 'Something went wrong finding routes')
            setRoutes([])
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (selectedRouteId && !visibleRoutes.find((r) => r.id === selectedRouteId)) {
            setSelectedRouteId(visibleRoutes[0]?.id ?? null)
        }
    }, [maxSensoryLevel])

    useEffect(() => {
        if (initialDestination && !locationLoading) {
            const destinationOverride = initialDestinationCoords
                ? {name: initialDestination, lat: initialDestinationCoords.lat, lng: initialDestinationCoords.lng}
                : null
            handleSearch(from, initialDestination, destinationOverride)
        }
    }, [locationLoading]) // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <>
            <div className="HeaderContainer">
                <div className="FeatureHeader">
                    <div className="FeatureTitle">
                        <h2>Plan Route</h2>
                        <p>Sensory-safe paths</p>
                    </div>
                    <p>SenseWay /<span> Plan Route</span></p>
                </div>
            </div>
            <div className={styles.planRouteContent}>
                <div className={styles.planRouteSearchBar}>
                    <p>Journey Details</p>
                    <div className={styles.planRouteTitle}>
                        <div className={styles.planRouteFrom}>
                            <label htmlFor="from">From</label>
                            <div className={styles.planRouteFromInput}>
                                <span></span>
                                <input
                                    type="text"
                                    id="from"
                                    value={from}
                                    onChange={(e) => {
                                        setFrom(e.target.value)
                                        setUseMyLocation(false)
                                    }}
                                    placeholder="Enter starting location"
                                />
                            </div>
                        </div>
                        <div className={styles.planRouteTo}>
                            <label htmlFor="to">To</label>
                            <div className={styles.planRouteToInput}>
                                <span></span>
                                <input
                                    type="text"
                                    id="to"
                                    value={to}
                                    onChange={(e) => setTo(e.target.value)}
                                    placeholder="Enter destination"
                                />
                            </div>
                        </div>
                    </div>

                    <button type="button" onClick={() => handleSearch(from, to)} disabled={!from || !to || loading || locationLoading}>
                        {locationLoading ? 'Getting your location...' : loading ? 'Searching...' : 'Find Routes'}
                    </button>

                    {error && <p className={styles.errorText}>{error}</p>}
                </div>
                {routes.length > 0 && (
                    <div className={styles.sensoryFilterRow}>
                        <span className={styles.sensoryFilterLabel}>Max sensory load</span>
                        <div className={styles.sensoryFilterOptions}>
                            {['low', 'high'].map((level) => (
                                <button
                                    key={level}
                                    type="button"
                                    className={`${styles.sensoryFilterButton} ${maxSensoryLevel === level ? styles.sensoryFilterActive : ''}`}
                                    onClick={() => setMaxSensoryLevel(level)}
                                >
                                    {level === 'low' ? 'Low only' : 'All levels'}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
                {routes.length > 0 && (
                    <div className={styles.planRouteResults}>
                        <div className={styles.planRouteResultsLeft}>
                            <RouteList routes={visibleRoutes} selectedRouteId={selectedRouteId} onSelectRoute={handleSelectRoute} />
                        </div>
                        <div className={styles.planRouteResultsRight} ref={resultsRef}>
                            <RouteDetail route={selectedRoute} />
                            <RouteMap route={selectedRoute} />
                            <RouteBreakdown route={selectedRoute} />
                            
                        </div>
                    </div>
                )}
            </div>
        </>
    )
}