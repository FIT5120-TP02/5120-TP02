import { useState, useEffect } from 'react'

/**
 * Tracks the user's live geolocation using the browser's Geolocation API.
 * No backend involved — purely client-side.
 *
 * @returns {{ userLocation: {lat, lng} | null, error: string | null, loading: boolean }}
 */
export function useLiveLocation() {
    const [userLocation, setUserLocation] = useState(null)
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!navigator.geolocation) {
            setError('Geolocation is not supported by this browser')
            setLoading(false)
            return
        }

        console.log('Starting watchPosition...')

        const watchId = navigator.geolocation.watchPosition(
            (position) => {
                setUserLocation({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                })
                setError(null)
                setLoading(false)
            },
            (err) => {
                setError(err.message) // e.g. "User denied Geolocation"
                setLoading(false)
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 5000, // reuse a cached position up to 5s old
            }
        )

        // cleanup: stop watching when the component unmounts
        return () => navigator.geolocation.clearWatch(watchId)
    }, [])

    return { userLocation, error, loading }
}