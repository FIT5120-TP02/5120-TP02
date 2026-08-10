import { mockForecast } from './mockForecast'

// Mirrors the shape of the real call you'll swap in later,
// e.g. fetch('/api/conditions?area=melbourne-cbd').then(res => res.json())
export async function fetchForecast() {
    await new Promise((resolve) => setTimeout(resolve, 300))
    return mockForecast
}