import { useState, useEffect } from 'react'

export default function VariablesPanel() {
    const [vars, setVars] = useState({})
    const [loading, setLoading] = useState(true)
    const [editKey, setEditKey] = useState(null)
    const [editVal, setEditVal] = useState('')
    const [newKey, setNewKey] = useState('')
    const [newVal, setNewVal] = useState('')
    const [collapsed, setCollapsed] = useState({ P: false, J: true, I: false, B: false, S: false })

    const toggleCollapse = (p) => {
        setCollapsed(prev => ({ ...prev, [p]: !prev[p] }))
    }

    const fetchVars = async () => {
        try {
            const r = await fetch('/api/variables')
            const d = await r.json()
            if (d.success) setVars(d.variables)
        } catch (e) {
            console.error('Failed to fetch variables', e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchVars()
        const t = setInterval(fetchVars, 2000)
        return () => clearInterval(t)
    }, [])

    const handleSave = async (k, v) => {
        let parsed = v;
        if (k.startsWith('B')) {
            parsed = v === 'true' || v === '1' || v === true;
        } else if (k.startsWith('I')) {
            parsed = parseInt(v, 10) || 0;
        } else if (k.startsWith('P') || k.startsWith('J')) {
            // Parse comma separated list of 6 numbers
            try {
                if (typeof v === 'string') {
                    parsed = v.replace(/[\[\]]/g, '').split(',').map(n => parseFloat(n) || 0.0);
                }
                if (!Array.isArray(parsed)) parsed = [0, 0, 0, 0, 0, 0];
                while (parsed.length < 6) parsed.push(0.0);
                parsed = parsed.slice(0, 6);
            } catch { parsed = [0, 0, 0, 0, 0, 0]; }
        } else {
            parsed = String(v); // 'S' string type
        }

        await fetch('/api/variables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: k, value: parsed })
        });
        setEditKey(null);
        fetchVars();
    }

    if (loading) return <div className="card">Loading variables...</div>

    const renderValue = (k, v) => {
        if (k.startsWith('P') || k.startsWith('J')) return `[${(v || []).map(n => Number(n).toFixed(1)).join(', ')}]`;
        if (k.startsWith('B')) return v ? 'TRUE' : 'FALSE';
        return String(v);
    };

    // Group variables by type
    const prefixes = ['P', 'J', 'I', 'B', 'S'];
    const grouped = {};
    prefixes.forEach(p => grouped[p] = Object.keys(vars).filter(k => k.startsWith(p)).sort((a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1))));

    const getTypeName = (p) => ({
        'P': 'Cartesian Poses (P)', 'J': 'Joint Poses (J)',
        'I': 'Integers (I)', 'B': 'Booleans (B)', 'S': 'Strings (S)'
    }[p]);

    return (
        <div className="card" style={{ flex: 1, maxHeight: 'calc(100vh - 120px)', overflowY: 'auto' }}>
            <div className="card-title" style={{ marginBottom: 16 }}>Robot Global Variables (GVAR)</div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                {prefixes.map(prefix => {
                    const isLongStr = prefix === 'P' || prefix === 'J' || prefix === 'S';
                    // Smaller cards for Integers/Booleans, wider for Poses/Strings
                    const gridCols = isLongStr ? 'repeat(auto-fill, minmax(220px, 1fr))' : 'repeat(auto-fill, minmax(130px, 1fr))';
                    return (
                        <div key={prefix} style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
                            {/* Header (Collapsible) */}
                            <div
                                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'rgba(255,255,255,0.03)', cursor: 'pointer', borderBottom: collapsed[prefix] ? 'none' : '1px solid var(--border)' }}
                                onClick={() => toggleCollapse(prefix)}
                            >
                                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-1)' }}>
                                    {getTypeName(prefix)} <span style={{ color: 'var(--text-3)', fontSize: '0.8rem', fontWeight: 400 }}>({grouped[prefix].length})</span>
                                </h3>
                                <div style={{ fontSize: '1.2rem', color: 'var(--text-3)', transform: collapsed[prefix] ? 'rotate(-90deg)' : 'none', transition: 'transform 0.2s' }}>
                                    ▼
                                </div>
                            </div>

                            {/* Content Grid */}
                            {!collapsed[prefix] && (
                                <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: '10px', padding: '16px' }}>
                                    {grouped[prefix].map(k => (
                                        <div key={k} style={{
                                            display: 'flex', flexDirection: 'column', gap: '6px',
                                            background: 'var(--bg-base)', border: '1px solid var(--border-light)', borderRadius: '6px', padding: '10px'
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: '0.85rem' }}>{k}</span>
                                                {editKey === k ? (
                                                    <button className="btn btn-primary" style={{ padding: '2px 8px', fontSize: '0.7rem' }} onClick={() => handleSave(k, editVal)}>Save</button>
                                                ) : (
                                                    <button className="btn" style={{ padding: '2px 8px', fontSize: '0.7rem', background: 'var(--bg-elevated)', border: '1px solid var(--border)' }} onClick={() => { setEditKey(k); setEditVal(renderValue(k, vars[k])); }}>Edit</button>
                                                )}
                                            </div>

                                            <div style={{ marginTop: '2px' }}>
                                                {editKey === k ? (
                                                    <input
                                                        type="text"
                                                        style={{
                                                            width: '100%', padding: '6px', fontSize: '0.8rem',
                                                            background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-1)', borderRadius: '4px', outline: 'none'
                                                        }}
                                                        value={editVal}
                                                        onChange={e => setEditVal(e.target.value)}
                                                        onKeyDown={e => e.key === 'Enter' && handleSave(k, editVal)}
                                                        autoFocus
                                                    />
                                                ) : (
                                                    <div style={{
                                                        fontFamily: 'monospace', color: 'var(--text-2)', fontSize: '0.85rem',
                                                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                                                    }}>
                                                        {renderValue(k, vars[k])}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
