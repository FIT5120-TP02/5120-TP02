/**
 * Converts a real RefugeLocationOut (from /api/refuges) into the shape
 * QuietSpaces' components expect. Fields the real API doesn't provide
 * (address, suburb, crowdLevel, features, hours, sensoryScore, sunflower)
 * are explicitly null/empty — components must handle that gracefully.
 */
export function transformRefuge(refuge) {
    return {
        id: String(refuge.location_id),
        name: refuge.name,
        type: normalizeCategory(refuge.category),
        walkMinutes: Math.round(refuge.eta_min),
        lat: refuge.lat,
        lng: refuge.lng,
        address: null,
        suburb: null,
        distanceM: null,
        crowdLevel: null,
        features: [],
        hours: null,
        sensoryScore: null,
        sunflower: false,
        isLiveData: true,
    }
}

// Real API's `category` values are unconfirmed — normalize defensively
// against your known TYPE_CONFIG keys (park/library/indoor/garden).
function normalizeCategory(category) {
    if (!category) return 'indoor'
    const lower = String(category).toLowerCase()
    if (lower.includes('park')) return 'park'
    if (lower.includes('librar')) return 'library'
    if (lower.includes('garden')) return 'garden'
    if (lower.includes('indoor')) return 'indoor'
    return 'indoor' // fallback so TYPE_CONFIG lookup never breaks
}