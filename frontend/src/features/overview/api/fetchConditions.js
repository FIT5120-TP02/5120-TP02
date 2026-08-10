import { mockConditions } from './mockConditions'

// Mirrors the shape of the real call you'll swap in later,
// e.g. fetch('/api/conditions?area=melbourne-cbd').then(res => res.json())
export async function fetchConditions() {
    await new Promise((resolve) => setTimeout(resolve, 300))
    return mockConditions
}