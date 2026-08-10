import RouteCard from './RouteCard'
import styles from './RouteList.module.css'

export default function RouteList({ routes, selectedRouteId, onSelectRoute }) {
    return (
        <div className={styles.wrapper}>
            <p className={styles.count}>{routes.length} ROUTES FOUND</p>
            <div className={styles.list}>
                {routes.map((route) => (
                <RouteCard
                    key={route.id}
                    route={route}
                    isSelected={route.id === selectedRouteId}
                    onSelect={onSelectRoute}
                />
                ))}
            </div>
        </div>
    )
}