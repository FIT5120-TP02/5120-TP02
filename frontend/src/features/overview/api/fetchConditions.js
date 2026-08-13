import { KNOWN_LOCATIONS } from "../../../lib/geocode"
import { fetchWithTimeout } from "../../../lib/fetchWithTimeout"

const API_BASE_URL = 'https://five120-tp02.onrender.com'

export async function fetchConditions( userLocation ) {
    if (!userLocation?.lat || !userLocation?.lng) {
        throw new Error('Missing user location')
    }

    const cbd = KNOWN_LOCATIONS['Melbourne Central']
    try {
        const res = await fetchWithTimeout(`${API_BASE_URL}/api/routes/compare`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                origin_lat: userLocation.lat,
                origin_lng: userLocation.lng,
                destination_lat: cbd.lat,
                destination_lng: cbd.lng,
            }),
        }, 30000)

        if (!res.ok) {
            throw new Error(`API returned ${res.status}`)
        }

        const data = await res.json()

        if (!data.routes || data.routes.length === 0) {
            throw new Error('No route data returned')
        }

        const route = data.routes[0]
        console.log('Full route: ', route)

        return {
            pedestrianPerHour: route.pedestrian_per_hour,
            pedestrianPerMin: route.pedestrian_per_min,
        }
    } catch (err) {
        console.error('[fetchConditions] API unavailable:', err.message)
        throw err
    }
}