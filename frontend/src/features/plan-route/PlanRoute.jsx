import styles from './PlanRoute.module.css'
import { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Polyline } from 'react-leaflet'
import { fetchRoutes } from './api/fetchRoutes'
import { resolveLocation } from '../../lib/geocode'
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

    function handleSelectRoute(routeID) {
        setSelectedRouteId(routeID)
        if(window.innerWidth < 1024 && resultsRef.current) {
            const y = resultsRef.current.getBoundingClientRect().top + window.scrollY - 80
            window.scrollTo({
                top: y,
                behavior: 'smooth',
                block: 'start'
            })
        }
    }

    async function handleSearch(fromText, toText, destinationOverride = null) {
        setLoading(true)
        setError(null)
        try {
            const origin = (useMyLocation && userLocation)
                ? { name: 'My Location', ...userLocation }
                : await resolveLocation(fromText)
            const destination = destinationOverride ?? await resolveLocation(toText)

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
                    <div className={styles.planRouteResults}>
                        <div className={styles.planRouteResultsLeft}>
                            <RouteList routes={routes} selectedRouteId={selectedRouteId} onSelectRoute={handleSelectRoute} />
                        </div>
                        <div className={styles.planRouteResultsRight} ref={resultsRef}>
                            <RouteDetail route={selectedRoute} />
                            <RouteMap route={selectedRoute} />
                            <RouteBreakdown route={selectedRoute} />
                            
                            {/* {selectedRoute && (
                                <a
                                    href={`https://www.google.com/maps/dir/?api=1&origin=${resolvedOrigin.lat},${resolvedOrigin.lng}&destination=${resolvedDestination.lat},${resolvedDestination.lng}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={styles.navigationButton}
                                >
                                    Start Navigation on This Route →
                                </a>
                            )} */}
                        </div>
                    </div>
                )}
            </div>
        </>
    )
}