import { useEffect, useMemo, useState } from 'react'

function formatBytes(bytes) {
    if (!bytes) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    let value = bytes
    let idx = 0
    while (value >= 1024 && idx < units.length - 1) {
        value /= 1024
        idx += 1
    }
    return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`
}

export default function ResultsPanel() {
    const [images, setImages] = useState([])
    const [selected, setSelected] = useState(null)
    const [zoom, setZoom] = useState(500)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [naturalSize, setNaturalSize] = useState(null)
    const [sortBy, setSortBy] = useState('date')
    const [sortDir, setSortDir] = useState('desc')

    useEffect(() => { setNaturalSize(null) }, [selected?.name])

    const loadImages = async () => {
        setLoading(true)
        setError('')
        try {
            const r = await fetch('/api/results/images')
            const d = await r.json()
            if (!d.success) {
                setError(d.error || 'Failed to load results')
                setImages([])
                setSelected(null)
                return
            }

            const normalized = (d.images || []).map(item => ({
                ...item,
                url: item.url || `/api/results/image/${encodeURIComponent(item.name)}`,
            }))

            setImages(normalized)
            setSelected(prev => {
                if (prev && normalized.some(item => item.name === prev.name)) {
                    return normalized.find(item => item.name === prev.name)
                }
                return normalized[0] || null
            })
        } catch (err) {
            setError(err.message || 'Failed to load results')
            setImages([])
            setSelected(null)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadImages()
    }, [])

    const selectedInfo = useMemo(() => {
        if (!selected) return null
        return {
            ...selected,
            modified: new Date(selected.mtime * 1000).toLocaleString('en-GB', { hour12: false }),
            sizeText: formatBytes(selected.size),
        }
    }, [selected])

    const sortedImages = useMemo(() => {
        const items = [...images]
        items.sort((a, b) => {
            const dir = sortDir === 'asc' ? 1 : -1
            if (sortBy === 'name') {
                return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }) * dir
            }
            return (a.mtime - b.mtime) * dir
        })
        return items
    }, [images, sortBy, sortDir])

    const selectedIndex = useMemo(
        () => sortedImages.findIndex((item) => item.name === selected?.name),
        [sortedImages, selected],
    )

    const goToImage = (direction) => {
        if (sortedImages.length === 0) return
        if (selectedIndex < 0) {
            setSelected(sortedImages[0])
            return
        }
        const nextIndex = (selectedIndex + direction + sortedImages.length) % sortedImages.length
        setSelected(sortedImages[nextIndex])
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '340px minmax(0, 1fr)', gap: 16, minHeight: 'calc(90vh - 120px)', width: '100%' }}>
            <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div className="card-title" style={{ marginBottom: 4 }}>Results</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-3)' }}>
                            Images from the mounted Windows share.
                        </div>
                    </div>
                    <button className="btn btn-secondary" style={{ padding: '7px 14px', fontSize: '0.84rem' }} onClick={loadImages} disabled={loading}>
                        {loading ? '⏳' : 'Refresh'}
                    </button>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-3)' }}>
                        {sortedImages.length} images
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'nowrap' }}>
                        <select
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value)}
                            style={{ background: 'var(--bg-base)', color: 'var(--text-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 10px', fontSize: '0.8rem' }}
                        >
                            <option value="date">Sort by Date</option>
                            <option value="name">Sort by Name</option>
                        </select>
                        <button
                            className="btn btn-secondary"
                            style={{ padding: '7px 12px', fontSize: '0.8rem' }}
                            onClick={() => setSortDir((prev) => prev === 'asc' ? 'desc' : 'asc')}
                        >
                            {sortDir === 'desc' ? 'Desc' : 'Asc'}
                        </button>
                    </div>
                </div>

                {error && (
                    <div style={{ color: 'var(--danger)', fontSize: '0.82rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: 10 }}>
                        {error}
                    </div>
                )}

                {!loading && sortedImages.length === 0 && !error && (
                    <div style={{ color: 'var(--text-3)', fontSize: '0.84rem' }}>
                        No image files found in the results directory.
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', paddingRight: 4, maxHeight: 'calc(90vh - 220px)' }}>
                    {sortedImages.map((item) => (
                        <button
                            key={item.name}
                            onClick={() => setSelected(item)}
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '64px minmax(0, 1fr)',
                                gap: 9,
                                alignItems: 'center',
                                textAlign: 'left',
                                padding: 9,
                                borderRadius: 8,
                                border: selected?.name === item.name ? '1px solid var(--accent)' : '1px solid var(--border)',
                                background: selected?.name === item.name ? 'rgba(244,70,11,0.08)' : 'var(--bg-card2)',
                                cursor: 'pointer',
                                color: 'inherit'
                            }}
                        >
                            <img
                                src={item.url}
                                alt={item.name}
                                style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 7, border: '1px solid var(--border)' }}
                            />
                            <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {item.name}
                                </div>
                                <div style={{ fontSize: '0.74rem', color: 'var(--text-3)', marginTop: 4 }}>
                                    {formatBytes(item.size)}
                                </div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 2 }}>
                                    {new Date(item.mtime * 1000).toLocaleString('en-GB', { hour12: false })}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'nowrap' }}>
                    <div style={{ minWidth: 0, flex: '1 1 auto' }}>
                        <div className="card-title" style={{ marginBottom: 4 }}>{selectedInfo ? selectedInfo.name : 'Preview'}</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {selectedInfo ? `${selectedInfo.sizeText} · ${selectedInfo.modified}` : 'Select an image to inspect it.'}
                        </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 14, flex: '0 0 auto', minWidth: 0 }}>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                            <button
                                className="btn btn-secondary"
                                style={{ padding: '8px 12px' }}
                                onClick={() => goToImage(-1)}
                                disabled={sortedImages.length === 0}
                            >
                                ←
                            </button>
                            <button
                                className="btn btn-secondary"
                                style={{ padding: '8px 12px' }}
                                onClick={() => goToImage(1)}
                                disabled={sortedImages.length === 0}
                            >
                                →
                            </button>
                        </div>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                            Zoom
                            <input
                                type="range"
                                min="25"
                                max="1000"
                                step="5"
                                value={zoom}
                                onChange={(e) => setZoom(Number(e.target.value))}
                            />
                            <span style={{ minWidth: 44, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{zoom}%</span>
                        </label>

                        {selectedInfo && (
                            <a
                                className="btn btn-primary"
                                href={selectedInfo.url}
                                download={selectedInfo.name}
                                style={{ padding: '8px 14px', textDecoration: 'none' }}
                            >
                                Save Copy
                            </a>
                        )}
                    </div>
                </div>

                <div style={{
                    flex: 1,
                    minHeight: 0,
                    maxHeight: 'calc(90vh - 190px)',
                    background: 'linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    overflow: 'auto',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 18
                }}>
                    {selectedInfo ? (
                        <div style={{
                            width: naturalSize ? naturalSize.w * (zoom / 100) : 'auto',
                            height: naturalSize ? naturalSize.h * (zoom / 100) : 'auto',
                            flexShrink: 0,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}>
                            <img
                                src={selectedInfo.url}
                                alt={selectedInfo.name}
                                onLoad={e => setNaturalSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
                                style={{
                                    width: naturalSize ? naturalSize.w : 'auto',
                                    height: naturalSize ? naturalSize.h : 'auto',
                                    maxWidth: naturalSize ? 'none' : '100%',
                                    transform: `scale(${zoom / 100})`,
                                    transformOrigin: 'center center',
                                    borderRadius: 10,
                                    boxShadow: '0 12px 30px rgba(0,0,0,0.18)'
                                }}
                            />
                        </div>
                    ) : (
                        <div style={{ color: 'var(--text-3)', fontSize: '0.86rem' }}>
                            No image selected.
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
