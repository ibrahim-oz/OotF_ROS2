import { useState, useEffect } from 'react'

export default function UserFramesPanel({ ros }) {
    const [frames, setFrames] = useState({})
    const [editingId, setEditingId] = useState(null)
    const [editForm, setEditForm] = useState({ name: '', pos: [0, 0, 0, 0, 0, 0] })
    const [msg, setMsg] = useState('')

    const fetchFrames = async () => {
        try {
            const r = await fetch('/api/userframes')
            const d = await r.json()
            if (d.success) setFrames(d.frames)
        } catch { }
    }

    useEffect(() => { fetchFrames() }, [])

    const handleSave = async () => {
        setMsg('Saving...')
        try {
            const r = await fetch('/api/userframes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: editingId,
                    name: editForm.name,
                    pos: editForm.pos.map(Number)
                })
            })
            const d = await r.json()
            if (d.success) {
                setMsg('✔ Saved')
                setEditingId(null)
                fetchFrames()
            } else setMsg('✘ Save failed')
        } catch { setMsg('✘ Error') }
        setTimeout(() => setMsg(''), 3000)
    }

    const startEdit = (id) => {
        const frame = frames[id] || { name: `Frame ${id}`, pos: [0, 0, 0, 0, 0, 0] }
        setEditingId(id)
        setEditForm({ name: frame.name || `Frame ${id}`, pos: [...frame.pos] })
        setMsg('')
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) 2fr', gap: 20 }}>
            {/* Left Column: Editor */}
            <div className="card" style={{ alignSelf: 'start' }}>
                <div className="card-title">Edit User Frame</div>
                {editingId ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-3)' }}>Editing Frame ID: <strong style={{ color: 'var(--accent)' }}>{editingId}</strong></div>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.85rem', color: 'var(--text-2)' }}>
                            Name/Alias
                            <input
                                type="text"
                                className="input-field"
                                value={editForm.name}
                                onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                            />
                        </label>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                            {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((k, i) => (
                                <label key={k} style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.85rem', color: 'var(--text-2)' }}>
                                    {k} {i < 3 ? '(mm)' : '(deg)'}
                                    <input
                                        type="number" step="0.1"
                                        className="input-field"
                                        style={{ fontFamily: 'monospace' }}
                                        value={editForm.pos[i]}
                                        onChange={e => {
                                            const newPos = [...editForm.pos]
                                            newPos[i] = e.target.value
                                            setEditForm(f => ({ ...f, pos: newPos }))
                                        }}
                                    />
                                </label>
                            ))}
                        </div>

                        <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                            <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleSave}>Save Frame</button>
                            <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setEditingId(null)}>Cancel</button>
                        </div>
                        {msg && <div style={{ fontSize: '0.85rem', color: msg.includes('✔') ? 'var(--success)' : 'var(--danger)', textAlign: 'center' }}>{msg}</div>}
                    </div>
                ) : (
                    <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: '0.9rem' }}>
                        Select a frame from the list on the right to edit its coordinate values.
                    </div>
                )}
            </div>

            {/* Right Column: List of 100 Frames */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', maxHeight: '72vh' }}>
                <div className="card-title">User Frames Index (1-100)</div>
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: '10px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                        {Array.from({ length: 100 }, (_, i) => i + 1).map(id => {
                            const frame = frames[id]
                            const name = frame ? frame.name : `Frame ${id}`
                            const hasData = !!frame
                            return (
                                <div key={id} onClick={() => startEdit(id)} style={{
                                    background: editingId === id ? 'var(--bg-card)' : 'var(--bg-base)',
                                    border: editingId === id ? '1px solid var(--accent)' : '1px solid var(--border-light)',
                                    borderRadius: 6, padding: '10px 14px', cursor: 'pointer',
                                    transition: 'all 0.15s',
                                    opacity: hasData ? 1 : 0.6
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                                        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: hasData ? 'var(--accent)' : 'var(--text-3)' }}>#{id}</span>
                                        <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-1)' }}>{name}</span>
                                    </div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontFamily: 'monospace', display: 'flex', gap: 8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        {hasData ? `[${frame.pos.map(v => Number(v).toFixed(1)).join(', ')}]` : '[0.0, 0.0, ... 0.0]'}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>
        </div>
    )
}
