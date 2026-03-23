import { useState, useEffect } from 'react';

const FIELDS = ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'];
const UNITS = ['mm', 'mm', 'mm', '°', '°', '°'];
const COLORS = ['#ef4444', '#22c55e', '#3b82f6', '#f97316', '#a855f7', '#06b6d4'];

const DEFAULT_OFFSET = [0, 0, 500, 0, 0, 0]; // X Y Z Rx Ry Rz

const post = (url, body) => fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
}).then(r => r.json());

function ToolCard({ name, label, isActive, offsets, onSelect, onOffsetsChange, onSave }) {
    return (
        <div className="card" style={{
            border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
            background: isActive ? '#3b82f60d' : 'var(--bg-card)',
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <div>
                    <span style={{ fontWeight: 700, fontSize: '1.1rem', color: isActive ? 'var(--accent)' : 'var(--text-1)' }}>{label}</span>
                    {isActive && <span style={{ marginLeft: 8, fontSize: '0.75rem', background: 'var(--accent)', color: '#fff', padding: '2px 8px', borderRadius: 10 }}>ACTIVE</span>}
                </div>
                {!isActive && (
                    <button className="btn btn-primary" style={{ padding: '6px 16px', fontSize: '0.8rem' }} onClick={() => onSelect(name)}>
                        Activate
                    </button>
                )}
            </div>

            {/* TCP Offset Inputs */}
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>TCP Offset</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
                {FIELDS.map((f, i) => (
                    <div key={f}>
                        <div style={{ fontSize: '0.7rem', color: COLORS[i], fontWeight: 600, marginBottom: 4, textAlign: 'center' }}>{f} <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>({UNITS[i]})</span></div>
                        <input
                            type="number" step="0.1"
                            value={offsets[i]}
                            onChange={e => { const v = [...offsets]; v[i] = e.target.value; onOffsetsChange(v); }}
                            style={{
                                width: '100%', background: 'var(--bg-base)', border: `1px solid ${COLORS[i]}33`,
                                borderRadius: 6, padding: '7px 6px', color: 'var(--text-1)', fontFamily: 'inherit',
                                fontSize: '0.85rem', textAlign: 'center', outline: 'none'
                            }}
                        />
                    </div>
                ))}
            </div>
            <button className="btn btn-secondary" style={{ marginTop: 10, padding: '6px 16px', fontSize: '0.78rem', width: '100%' }} onClick={onSave}>
                💾 Save Offsets
            </button>
        </div>
    );
}

export default function ToolsPanel() {
    const [activeTool, setActiveTool] = useState('tcp_gripper_A');
    const [offsetsA, setOffsetsA] = useState([...DEFAULT_OFFSET]);
    const [offsetsB, setOffsetsB] = useState([...DEFAULT_OFFSET]);
    const [msg, setMsg] = useState('');

    useEffect(() => {
        fetch('/api/tools/active').then(r => r.json()).then(d => {
            if (d.success) setActiveTool(d.active_tool);
        }).catch(() => { });
        fetch('/api/tools/offsets').then(r => r.json()).then(d => {
            if (d.success) {
                setOffsetsA(d.tcp_gripper_A || [...DEFAULT_OFFSET]);
                setOffsetsB(d.tcp_gripper_B || [...DEFAULT_OFFSET]);
            }
        }).catch(() => { });
    }, []);

    const flash = (text) => { setMsg(text); setTimeout(() => setMsg(''), 3000); };

    const handleSelect = async (name) => {
        const r = await post('/api/tools/active', { name });
        if (r.success) { setActiveTool(name); flash('✔ Active tool → ' + name); }
        else flash('✘ Failed');
    };

    const handleSave = async (name, offsets) => {
        const r = await post('/api/tools/offsets', { name, offsets: offsets.map(Number) });
        if (r.success) flash('✔ Offsets saved for ' + name);
        else flash('✘ Save failed');
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <ToolCard name="tcp_gripper_A" label="Tool A" isActive={activeTool === 'tcp_gripper_A'}
                    offsets={offsetsA} onSelect={handleSelect} onOffsetsChange={setOffsetsA}
                    onSave={() => handleSave('tcp_gripper_A', offsetsA)} />
                <ToolCard name="tcp_gripper_B" label="Tool B" isActive={activeTool === 'tcp_gripper_B'}
                    offsets={offsetsB} onSelect={handleSelect} onOffsetsChange={setOffsetsB}
                    onSave={() => handleSave('tcp_gripper_B', offsetsB)} />
            </div>
            {msg && <div style={{ fontSize: '0.9rem', color: msg.startsWith('✔') ? 'var(--success)' : 'var(--danger)', textAlign: 'center' }}>{msg}</div>}
        </div>
    );
}
