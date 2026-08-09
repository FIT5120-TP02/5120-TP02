import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import styles from './RouteMap.module.css'

export default function RouteMap({ route }) {
    if (!route?.geometry || route.geometry.length === 0) return null

    const positions = route.geometry // already [lat, lng] pairs
    const start = positions[0]
    const end = positions[positions.length - 1]

    return (
        <div className={styles.mapWrapper}>
            <MapContainer
                center={start}
                zoom={15}
                scrollWheelZoom={false}
                className={styles.map}
            >
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                <Polyline positions={positions} pathOptions={{ color: '#115e59', weight: 4 }} />
                <Marker position={start}>
                    <Popup>Start</Popup>
                </Marker>
                <Marker position={end}>
                    <Popup>{route.name}</Popup>
                </Marker>
            </MapContainer>
        </div>
    )
}