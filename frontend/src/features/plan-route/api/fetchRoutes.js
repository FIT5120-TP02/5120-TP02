import { transformRouteOption } from './transformRoute'

const API_BASE_URL = 'https://five120-tp02.onrender.com'

/**
 * @param {{ 
 * origin: {lat, lng}, 
 * destination: {lat, lng}, 
 * preferenceId?: number }} params
 */
export async function fetchRoutes({ origin, destination, preferenceId }) {
    try {
        if (origin?.lat == null ||
            origin?.lng == null ||
            destination?.lat == null ||
            destination?.lng == null) {
        throw new Error('Missing coordinates')
        }
        
        const res = await fetch(`${API_BASE_URL}/api/routes/compare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin_lat: origin.lat,
                origin_lng: origin.lng,
                destination_lat: destination.lat,
                destination_lng: destination.lng,
                preference_id: preferenceId ?? null,
            }),
        })
        if (!res.ok) {
            throw new Error(`API returned ${res.status}`)
        }
        const data = await res.json()

        console.table(
            data.routes.map((route) => ({
                origin: origin,
                destination: destination,
                id: route.route_id,
                name: route.label,
                distance: route.distance_km,
                duration: route.duration_min,
                sensory_load: route.sensory_status,
            }))
        )

        if (!data.routes || data.routes.length === 0) {
            throw new Error('No routes returned')
        }

        return data.routes.map(transformRouteOption)
    } catch (err) {
        console.error('[fetchRoutes] Live API unavailable, using mock data:', err)
        throw err
    }
}