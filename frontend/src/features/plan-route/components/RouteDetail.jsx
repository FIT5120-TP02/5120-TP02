import styles from './RouteDetail.module.css'

const LOAD_STYLES = {
    low: { label: 'LOW', bg: '#4d7c62', color: '#ffffff' },
    high: { label: 'HIGH', bg: '#ef4444', color: '#ffffff' },
}

export default function RouteDetailPanel({ route }) {
    if (!route) return null
    const load = route.loadLevel ? LOAD_STYLES[route.loadLevel] : null

    return (
        <div className={styles.panel}>
            <div className={styles.headerRow}>
                <div>
                    <h3 className={styles.name}>{route.name}</h3>
                    {route.waypoints && <p className={styles.via}>{route.waypoints.join(' → ')}</p>}
                </div>
                {load && (
                <span className={styles.badge} style={{ backgroundColor: load.bg, color: load.color }}>
                    {load.label}
                </span>
                )}
            </div>

            <p className={styles.description}>
                {route.description || 'No additional route notes available.'}
            </p>

            <div className={styles.statsGrid}>
                <div>
                    <p className={styles.statLabel}>Duration</p>
                    <p className={styles.statValue}>{route.durationMin} min</p>
                </div>
                <div>
                    <p className={styles.statLabel}>Distance</p>
                    <p className={styles.statValue}>{route.distanceKm} km</p>
                </div>
                {route.pedestrianPerMin != null && (
                    <div>
                        <p className={styles.statLabel}>Crowd density</p>
                        <p className={styles.statValue}>{route.pedestrianPerMin}/min</p>
                    </div>
                )}
                {route.transport && (
                    <div>
                        <p className={styles.statLabel}>Transport</p>
                        <p className={styles.statValueSmall}>{route.transport}</p>
                    </div>
                )}
            </div>
        </div>
    )
}