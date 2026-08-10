import styles from './CrowdDensityBar.module.css'

const FILL_COLOR_BY_LEVEL = {
    low: '#16a34a',
    medium: '#f59e0b',
    high: '#ef4444',
}

export default function CrowdDensityBar({ percent, level }) {
    const fillColor = FILL_COLOR_BY_LEVEL[level] ?? '#16a34a'

    return (
        <div className={styles.wrapper}>
            <div className={styles.labelRow}>
                <span className={styles.label}>Crowd density</span>
                <span className={styles.percent}>{percent}%</span>
            </div>
            <div className={styles.track}>
                <div
                className={styles.fill}
                style={{ width: `${percent}%`, backgroundColor: fillColor }}
                />
            </div>
        </div>
    )
}