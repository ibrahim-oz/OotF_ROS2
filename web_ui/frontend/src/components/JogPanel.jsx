/* ── JogPanel.jsx ── */
//web_ui/frontend/src/components/JogPanel.jsx
import { useState } from 'react'

const JOINTS = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6']
const JOINT_STEPS = [0.5, 1, 5, 10]
const CART_AXES = ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']
const CART_STEPS = [0.5, 1, 5, 10]

async function jogJoint(joint, delta, vel, acc) {
    return fetch('/api/jog/joint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ joint, delta, vel, acc }),
    }).then(r => r.json())
}

export default function JogPanel({ joints, ros }) {
    const [jStep, setJStep] = useState(1)
    const [cStep, setCStep] = useState(1)
    const [vel, setVel] = useState(20)
    const [acc, setAcc] = useState(40)
    const [busy, setBusy] = useState(false)
    const [lastMsg, setMsg] = useState('')

    const doJog = async (joint, sign) => {
        if (busy || !ros) return
        setBusy(true)
        const res = await jogJoint(joint, sign * jStep, vel, acc)
        setMsg(res.success ? `✔ J${joint + 1} jogged ${sign > 0 ? '+' : ''}${sign * jStep}°` : `✘ ${res.error || 'Failed'}`)
        setBusy(false)
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* ── Settings Bar ── */}
            <div className="card" style={{ padding: '14px 18px' }}>
                <div style={{ display: 'flex', gap: 28, alignItems: 'center', flexWrap: 'wrap' }}>
                    <div>
                        <span className="card-title" style={{ marginBottom: 6 }}>Joint Step</span>
                        <div style={{ display: 'flex', gap: 6 }}>
                            {JOINT_STEPS.map(s => (
                                <button key={s} className={`btn btn-secondary ${jStep === s ? 'active' : ''}`}
                                    style={{ width: 56, padding: '6px 0', ...(jStep === s ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}) }}
                                    onClick={() => setJStep(s)}>{s}°
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <span className="card-title" style={{ marginBottom: 6 }}>Velocity</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <input type="range" min={1} max={100} value={vel} onChange={e => setVel(+e.target.value)}
                                style={{ width: 100 }} />
                            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{vel} °/s</span>
                        </div>
                    </div>
                    {lastMsg && <div style={{ marginLeft: 'auto', fontSize: '0.8rem', color: lastMsg.startsWith('✔') ? 'var(--success)' : 'var(--danger)' }}>{lastMsg}</div>}
                </div>
            </div>

            {/* ── Joint Jog ── */}
            <div className="card">
                <div className="card-title">Joint Jog</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
                    {JOINTS.map((name, i) => (
                        <div key={name} style={{ background: 'var(--bg-card2)', borderRadius: 8, padding: 14, border: '1px solid var(--border)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{name}</span>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-2)', fontVariantNumeric: 'tabular-nums' }}>
                                    {(joints[i] ?? 0).toFixed(1)}°
                                </span>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                                <button className="btn btn-secondary" style={{ flex: 1, padding: '8px 0', fontSize: '1.1rem' }}
                                    onClick={() => doJog(i, -1)} disabled={!ros || busy}>−</button>
                                <button className="btn btn-secondary" style={{ flex: 1, padding: '8px 0', fontSize: '1.1rem' }}
                                    onClick={() => doJog(i, 1)} disabled={!ros || busy}>+</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
