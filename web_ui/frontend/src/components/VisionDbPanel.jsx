import { useEffect, useState } from 'react'

export default function VisionDbPanel() {
    const [status, setStatus] = useState(null)
    const [tables, setTables] = useState([])
    const [selectedTable, setSelectedTable] = useState('')
    const [columns, setColumns] = useState([])
    const [rows, setRows] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [loadingRows, setLoadingRows] = useState(false)
    const [error, setError] = useState('')

    const loadStatusAndTables = async () => {
        setLoading(true)
        setError('')
        try {
            const [statusResp, tablesResp] = await Promise.all([
                fetch('/api/vision/db/status'),
                fetch('/api/vision/db/tables'),
            ])
            const statusData = await statusResp.json()
            const tablesData = await tablesResp.json()

            setStatus(statusData)
            if (!tablesData.success) {
                setTables([])
                setSelectedTable('')
                setColumns([])
                setRows([])
                setTotal(0)
                setError(tablesData.error || 'Vision DB could not be loaded')
                return
            }

            setTables(tablesData.tables || [])
            setSelectedTable((prev) => {
                if (prev && (tablesData.tables || []).includes(prev)) return prev
                return tablesData.tables?.[0] || ''
            })
        } catch (err) {
            setError(err.message || 'Vision DB could not be loaded')
        } finally {
            setLoading(false)
        }
    }

    const loadRows = async (tableName) => {
        if (!tableName) {
            setColumns([])
            setRows([])
            setTotal(0)
            return
        }

        setLoadingRows(true)
        setError('')
        try {
            const r = await fetch(`/api/vision/db/table/${encodeURIComponent(tableName)}?limit=200`)
            const d = await r.json()
            if (!d.success) {
                setColumns([])
                setRows([])
                setTotal(0)
                setError(d.error || `Failed to load table ${tableName}`)
                return
            }

            setColumns(d.columns || [])
            setRows(d.rows || [])
            setTotal(d.total || 0)
        } catch (err) {
            setError(err.message || `Failed to load table ${tableName}`)
        } finally {
            setLoadingRows(false)
        }
    }

    useEffect(() => {
        loadStatusAndTables()
    }, [])

    useEffect(() => {
        loadRows(selectedTable)
    }, [selectedTable])

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '300px minmax(0, 1fr)', gap: 20, minHeight: 620 }}>
            <div className="card" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div className="card-title" style={{ marginBottom: 4 }}>Vision DB</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-3)' }}>
                            SQLite tables from the shared Windows database.
                        </div>
                    </div>
                    <button className="btn btn-secondary" style={{ padding: '7px 14px', fontSize: '0.84rem' }} onClick={loadStatusAndTables} disabled={loading}>
                        {loading ? '⏳' : 'Refresh'}
                    </button>
                </div>

                <div style={{ fontSize: '0.8rem', color: status?.success ? 'var(--success)' : 'var(--warning)' }}>
                    {status?.success ? 'DB connected' : 'DB not mounted yet'}
                </div>

                <div style={{ fontSize: '0.76rem', color: 'var(--text-3)', wordBreak: 'break-all' }}>
                    {status?.path || status?.candidates?.[0] || '/mnt/affix_db/Buffer.db'}
                </div>

                {error && (
                    <div style={{ color: 'var(--danger)', fontSize: '0.82rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: 10 }}>
                        {error}
                    </div>
                )}

                <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
                    {tables.length === 0 && !loading && (
                        <div style={{ color: 'var(--text-3)', fontSize: '0.84rem' }}>
                            No tables found.
                        </div>
                    )}

                    {tables.map((table) => (
                        <button
                            key={table}
                            className="btn btn-secondary"
                            onClick={() => setSelectedTable(table)}
                            style={{
                                justifyContent: 'flex-start',
                                padding: '10px 12px',
                                border: selectedTable === table ? '1px solid var(--accent)' : '1px solid var(--border)',
                                background: selectedTable === table ? 'rgba(244,70,11,0.08)' : 'var(--bg-card2)',
                            }}
                        >
                            {table}
                        </button>
                    ))}
                </div>
            </div>

            <div className="card" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div>
                        <div className="card-title" style={{ marginBottom: 4 }}>{selectedTable || 'Table Preview'}</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-3)' }}>
                            {selectedTable ? `${rows.length} rows loaded${total ? ` of ${total}` : ''}` : 'Select a table to inspect rows.'}
                        </div>
                    </div>
                    {selectedTable && (
                        <button className="btn btn-secondary" style={{ padding: '8px 14px' }} onClick={() => loadRows(selectedTable)} disabled={loadingRows}>
                            {loadingRows ? '⏳ Loading...' : 'Reload Rows'}
                        </button>
                    )}
                </div>

                <div style={{
                    flex: 1,
                    minHeight: 320,
                    background: 'linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    overflow: 'auto',
                }}>
                    {!selectedTable ? (
                        <div style={{ color: 'var(--text-3)', fontSize: '0.86rem', padding: 18 }}>
                            No table selected.
                        </div>
                    ) : columns.length === 0 && !loadingRows ? (
                        <div style={{ color: 'var(--text-3)', fontSize: '0.86rem', padding: 18 }}>
                            No rows available.
                        </div>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                                <tr>
                                    {columns.map((column) => (
                                        <th
                                            key={column}
                                            style={{
                                                textAlign: 'left',
                                                padding: '10px 12px',
                                                borderBottom: '1px solid var(--border)',
                                                whiteSpace: 'nowrap',
                                            }}
                                        >
                                            {column}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((row, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-light)' }}>
                                        {columns.map((column) => (
                                            <td
                                                key={`${idx}-${column}`}
                                                style={{
                                                    padding: '9px 12px',
                                                    color: 'var(--text-2)',
                                                    verticalAlign: 'top',
                                                    whiteSpace: 'nowrap',
                                                }}
                                            >
                                                {row[column] == null ? '' : String(row[column])}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    )
}
