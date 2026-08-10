import L from 'leaflet'

import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import styles from './RouteMap.module.css'

const defaultIcon = L.icon({
    iconUrl: markerIcon,
    iconRetinaUrl: markerIcon2x,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
})

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
                <Marker position={start} icon={defaultIcon}>
                    <Popup>Start</Popup>
                </Marker>
                <Marker position={end} icon={defaultIcon}>
                    <Popup>{route.name}</Popup>
                </Marker>
            </MapContainer>
        </div>
    )
}