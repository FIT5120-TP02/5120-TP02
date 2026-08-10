import styles from './RouteBreakdown.module.css'
import RouteStepList from './RouteStep'

const ZONE_STYLES = {
  quiet: { color: '#16a34a', label: 'Quiet zone' },
  walk: { color: '#2dd4bf', label: 'Walk' },
  busy: { color: '#ef4444', label: 'Busy area' },
  transit: { color: '#0369a1', label: 'Transit' },
}

export default function RouteBreakdown({ route }) {
    if (!route) return null

    const hasBreakdown = route.breakdown && route.breakdown.length > 0
    const hasSteps = route.steps && route.steps.length > 0

    if (!hasBreakdown && !hasSteps) {
        return (
        <div className={styles.panel}>
            <p className={styles.title}>Route Breakdown</p>
            <p className={styles.emptyNote}>
            Detailed zone-by-zone breakdown isn't available for this route yet.
            </p>
        </div>
        )
    }

    return (
        <div className={styles.panel}>
            <p className={styles.title}>Route Breakdown</p>

            {hasBreakdown && (
                <>
                <div className={styles.strip}>
                    {route.breakdown.map((seg, i) => (
                    <div
                        key={i}
                        className={styles.stripSegment}
                        style={{ width: `${seg.widthPct}%`, backgroundColor: ZONE_STYLES[seg.zoneType]?.color }}
                    />
                    ))}
                </div>
                <div className={styles.legend}>
                    {Object.entries(ZONE_STYLES).map(([zoneType, config]) => (
                    <div key={zoneType} className={styles.legendItem}>
                        <span className={styles.legendDot} style={{ backgroundColor: config.color }} />
                        <span className={styles.legendLabel}>{config.label}</span>
                    </div>
                    ))}
                </div>
                </>
            )}

            {hasSteps && <RouteStepList steps={route.steps} />}
        </div>
    )
}