import { useState, useEffect } from 'react';

const FIELDS = ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'];
const UNITS = ['mm', 'mm', 'mm', '°', '°', '°'];
const COLORS = ['#f4460b', '#2f5667', '#7a9fad', '#c0340a', '#4a7f94', '#94a3b8'];

const DEFAULT_OFFSET = [0, 0, 500, 0, 0, 0]; // X Y Z Rx Ry Rz

function ToolCard({ name, label, isActive, offsets }) {
    return (
        <div className="card" style={{
            border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: isActive ? 'rgba(244,70,11,0.07)' : 'var(--bg-card)',
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <div>
                    <span style={{ fontWeight: 700, fontSize: '1.1rem', color: isActive ? 'var(--accent)' : 'var(--text-1)' }}>{label}</span>
                    {isActive && <span style={{ marginLeft: 8, fontSize: '0.75rem', background: 'var(--accent)', color: '#fff', padding: '2px 8px', borderRadius: 10 }}>ACTIVE</span>}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{name}</div>
            </div>

            {/* TCP Offset Inputs */}
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>TCP Offset</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
                {FIELDS.map((f, i) => (
                    <div key={f}>
                        <div style={{ fontSize: '0.7rem', color: COLORS[i], fontWeight: 600, marginBottom: 4, textAlign: 'center' }}>{f} <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>({UNITS[i]})</span></div>
                        <input
                            type="number" step="0.1"
                            value={offsets[i] != null ? offsets[i] : 0}
                            readOnly
                            style={{
                                width: '100%', background: 'var(--bg-card2)', border: `1px solid ${COLORS[i]}33`,
                                borderRadius: 6, padding: '7px 6px', color: 'var(--text-2)', fontFamily: 'inherit',
                                fontSize: '0.85rem', textAlign: 'center', outline: 'none', cursor: 'default'
                            }}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function ToolsPanel({ currentTool }) {
    const [offsetsA, setOffsetsA] = useState([...DEFAULT_OFFSET]);
    const [offsetsB, setOffsetsB] = useState([...DEFAULT_OFFSET]);

    useEffect(() => {
        // Fetch offsets for display
        fetch('/api/tools/offsets').then(r => r.json()).then(d => {
            if (d.success) {
                setOffsetsA(d.tcp_gripper_A || [...DEFAULT_OFFSET]);
                setOffsetsB(d.tcp_gripper_B || [...DEFAULT_OFFSET]);
            }
        }).catch(() => { });
    }, []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: '0 4px', marginBottom: -4, fontSize: '0.85rem', color: 'var(--text-3)' }}>
                These tools and their offsets are configured on the robot. They are displayed here in read-only mode for monitoring.
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <ToolCard name="tcp_gripper_A" label="Tool A" isActive={currentTool === 'tcp_gripper_A'} offsets={offsetsA} />
            </div>
        </div>
    );
}
