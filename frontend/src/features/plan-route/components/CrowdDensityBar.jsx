import styles from './CrowdDensityBar.module.css'

const FILL_COLOR_BY_LEVEL = {
    low: '#16a34a',
    high: '#ef4444',
}

const widthByLevel = {
    low: 50,
    high: 100,
}

export default function CrowdDensityBar({ crowd, level }) {
    const fillColor = FILL_COLOR_BY_LEVEL[level] ?? '#16a34a'

    return (
        <div className={styles.wrapper}>
            <div className={styles.labelRow}>
                <span className={styles.label}>Crowd density</span>
                <span className={styles.percent}>{crowd}/hour</span>
            </div>
            <div className={styles.track}>
                <div
                className={styles.fill}
                style={{ width: `${widthByLevel[level] ?? 0}%`, backgroundColor: fillColor }}
                />
            </div>
        </div>
    )
}