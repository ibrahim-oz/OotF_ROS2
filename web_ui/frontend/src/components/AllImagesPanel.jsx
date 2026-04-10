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

export default function AllImagesPanel() {
    const [folders, setFolders] = useState([])
    const [selectedFolder, setSelectedFolder] = useState('')
    const [images, setImages] = useState([])
    const [selected, setSelected] = useState(null)
    const [zoom, setZoom] = useState(100)
    const [loadingFolders, setLoadingFolders] = useState(true)
    const [loadingImages, setLoadingImages] = useState(false)
    const [error, setError] = useState('')
    const [directory, setDirectory] = useState('')
    const [naturalSize, setNaturalSize] = useState(null)
    const [sortBy, setSortBy] = useState('date')
    const [sortDir, setSortDir] = useState('desc')

    useEffect(() => { setNaturalSize(null) }, [selected?.relative_path, selected?.name, selectedFolder])

    const loadFolders = async () => {
        setLoadingFolders(true)
        setError('')
        try {
            const r = await fetch('/api/all-images/folders')
            const d = await r.json()
            if (!d.success) {
                setError(d.error || 'Failed to load folders')
                setFolders([])
                setSelectedFolder('')
                setImages([])
                setSelected(null)
                return
            }

            setDirectory(d.directory || '')
            setFolders(d.folders || [])
            setSelectedFolder((prev) => {
                if (prev && (d.folders || []).includes(prev)) return prev
                return d.folders?.[0] || ''
            })
        } catch (err) {
            setError(err.message || 'Failed to load folders')
        } finally {
            setLoadingFolders(false)
        }
    }

    const loadFolderImages = async (folderName) => {
        if (!folderName) {
            setImages([])
            setSelected(null)
            return
        }

        setLoadingImages(true)
        setError('')
        try {
            const r = await fetch(`/api/all-images/folder/${encodeURIComponent(folderName)}`)
            const d = await r.json()
            if (!d.success) {
                setError(d.error || 'Failed to load images')
                setImages([])
                setSelected(null)
                return
            }

            setImages(d.images || [])
            setSelected((prev) => {
                if (prev && (d.images || []).some((item) => item.relative_path === prev.relative_path && item.folder === prev.folder)) {
                    return d.images.find((item) => item.relative_path === prev.relative_path && item.folder === prev.folder)
                }
                return d.images?.[0] || null
            })
        } catch (err) {
            setError(err.message || 'Failed to load images')
            setImages([])
            setSelected(null)
        } finally {
            setLoadingImages(false)
        }
    }

    useEffect(() => {
        loadFolders()
    }, [])

    useEffect(() => {
        loadFolderImages(selectedFolder)
    }, [selectedFolder])

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
        () => sortedImages.findIndex((item) => item.relative_path === selected?.relative_path && item.folder === selected?.folder),
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
        <div style={{ display: 'grid', gridTemplateColumns: '240px 320px minmax(0, 1fr)', gap: 16, minHeight: 'calc(90vh - 120px)', width: '100%' }}>
            <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div className="card-title" style={{ marginBottom: 4 }}>All Images</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-3)' }}>
                            Browse mounted image folders.
                        </div>
                    </div>
                    <button className="btn btn-secondary" style={{ padding: '7px 14px', fontSize: '0.84rem' }} onClick={loadFolders} disabled={loadingFolders}>
                        {loadingFolders ? '⏳' : 'Refresh'}
                    </button>
                </div>

                <div style={{ fontSize: '0.76rem', color: 'var(--text-3)', wordBreak: 'break-all' }}>
                    {directory || '/mnt/affix_all_images'}
                </div>

                {error && (
                    <div style={{ color: 'var(--danger)', fontSize: '0.82rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: 10 }}>
                        {error}
                    </div>
                )}

                {!loadingFolders && folders.length === 0 && !error && (
                    <div style={{ color: 'var(--text-3)', fontSize: '0.84rem' }}>
                        No folders found.
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', paddingRight: 4 }}>
                    {folders.map((folder) => (
                        <button
                            key={folder}
                            onClick={() => setSelectedFolder(folder)}
                            style={{
                                textAlign: 'left',
                                padding: '9px 11px',
                                borderRadius: 8,
                                border: selectedFolder === folder ? '1px solid var(--accent)' : '1px solid var(--border)',
                                background: selectedFolder === folder ? 'rgba(244,70,11,0.08)' : 'var(--bg-card2)',
                                cursor: 'pointer',
                                color: 'inherit'
                            }}
                        >
                            {folder}
                        </button>
                    ))}
                </div>
            </div>

            <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                    <div>
                        <div className="card-title" style={{ marginBottom: 4 }}>{selectedFolder || 'Folder'}</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-3)' }}>
                            {selectedFolder ? `${sortedImages.length} images` : 'Select a folder.'}
                        </div>
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

                {!loadingImages && sortedImages.length === 0 && selectedFolder && !error && (
                    <div style={{ color: 'var(--text-3)', fontSize: '0.84rem' }}>
                        No images in this folder.
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', paddingRight: 4, maxHeight: 'calc(90vh - 220px)' }}>
                    {sortedImages.map((item) => (
                        <button
                            key={`${item.folder}-${item.relative_path || item.name}`}
                            onClick={() => setSelected(item)}
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '64px minmax(0, 1fr)',
                                gap: 9,
                                alignItems: 'center',
                                textAlign: 'left',
                                padding: 9,
                                borderRadius: 8,
                                border: selected?.relative_path === item.relative_path && selected?.folder === item.folder ? '1px solid var(--accent)' : '1px solid var(--border)',
                                background: selected?.relative_path === item.relative_path && selected?.folder === item.folder ? 'rgba(244,70,11,0.08)' : 'var(--bg-card2)',
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
                                    {item.subfolder ? `${item.subfolder} · ` : ''}{formatBytes(item.size)}
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
                            {selectedInfo ? `${selectedInfo.folder}${selectedInfo.subfolder ? `/${selectedInfo.subfolder}` : ''} · ${selectedInfo.sizeText} · ${selectedInfo.modified}` : 'Select an image to inspect it.'}
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
