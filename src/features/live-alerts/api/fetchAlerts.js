import { mockAlerts, mockPredictive } from './mockAlerts'

export async function fetchAlerts() {
    await new Promise((resolve) => setTimeout(resolve, 300))
    return mockAlerts
}

export async function fetchPredictiveStressors() {
    await new Promise((resolve) => setTimeout(resolve, 300))
    return mockPredictive
}