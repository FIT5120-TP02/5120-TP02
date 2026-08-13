import { transformRouteOption } from './transformRoute'
import { fetchWithTimeout } from '../../../lib/fetchWithTimeout'
const API_BASE_URL = 'https://five120-tp02.onrender.com'

/**
 * @param {{ 
 * origin: {lat, lng}, 
 * destination: {lat, lng} }} params
 */
export async function fetchRoutes({ origin, destination}) {
    try {
        if (origin?.lat == null ||
            origin?.lng == null ||
            destination?.lat == null ||
            destination?.lng == null) {
        throw new Error('Missing coordinates')
        }
        const res = await fetchWithTimeout(`${API_BASE_URL}/api/routes/compare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin_lat: origin.lat,
                origin_lng: origin.lng,
                destination_lat: destination.lat,
                destination_lng: destination.lng,
            }),
        }, 30000)
        
        if (!res.ok) {
            throw new Error(`API returned ${res.status}`)
        }
        const data = await res.json()

        if (!data.routes || data.routes.length === 0) {
            throw new Error('No routes returned')
        }

        return data.routes.map(transformRouteOption)
    } catch (err) {
        console.error('[fetchRoutes] Live API unavailable:', err.message)
        throw err
    }
}