/* ── TcpPanel.jsx ── */
export default function TcpPanel({ tcp }) {
    const fields = [
        { key: 'x', label: 'X', unit: 'mm', color: '#f4460b' },
        { key: 'y', label: 'Y', unit: 'mm', color: '#2f5667' },
        { key: 'z', label: 'Z', unit: 'mm', color: '#7a9fad' },
        { key: 'rx', label: 'Rx', unit: '°', color: '#c0340a' },
        { key: 'ry', label: 'Ry', unit: '°', color: '#4a7f94' },
        { key: 'rz', label: 'Rz', unit: '°', color: '#94a3b8' },
    ]

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div className="card">
                <div className="card-title">TCP Position (Tool Center Point)</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
                    {fields.map(({ key, label, unit, color }) => (
                        <div key={key} style={{
                            background: 'var(--bg-card2)',
                            border: `1px solid ${color}22`,
                            borderLeft: `3px solid ${color}`,
                            borderRadius: 8,
                            padding: '16px 18px',
                        }}>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontWeight: 600, marginBottom: 6, letterSpacing: '0.08em' }}>{label}</div>
                            <div style={{ fontSize: '1.8rem', fontWeight: 700, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums', lineHeight: 1, color }}>
                                {tcp?.[key] != null ? tcp[key].toFixed(2) : '—'}
                            </div>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 4 }}>{unit}</div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="card" style={{ padding: '14px 18px' }}>
                <div className="card-title">Reference Frame</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>
                    Base (DR_BASE) — values are in <strong style={{ color: 'var(--text-1)' }}>mm</strong> and <strong style={{ color: 'var(--text-1)' }}>degrees</strong>.<br />
                    Updated at ~10 Hz via <code style={{ color: 'var(--accent)' }}>/aux_control/get_current_posx</code>.
                </div>
            </div>
        </div>
    )
}
