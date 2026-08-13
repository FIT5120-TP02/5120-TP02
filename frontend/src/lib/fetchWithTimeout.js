export async function fetchWithTimeout(url, options = {}, timeoutMs = 20000) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)
    try {
        const res = await fetch(url, { ...options, signal: controller.signal })
        clearTimeout(timeout)
        return res
    } catch (err) {
        clearTimeout(timeout)
        if (err.name === 'AbortError') {
            throw new Error('Request timed out')
        }
        throw err
    }
}