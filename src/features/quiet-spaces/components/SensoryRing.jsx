export default function SensoryRing({ score }) {
    const color = score >= 85 ? '#5d9c6e' : score >= 70 ? '#e8a020' : '#d94f4f'
    const r = 20, cx = 26, cy = 26
    const circ = 2 * Math.PI * r
    const offset = circ - (score / 100) * circ

    return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
        <svg width="52" height="52" viewBox="0 0 52 52">
            <circle cx={cx} cy={cy} r={r} fill="none" stroke="#e0f4fb" strokeWidth="5" />
            <circle
            cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="5"
            strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cy})`}
            style={{ transition: 'stroke-dashoffset 400ms ease' }}
            />
            <text x={cx} y={cy + 4} textAnchor="middle" fontSize="11" fontWeight="700" fill="#0d3d4f">
            {score}
            </text>
        </svg>
        <p style={{ margin: 0, fontSize: '0.5625rem', color: '#2dd4bf', fontWeight: 500 }}>calm score</p>
        </div>
    )
}