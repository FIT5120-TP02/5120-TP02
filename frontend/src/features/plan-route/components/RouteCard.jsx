import CrowdDensityBar from './CrowdDensityBar'
import styles from './RouteCard.module.css'

const LOAD_STYLES = {
    low: { label: 'Low', bg: '#4d7c62', color: '#ffffff' },
    medium: { label: 'Medium', bg: '#fbbf24', color: '#78350f' },
    high: { label: 'High', bg: '#ef4444', color: '#ffffff' },
}

const TAG_STYLES = {
    construction: { bg: '#fff7ed', color: '#c2410c' },
    event: { bg: '#faf5ff', color: '#7e22ce' },
    notice: { bg: '#eff6ff', color: '#1e40af' },
}

export default function RouteCard({ route, isSelected, onSelect }) {
    const load = route.loadLevel ? LOAD_STYLES[route.loadLevel] : null

    return (
        <button
        className={`${styles.card} ${isSelected ? styles.selected : ''}`}
        onClick={() => onSelect(route.id)}
        >
        <div className={styles.headerRow}>
            <h3 className={styles.name}>{route.name}</h3>
            {load && (
            <span className={styles.badge} style={{ backgroundColor: load.bg, color: load.color }}>
                {load.label}
            </span>
            )}
        </div>

        {route.tags?.length > 0 && (
            <div className={styles.tagsRow}>
            {route.tags.map((tag) => {
                const tagStyle = TAG_STYLES[tag.type] ?? { bg: '#f3f4f6', color: '#374151' }
                return (
                <span key={tag.label} className={styles.tag} style={{ backgroundColor: tagStyle.bg, color: tagStyle.color }}>
                    {tag.type === 'notice' ? 'ℹ' : '⚠'} {tag.label}
                </span>
                )
            })}
            </div>
        )}

        {route.crowdDensityPct != null && (
            <CrowdDensityBar percent={route.crowdDensityPct} level={route.loadLevel} />
        )}

        <p className={styles.meta}>
            {route.durationMin} min · {route.distanceKm} km
        </p>
        </button>
    )
}