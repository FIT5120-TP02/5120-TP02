import styles from './CrowdForecastChart.module.css'

const LEVEL_COLORS = {
    low: '#5a8f6f',
    medium: '#f5a623',
    high: '#f56565',
}

const LEGEND_ITEMS = [
    { level: 'low', label: 'Low' },
    { level: 'medium', label: 'Medium' },
    { level: 'high', label: 'High' },
]

export default function CrowdForecastChart({ forecast }) {
    if (!forecast || forecast.length === 0) return null

    return (
        <div className={styles.panel}>
            <div className={styles.headerRow}>
                <p className={styles.title}>Crowd Forecast — Next 8 Hours</p>
                <div className={styles.legend}>
                {LEGEND_ITEMS.map((item) => (
                    <div key={item.level} className={styles.legendItem}>
                    <span
                        className={styles.legendDot}
                        style={{ backgroundColor: LEVEL_COLORS[item.level] }}
                    />
                    <span className={styles.legendLabel}>{item.label}</span>
                    </div>
                ))}
                </div>
            </div>

            <div className={styles.chart}>
                {forecast.map((hour, i) => (
                <div key={i} className={styles.barColumn}>
                    <div className={styles.barTrack}>
                    <div
                        className={styles.bar}
                        style={{
                        height: `${hour.crowdPct}%`,
                        backgroundColor: LEVEL_COLORS[hour.level],
                        }}
                    />
                    </div>
                    <span className={styles.barLabel}>{hour.label}</span>
                </div>
                ))}
            </div>
        </div>
    )
}