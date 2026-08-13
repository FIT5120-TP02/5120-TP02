import { useState, useEffect, useRef } from 'react'
import styles from './QuietSpaces.module.css'
import { fetchRefuges } from './api/fetchRefuges'
import SensoryRing from './components/SensoryRing'
import { KNOWN_LOCATIONS } from '../../lib/geocode'
import { useLiveLocation } from '../../lib/liveLocation'

const TYPE_CONFIG = {
    park: { icon: '⊙', label: 'Park', bg: '#dcfce7', color: '#16a34a' },
    library: { icon: '⊡', label: 'Library', bg: '#ccfbf1', color: '#0f766e' },
    indoor: { icon: '⊞', label: 'Indoor', bg: '#f3e8ff', color: '#9333ea' },
    garden: { icon: '⊘', label: 'Garden', bg: '#d1fae5', color: '#059669' },
}

const FILTERS = [
    { value: 'all', label: 'All spaces' },
    { value: 'park', label: 'Parks' },
    { value: 'library', label: 'Libraries' },
    { value: 'indoor', label: 'Indoor' },
    { value: 'garden', label: 'Gardens' },
]

export default function QuietSpaces({onNavigate}) {
    const { userLocation, loading: locationLoading } = useLiveLocation()
    const [refuges, setRefuges] = useState([])
    const [filter, setFilter] = useState('all')
    const [sortBy, setSortBy] = useState('distance')
    const [selectedId, setSelectedId] = useState(null)
    const [radiusKm, setRadiusKm] = useState(0.5)
    const [loading, setLoading] = useState(true)
    const detailColumnRef = useRef(null)

    function handleSelectRefuge(refugeId) {
        setSelectedId(refugeId)
        if(detailColumnRef.current) {
            const y = detailColumnRef.current.getBoundingClientRect().top + window.scrollY - 100
            window.scrollTo({
                top: y,
                behavior: 'smooth',
                })
        }
    }

    useEffect(() => {
        if (locationLoading) return

        async function load() {
            setLoading(true)
            try {
                const location = userLocation ?? KNOWN_LOCATIONS['My Location — Melbourne CBD']

                const data = await fetchRefuges({
                    lat: location.lat,
                    lng: location.lng,
                    radiusKm: radiusKm,
                })
                setRefuges(data)
                setSelectedId(data[0]?.id ?? null)
            } catch(err) {
                console.error('Failed to load quiet spaces:', err)
                setRefuges([])
                setSelectedId(null)
            } finally {
                setLoading(false)
            }
        }
        load()
    }, [radiusKm, userLocation, locationLoading])

    const filtered = refuges
        .filter((r) => filter === 'all' || r.type === filter)
        .sort((a, b) => {
            if (sortBy === 'distance') {
                // real data has no distanceM yet — fall back to walkMinutes
                const aVal = a.distanceM ?? a.walkMinutes
                const bVal = b.distanceM ?? b.walkMinutes
                return aVal - bVal
            }
            return (b.sensoryScore ?? 0) - (a.sensoryScore ?? 0)
        })
    const selectedRefuge = refuges.find((r) => r.id === selectedId) ?? null
    return (
        <>
            <div className="HeaderContainer">
                <div className="FeatureHeader">
                    <div className="FeatureTitle">
                        <h2>Quiet Spaces</h2>
                        <p>Sensory refuges nearby</p>
                    </div>
                    <p>SenseWay /<span> Quiet Spaces</span></p>
                </div>
            </div>

            <div className={styles.content}>
                <div className={styles.banner}>
                    <div className={styles.bannerLeft}>
                        <span className={styles.bannerIcon}>♡</span>
                        <div>
                            <p className={styles.bannerTitle}>{refuges.length} sensory refuges nearby</p>
                            <p className={styles.bannerSubtitle}>
                                These are verified calm spaces — parks, libraries, and quiet indoor areas — where you can rest and decompress. Data sourced from City of Melbourne open datasets.
                            </p>
                        </div>
                    </div>
                    <div className={styles.radiusRow}>
                        <div className={styles.radiusHeader}>
                            <span className={styles.radiusLabel}>Search radius</span>
                            <span className={styles.radiusValue}> {radiusKm} km</span>
                        </div>
                        <input
                            type="range"
                            min={0.5}
                            max={10}
                            step={0.5}
                            value={radiusKm}
                            onChange={(e) => setRadiusKm(Number(e.target.value))}
                            className={styles.radiusSlider}
                        />
                        <div className={styles.radiusRange}>
                            <span>0.5 km</span>
                            <span>10 km</span>
                        </div>
                    </div>
                </div>

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

                <div className={styles.layout}>
                    <div className={styles.listColumn}>
                        {filtered.map((refuge) => {
                            const typeCfg = TYPE_CONFIG[refuge.type]
                            const isSelected = selectedId === refuge.id
                            return (
                                <button
                                    key={refuge.id}
                                    className={`${styles.refugeCard} ${isSelected ? styles.refugeCardSelected : ''}`}
                                    onClick={() => handleSelectRefuge(refuge.id)}
                                >
                                    {refuge.sensoryScore != null && <SensoryRing score={refuge.sensoryScore} />}
                                    <div className={styles.refugeCardBody}>
                                        <div className={styles.refugeTagsRow}>
                                            <span className={styles.typeTag} style={{ backgroundColor: typeCfg.bg, color: typeCfg.color }}>
                                                {typeCfg.label}
                                            </span>
                                            {refuge.sunflower && <span className={styles.sunflowerTag}>🌻 Sunflower</span>}
                                            {refuge.crowdLevel === 'low' && <span className={styles.quietTag}>Quiet now</span>}
                                        </div>
                                        <p className={styles.refugeName}>{refuge.name}</p>
                                        {refuge.address && <p className={styles.refugeAddress}>{refuge.address}</p>}
                                        <p className={styles.refugeMeta}>
                                            <strong>{refuge.walkMinutes} min walk</strong>
                                            {refuge.distanceM != null && <> · {refuge.distanceM}m</>}
                                        </p>
                                    </div>
                                </button>
                            )
                        })}
                    </div>

                    <div className={styles.detailColumn} ref={detailColumnRef}>
                        {selectedRefuge && (
                            <div className={styles.detailPanel}>
                                <div className={styles.detailHeader}>
                                    <div>
                                        <div className={styles.detailTagsRow}>
                                            <span
                                                className={styles.typeTag}
                                                style={{
                                                    backgroundColor: TYPE_CONFIG[selectedRefuge.type].bg,
                                                    color: TYPE_CONFIG[selectedRefuge.type].color,
                                                }}
                                            >
                                                {TYPE_CONFIG[selectedRefuge.type].label}
                                            </span>
                                            {selectedRefuge.sunflower && <span className={styles.sunflowerTag}>🌻 Sunflower partner</span>}
                                            {selectedRefuge.crowdLevel === 'low' && <span className={styles.quietTag}>Quiet right now</span>}
                                        </div>
                                        <h3 className={styles.detailName}>{selectedRefuge.name}</h3>
                                        {selectedRefuge.address && (
                                            <p className={styles.detailAddress}>
                                                {selectedRefuge.address}
                                            </p>
                                        )}
                                    </div>
                                    {selectedRefuge.sensoryScore != null && <SensoryRing score={selectedRefuge.sensoryScore} />}
                                </div>

                                <div className={styles.statsRow}>
                                    <div>
                                        <p className={styles.statLabel}>Walk time</p>
                                        <p className={styles.statValue}>{selectedRefuge.walkMinutes} min</p>
                                    </div>
                                    {selectedRefuge.distanceM != null && (
                                        <div>
                                            <p className={styles.statLabel}>Distance</p>
                                            <p className={styles.statValue}>{selectedRefuge.distanceM}m</p>
                                        </div>
                                    )}
                                    {selectedRefuge.sensoryScore != null && (
                                        <div>
                                            <p className={styles.statLabel}>Calm score</p>
                                            <p className={styles.statValue}>{selectedRefuge.sensoryScore}/100</p>
                                        </div>
                                    )}
                                </div>

                                {selectedRefuge.hours && (
                                    <div>
                                        <p className={styles.sectionLabel}>Opening Hours</p>
                                        <p className={styles.hoursText}>{selectedRefuge.hours}</p>
                                    </div>
                                )}

                                {selectedRefuge.features.length > 0 && (
                                    <div>
                                        <p className={styles.sectionLabel}>Sensory Features</p>
                                        <div className={styles.featuresRow}>
                                            {selectedRefuge.features.map((f) => (
                                                <span key={f} className={styles.featureTag}>{f}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                <button
                                    onClick={() => 
                                        onNavigate('routes', selectedRefuge.name, {
                                            lat: selectedRefuge.lat,
                                            lng: selectedRefuge.lng,
                                        })
                                    }
                                    className={styles.navigateButton}
                                >
                                    Navigate to {selectedRefuge.name} →
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                <div className={styles.sunflowerStrip}>
                    <span className={styles.sunflowerEmoji}>🌻</span>
                    <div>
                        <p className={styles.sunflowerTitle}>Hidden Disabilities Sunflower Scheme</p>
                        <p className={styles.sunflowerText}>
                            Partner venues are trained to assist people with hidden disabilities. Ask for a sunflower lanyard at reception — no explanation required.
                        </p>
                    </div>
                </div>
            </div>
        </>
    )
}