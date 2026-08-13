export const KNOWN_LOCATIONS = {
    'My Location — Melbourne CBD': { lat: -37.8136, lng: 144.9631 },
    'Flinders St Station': { lat: -37.8183, lng: 144.9671 },
    'Melbourne Central': { lat: -37.8103, lng: 144.9628 },
    'Fed Square': { lat: -37.8180, lng: 144.9691 },
    'State Library': { lat: -37.8098, lng: 144.9652 },
    'Southern Cross': { lat: -37.8183, lng: 144.9530 },
}
export const CBD_BOUNDS = {
    minLat: -37.835,
    maxLat: -37.795,
    minLng: 144.935,
    maxLng: 144.985,
}
export function isWithinCBD({ lat, lng }) {
    return (
        lat >= CBD_BOUNDS.minLat &&
        lat <= CBD_BOUNDS.maxLat &&
        lng >= CBD_BOUNDS.minLng &&
        lng <= CBD_BOUNDS.maxLng
    )
}
/**
 * Resolves free text into { name, lat, lng }.
 * Checks known locations first (instant, no network call).
 * Falls back to Nominatim (OpenStreetMap) geocoding for anything else.
 * Throws if nothing can be resolved.
 */
export async function resolveLocation(text) {
    const trimmed = text.trim()
    if (!trimmed) throw new Error('Please enter a location')

    if (KNOWN_LOCATIONS[trimmed]) {
        return { name: trimmed, ...KNOWN_LOCATIONS[trimmed] }
    }

    const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
        trimmed + ', Melbourne, Australia'
        )}&format=json&limit=1`,
        { headers: { 'Accept-Language': 'en' } }
    )

    if (!res.ok) {
        throw new Error('Geocoding service unavailable')
    }

    const results = await res.json()
    if (!results || results.length === 0) {
        throw new Error(`Could not find "${text}" — try a nearby landmark`)
    }

    return {
        name: trimmed,
        lat: parseFloat(results[0].lat),
        lng: parseFloat(results[0].lon),
    }
}