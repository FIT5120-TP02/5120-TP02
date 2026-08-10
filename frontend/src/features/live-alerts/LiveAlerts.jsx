import { useState, useEffect } from 'react'
import styles from './LiveAlerts.module.css'
import { fetchAlerts, fetchPredictiveStressors } from './api/fetchAlerts.js'

const TYPE_CONFIG = {
  crowd: { icon: '⊛', label: 'Crowd', iconBg: '#fee2e2', iconColor: '#ef4444' },
  construction: { icon: '⚠', label: 'Construction', iconBg: '#ffedd5', iconColor: '#f97316' },
  event: { icon: '◈', label: 'Event', iconBg: '#f3e8ff', iconColor: '#a855f7' },
  enforcement: { icon: '◉', label: 'Police', iconBg: '#dbeafe', iconColor: '#3b82f6' },
}

const SEVERITY_CONFIG = {
  high: { bg: 'rgba(254, 242, 242, 0.8)', border: '#fecaca', badgeBg: '#ef4444', badgeColor: '#ffffff', label: 'High' },
  medium: { bg: 'rgba(255, 251, 235, 0.6)', border: '#fde68a', badgeBg: '#fbbf24', badgeColor: '#ffffff', label: 'Medium' },
  low: { bg: 'rgba(255, 255, 255, 0.6)', border: '#ccfbf1', badgeBg: '#99f6e4', badgeColor: '#0f766e', label: 'Low' },
}

const LEVEL_BAR_COLOR = { high: '#f87171', medium: '#fbbf24', low: '#4d7c62' }
const LEVEL_TEXT_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#4d7c62' }

const FILTERS = [
    { value: 'all', label: 'All alerts' },
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
    ]

    export default function LiveAlerts() {
    const [alerts, setAlerts] = useState([])
    const [predictive, setPredictive] = useState([])
    const [filter, setFilter] = useState('all')
    const [expandedId, setExpandedId] = useState(null)

    useEffect(() => {
        async function load() {
        const [alertsData, predictiveData] = await Promise.all([
            fetchAlerts(),
            fetchPredictiveStressors(),
        ])
        setAlerts(alertsData)
        setPredictive(predictiveData)
        setExpandedId(alertsData[0]?.id ?? null)
        }
        load()
    }, [])

    const filtered = alerts.filter((a) => filter === 'all' || a.severity === filter)

    return (
        <>
        <div className="HeaderContainer">
            <div className="FeatureHeader">
                <div className="FeatureTitle">
                    <h2>Live Alerts</h2>
                    <p>Real-time stressors nearby</p>
                </div>
                <p>SenseWay /<span> Live Alerts</span></p>
            </div>
        </div>

        <div className={styles.content}>
            <div className={styles.layout}>
                <div className={styles.listColumn}>
                    <div className={styles.filterRow}>
                    {FILTERS.map((f) => (
                        <button
                        key={f.value}
                        className={`${styles.filterButton} ${filter === f.value ? styles.filterActive : ''}`}
                        onClick={() => setFilter(f.value)}
                        >
                        {f.label}
                        </button>
                    ))}
                    </div>

                    {filtered.map((alert) => {
                    const typeCfg = TYPE_CONFIG[alert.type]
                    const sevCfg = SEVERITY_CONFIG[alert.severity]
                    const isExpanded = expandedId === alert.id

                    return (
                        <div
                        key={alert.id}
                        className={styles.alertCard}
                        style={{ backgroundColor: sevCfg.bg, borderColor: sevCfg.border }}
                        >
                        <button
                            className={styles.alertHeader}
                            onClick={() => setExpandedId(isExpanded ? null : alert.id)}
                        >
                            <span
                            className={styles.typeIcon}
                            style={{ backgroundColor: typeCfg.iconBg, color: typeCfg.iconColor }}
                            >
                            {typeCfg.icon}
                            </span>
                            <span className={styles.alertMain}>
                            <span className={styles.alertTitleRow}>
                                <span className={styles.alertTitle}>{alert.title}</span>
                                <span
                                className={styles.severityBadge}
                                style={{ backgroundColor: sevCfg.badgeBg, color: sevCfg.badgeColor }}
                                >
                                {sevCfg.label}
                                </span>
                            </span>
                            <span className={styles.alertLocation}>{alert.location}</span>
                            <span className={styles.alertMeta}>
                                {alert.distanceM}m away · Since {alert.since} · Clears ~{alert.predictedEnd}
                            </span>
                            </span>
                            <span className={`${styles.chevron} ${isExpanded ? styles.chevronOpen : ''}`}>▾</span>
                        </button>

                        {isExpanded && (
                            <div className={styles.alertDetail}>
                            <p className={styles.alertDescription}>{alert.description}</p>
                            <div className={styles.alertDetailFooter}>
                                <span className={styles.clearText}>
                                Expected to clear: <strong>{alert.predictedEnd}</strong>
                                </span>
                                <button className={styles.avoidButton}>Avoid this area →</button>
                            </div>
                            </div>
                        )}
                        </div>
                    )
                    })}
                </div>

                <div className={styles.sideColumn}>
                    <div className={styles.predictivePanel}>
                        <p className={styles.panelTitle}>Predicted Stressors</p>
                        <p className={styles.panelSubtitle}>Next 4 hours · Based on historical Melbourne pedestrian data</p>

                        <div className={styles.predictiveList}>
                            {predictive.map((p) => (
                            <div key={p.time + p.zone}>
                                <div className={styles.predictiveRow}>
                                <div>
                                    <p className={styles.predictiveZone}>{p.zone}</p>
                                    <p className={styles.predictiveReason}>{p.reason}</p>
                                </div>
                                <div className={styles.predictiveRight}>
                                    <p className={styles.predictiveTime}>{p.time}</p>
                                    <p className={styles.predictiveLevel} style={{ color: LEVEL_TEXT_COLOR[p.level] }}>
                                    {p.level.toUpperCase()}
                                    </p>
                                </div>
                                </div>
                                <div className={styles.predictiveTrack}>
                                <div
                                    className={styles.predictiveFill}
                                    style={{ width: `${p.pct}%`, backgroundColor: LEVEL_BAR_COLOR[p.level] }}
                                />
                                </div>
                            </div>
                            ))}
                        </div>
                    </div>

                    <div className={styles.notifyPanel}>
                        <p className={styles.notifyTitle}>Push Notifications</p>
                        <p className={styles.notifySubtitle}>Get alerted before stressors reach your threshold.</p>
                        <div className={styles.notifyOptions}>
                            {['High severity alerts', 'Predicted stressor warnings', 'Route impact updates'].map((item) => (
                            <label key={item} className={styles.notifyOption}>
                                <input type="checkbox" defaultChecked />
                                <span>{item}</span>
                            </label>
                            ))}
                        </div>
                        <button className={styles.saveButton}>Save notification preferences</button>
                    </div>
                </div>
            </div>
        </div>
        </>
  )
}