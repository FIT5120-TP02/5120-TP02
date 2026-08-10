import styles from './RouteStep.module.css'

const ZONE_STYLES = {
    quiet: { dot: '#16a34a', tagBg: '#134e4a', tagColor: '#ffffff', label: 'Quiet zone' },
    walk: { dot: '#2dd4bf', tagBg: '#fed7aa', tagColor: '#9a3412', label: 'Walk' },
    busy: { dot: '#ef4444', tagBg: '#fecaca', tagColor: '#991b1b', label: 'Busy area' },
    transit: { dot: '#0369a1', tagBg: '#bfdbfe', tagColor: '#1e3a8a', label: 'Transit' },
}

export default function RouteStepList({ steps }) {
    return (
        <div className={styles.list}>
            {steps.map((step, i) => {
                const config = ZONE_STYLES[step.zoneType]
                const isLast = i === steps.length - 1
                return (
                <div key={i} className={styles.step}>
                    <div className={styles.markerCol}>
                    <span className={styles.dot} style={{ backgroundColor: config?.dot }} />
                    {!isLast && <span className={styles.line} />}
                    </div>
                    <div className={styles.content}>
                    <p className={styles.label}>{step.label}</p>
                    <span className={styles.tag} style={{ backgroundColor: config?.tagBg, color: config?.tagColor }}>
                        {config?.label}
                    </span>
                    </div>
                </div>
                )
            })}
        </div>
    )
}