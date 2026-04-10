/* ── IOPanel.jsx  v4 ── */
/* Optimistic updates: SET works, GET is unreliable (Doosan ROS service issue).
   After toggle, we locally update the value immediately. */
import { useState, useEffect, useCallback, useRef } from 'react'

function Signal({ label, type, index, rawValue, onToggle, ros }) {
    const unk = rawValue === -1
    const isOne = rawValue === 1 // Normal UI convention: 1 = ON, 0 = OFF

    return (
        <div style={{
            background: 'var(--bg-card2)',
            border: `1px solid ${isOne ? '#10b98133' : 'var(--border)'}`,
            borderLeft: `4px solid ${isOne ? '#10b981' : unk ? 'var(--text-3)' : '#ef4444'}`,
            borderRadius: 8, padding: '10px 12px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            gap: 8,
        }}>
            <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', fontWeight: 600 }}>
                    {type} {index}
                </div>
                <div style={{ fontSize: '0.82rem', fontWeight: 500, color: 'var(--text-1)' }}>{label}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: unk ? '#4b5563' : isOne ? '#10b981' : '#ef4444',
                    boxShadow: isOne ? '0 0 6px #10b981' : 'none',
                    transition: 'all 0.2s',
                }} />
                <span style={{
                    fontSize: '0.8rem', fontWeight: 700, fontFamily: 'monospace',
                    color: unk ? 'var(--text-3)' : isOne ? '#10b981' : '#ef4444'
                }}>
                    {unk ? '?' : rawValue}
                </span>
                {onToggle && (
                    <button
                        className="btn btn-secondary"
                        style={{ padding: '4px 12px', fontSize: '0.75rem', opacity: !ros ? 0.4 : 1 }}
                        onClick={() => onToggle(index, rawValue === 1 ? 0 : 1)}
                        disabled={!ros || unk}
                    >
                        → {rawValue === 1 ? 'TURN OFF' : 'TURN ON'}
                    </button>
                )}
            </div>
        </div>
    )
}

export default function IOPanel({ ros }) {
    const [inputs, setInputs] = useState(Array(16).fill(-1))
    const [outputs, setOutputs] = useState(Array(16).fill(-1))
    const [loading, setLoading] = useState(true)
    const [msg, setMsg] = useState('')
    // Track which DO pins we've set locally (overrides unreliable GET)
    const localOverrides = useRef({})

    const refresh = useCallback(async (isInitial = false) => {
        if (!isInitial) setLoading(true)
        try {
            const r = await fetch('/api/io/digital/all').then(r => r.json())
            if (r.success) {
                setInputs(r.inputs)

                // Apply local overrides on top of GET data
                const merged = r.outputs.map((serverVal, i) => {
                    const pinIdx = i + 1
                    if (localOverrides.current[pinIdx] !== undefined) {
                        return localOverrides.current[pinIdx]
                    }
                    return serverVal
                })
                setOutputs(merged)
            }
            else setMsg('Failed to read I/O')
        } catch { setMsg('Backend unreachable') }
        setLoading(false)
    }, [])

    useEffect(() => {
        const initTimer = setTimeout(() => refresh(true), 500);
        return () => clearTimeout(initTimer);
    }, [refresh])
    useEffect(() => {
        const t = setInterval(() => refresh(false), 2000)
        return () => clearInterval(t)
    }, [refresh])

    const toggle = async (idx1based, newRawValue) => {
        console.log(`[IO v4] DO${idx1based} → raw ${newRawValue}`)

        // OPTIMISTIC UPDATE: immediately show the new value in UI
        localOverrides.current[idx1based] = newRawValue
        setOutputs(prev => {
            const copy = [...prev]
            copy[idx1based - 1] = newRawValue
            return copy
        })

        try {
            const r = await fetch(`/api/io/raw_set/${idx1based}/${newRawValue}`).then(r => r.json())
            if (r.set_success) {
                setMsg(`✔ DO${idx1based} → ${newRawValue}`)
            } else {
                setMsg(`✘ DO${idx1based} failed`)
                // Revert optimistic update on failure
                delete localOverrides.current[idx1based]
            }
        } catch (e) {
            setMsg(`✘ Error: ${e.message}`)
            delete localOverrides.current[idx1based]
        }

        // Local override stays permanently - GET is unreliable for DO
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <button className="btn btn-secondary" style={{ padding: '7px 18px' }} onClick={refresh} disabled={loading}>
                    {loading ? '⏳' : '🔄'} Refresh
                </button>
                {msg && <span style={{ fontSize: '0.82rem', color: msg.startsWith('✔') ? 'var(--success)' : 'var(--danger)' }}>{msg}</span>}
                <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-3)' }}>
                    Raw values · v4
                </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <div className="card">
                    <div className="card-title">Digital Inputs (DI 1–16) — Read Only</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {inputs.map((v, i) => (
                            <Signal key={i} label={`Digital Input ${i + 1}`} rawValue={v}
                                type="DI" index={i + 1} ros={ros} />
                        ))}
                    </div>
                </div>

                <div className="card">
                    <div className="card-title">Digital Outputs (DO 1–16) — Read/Write</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {outputs.map((v, i) => (
                            <Signal key={i} label={`Digital Output ${i + 1}`} rawValue={v}
                                type="DO" index={i + 1} onToggle={toggle} ros={ros} />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
