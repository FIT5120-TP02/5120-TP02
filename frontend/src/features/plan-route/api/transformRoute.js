
function normalizeSensoryStatus(status) {
    if (!status) return null
    const lower = String(status).toLowerCase()
    if (lower.includes('high')) return 'high'
    if (lower.includes('med')) return 'medium'
    if (lower.includes('low')) return 'low'
  return null // e.g. "NO DATA" or anything unrecognized
}

/**
 * Converts a real RouteOption (from /api/routes/compare) into the shape
 * PlanRoute's components expect. Fields the real API doesn't provide
 * (crowdDensityPct, waypoints, breakdown, steps) are explicitly null —
 * components must handle that, not assume mock-data completeness.
 */
export function transformRouteOption(option) {
    return {
        id: option.route_id,
        name: option.label,
        distanceKm: option.distance_km,
        durationMin: option.duration_min,
        loadLevel: normalizeSensoryStatus(option.sensory_status),
        rawSensoryStatus: option.sensory_status,
        crowdDensityPct: null,
        transport: null,
        tags: option.avoided_corridor
        ? [{ type: 'notice', label: `Avoids ${option.avoided_corridor}` }]
        : [],
        description: option.notification ?? '',
        geometry: option.geometry ?? [],
        waypoints: null,
        breakdown: null,
        steps: null,
        isLiveData: true,
    }
}