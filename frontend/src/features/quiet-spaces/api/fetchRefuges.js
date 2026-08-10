import { mockRefuges } from './mockRefuges'
import { transformRefuge } from './transformRefuges'

const API_BASE = import.meta.env.VITE_API_BASE_URL

/**
 * @param {{ lat: number, lng: number, radiusKm?: number }} params
 */
export async function fetchRefuges({ lat, lng, radiusKm = 1.5 } = {}) {
    try {
        if (lat == null || lng == null) {
        throw new Error('Missing coordinates')
        }

        const params = new URLSearchParams({
            lat: String(lat),
            lng: String(lng),
            radius_km: String(radiusKm),
        })

        const res = await fetch(`${API_BASE}/api/refuges?${params}`)
        if (!res.ok) throw new Error(`API returned ${res.status}`)

        const data = await res.json()
        if (!data.refuges || data.refuges.length === 0) {
        throw new Error('No refuges returned')
        }

        return data.refuges.map(transformRefuge)
    } catch (err) {
        console.error('[fetchRefuges] Live API unavailable, using mock data:', err)
        throw err
    }
}