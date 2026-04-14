import { useState, useRef, useEffect } from 'react'
import ViewerPanel from './ViewerPanel.jsx'

const DRL_STATES = { 0: 'Idle', 1: 'Running', 2: 'Paused', 3: 'Error', 4: 'Done' }

export default function OperationPanel({ ros, speed, setSpeed, joints, tcp, currentTool, currentTcpName, programLogs }) {
    const [programs, setPrograms] = useState([])
    const [toolOffsets, setToolOffsets] = useState({})
    const [selectedProg, setSelectedProg] = useState(null)
    const [running, setRunning] = useState(false)
    const [paused, setPaused] = useState(false)
    const [drlState, setDrlState] = useState(0)
    const [log, setLog] = useState([])
    const logRef = useRef(null)
    const pollRef = useRef(null)
    const prevProgramLogIdRef = useRef(0)

    const addLog = (msg, type = 'default') =>
        setLog(prev => [...prev.slice(-99), { ts: Date.now(), msg, type }])

    const fetchPrograms = async () => {
        try {
            const r = await fetch('/api/programs')
            const d = await r.json()
            if (d.success) setPrograms(d.programs)
        } catch { }
    }

    const fetchInitialSpeed = async () => {
        try {
            const r = await fetch('/api/speed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ speed: 25 })
            })
            const d = await r.json()
            if (d.success) setSpeed(25)
        } catch { }
    }

    const fetchTcps = async () => {
        try {
            const r = await fetch('/api/tools/offsets')
            const d = await r.json()
            if (d.success) {
                setToolOffsets(d.offsets ?? {})
            }
        } catch { }
    }

    useEffect(() => {
        fetchPrograms()
        fetchInitialSpeed()
        fetchTcps()

        // Fetch current program state on mount
        fetch('/api/program/state').then(async (r) => {
            const d = await r.json()
            if (d.success) {
                setDrlState(d.drl_state)
                if (d.program) setSelectedProg(d.program)
                if (d.drl_state === 1) {
                    setRunning(true); setPaused(false)
                    startPolling()
                } else if (d.drl_state === 2) {
                    setRunning(true); setPaused(true)
                    startPolling()
                }
            }
        }).catch(() => { })

        return () => clearInterval(pollRef.current)
    }, [])

    // Merge incoming programLogs from WebSocket into the local log.
    // Track the last processed id instead of array length, because App caps log history.
    useEffect(() => {
        if (!programLogs || programLogs.length === 0) return

        const newEntries = programLogs.filter(e => (e.id ?? 0) > prevProgramLogIdRef.current)
        if (newEntries.length === 0) return

        setLog(prev => [...prev, ...newEntries.map(e => ({ ts: e.ts, msg: e.msg, type: 'default' }))].slice(-100))
        prevProgramLogIdRef.current = newEntries[newEntries.length - 1].id ?? prevProgramLogIdRef.current
    }, [programLogs])

    useEffect(() => {
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
    }, [log])

    const startPolling = () => {
        clearInterval(pollRef.current)
        pollRef.current = setInterval(async () => {
            try {
                const r = await fetch('/api/program/state')
                const d = await r.json()
                if (d.success) {
                    setDrlState(d.drl_state)
                    if (d.drl_state === 1 || d.drl_state === 2) {
                        setRunning(true)
                        setPaused(d.drl_state === 2)
                    } else if (d.drl_state !== 1 && d.drl_state !== 2) {
                        setRunning(false)
                        setPaused(false)
                        clearInterval(pollRef.current)
                        if (d.drl_state === 4) addLog('Program finished.', 'success')
                        else addLog('Program stopped or error.', 'warning')
                    }
                }
            } catch { }
        }, 1000)
    }

    const handleRun = async () => {
        if (!selectedProg) return addLog('No program selected', 'error')
        if (!ros) return addLog('Not connected to ROS', 'error')
        if (!window.confirm('Robot is going to move. Be sure the cell is safe, the path is clear, and people are outside the robot area. Do you want to continue?')) {
            addLog('Run cancelled by operator.', 'warning')
            return
        }

        // Fetch code
        let code = ''
        try {
            const r = await fetch(`/api/programs/${selectedProg}`)
            const d = await r.json()
            if (d.success) code = d.code
            else return addLog(`Failed to load ${selectedProg}`, 'error')
        } catch { return addLog(`Fetch error for ${selectedProg}`, 'error') }

        addLog(`Executing: ${selectedProg}...`, 'info')
        try {
            const r = await fetch('/api/program/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: selectedProg, code, robot_system: 0 }),
            })
            if (!r.ok) { addLog(`✘ Server error: ${r.status}`, 'error'); return }
            const d = await r.json()
            if (d.success) {
                addLog('✔ Started.', 'success')
                setRunning(true)
                setPaused(false)
                startPolling()
            } else {
                addLog(`✘ Failed: ${d.error || 'unknown'}`, 'error')
            }
        } catch (e) { addLog(`✘ Error: ${e.message}`, 'error') }
    }

    const handleStop = async () => {
        clearInterval(pollRef.current)
        setRunning(false); setPaused(false); setDrlState(0)
        try {
            const r = await fetch('/api/program/stop', { method: 'POST' })
            const d = await r.json()
            addLog(d.success ? '⚠ Stopped.' : '✘ Stop failed.', d.success ? 'warning' : 'error')
        } catch { addLog('✘ Stop request failed.', 'error') }
    }

    const handlePause = async () => {
        try {
            const r = await fetch('/api/program/pause', { method: 'POST' })
            const d = await r.json()
            if (d.success) { setPaused(true); setDrlState(2); addLog('⚠ Paused.', 'warning') }
            else addLog(`✘ Pause failed: ${d.error || 'unknown error'}`, 'error')
        } catch { addLog('✘ Pause API error.', 'error') }
    }

    const handleResume = async () => {
        try {
            const r = await fetch('/api/program/resume', { method: 'POST' })
            const d = await r.json()
            if (d.success) { setPaused(false); setDrlState(1); addLog('▶ Resumed.', 'success') }
            else addLog(`✘ Resume failed: ${d.error || 'unknown error'}`, 'error')
        } catch { addLog('✘ Resume API error.', 'error') }
    }

    const handleClearLog = () => {
        setLog([])
    }

    const handleSaveLog = () => {
        if (log.length === 0) return addLog('No log entries to save.', 'warning')

        const txt = log.map((entry) =>
            `[${new Date(entry.ts).toLocaleTimeString('en-GB', { hour12: false })}] ${entry.msg}`
        ).join('\n')

        const stamp = new Date().toISOString().replace(/[:.]/g, '-')
        const blob = new Blob([txt], { type: 'text/plain;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${selectedProg || 'operation-log'}-${stamp}.txt`
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        addLog('Log saved as .txt', 'success')
    }

    const activeTcpLabel = currentTcpName || currentTool || '—'
    const activeTcpOffsets = toolOffsets[activeTcpLabel]
    const uiSpeed = Math.min(25, Number.isFinite(speed) ? speed : 25)

    const commitSpeed = async (val) => {
        if (!ros) return addLog('Not connected to ROS', 'error')
        const safeVal = Math.max(1, Math.min(25, parseInt(val, 10) || 1))
        setSpeed(safeVal)
        try {
            const r = await fetch('/api/speed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ speed: safeVal })
            })
            const d = await r.json()
            if (d.success) addLog(`Speed set to ${safeVal}%`, 'info')
            else addLog('Failed to set speed', 'error')
        } catch {
            addLog('Speed request failed', 'error')
        }
    }

    return (
        <div style={{ display: 'grid', gridTemplateRows: 'minmax(0, 1.2fr) auto minmax(0, 0.95fr)', gap: 14, width: '100%', height: '100%', overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(180px, 0.52fr) minmax(220px, 0.65fr) minmax(240px, 0.7fr)', gap: 14, alignItems: 'stretch', minHeight: 0 }}>
                <div className="card" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px 0 14px', gap: 12 }}>
                        <div className="card-title" style={{ marginBottom: 8 }}>3D Robot Viewer</div>
                        <div style={{
                            fontSize: '0.74rem',
                            color: 'var(--text-2)',
                            background: 'var(--bg-base)',
                            border: '1px solid var(--border)',
                            borderRadius: 999,
                            padding: '4px 8px',
                            marginBottom: 8,
                        }}>
                            Active TCP: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{activeTcpLabel}</span>
                        </div>
                    </div>
                    <div style={{ padding: '0 14px 14px 14px', minHeight: 0 }}>
                        <ViewerPanel currentTcpName={currentTcpName} viewerHeight={360} />
                    </div>
                </div>

                <div className="card" style={{ padding: '12px 12px 10px 12px', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                    <div className="card-title" style={{ marginBottom: 10 }}>Live Robot Data</div>

                    <div style={{ fontSize: '0.69rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 8 }}>
                        Cartesian
                    </div>
                    <div style={{ display: 'grid', gap: 6, marginBottom: 12 }}>
                        {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((axis) => (
                            <div key={axis} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, fontSize: '0.78rem', borderBottom: '1px solid var(--border-light)', paddingBottom: 4 }}>
                                <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{axis}</span>
                                <span style={{ color: 'var(--text-1)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                                    {tcp && tcp[axis.toLowerCase()] !== undefined ? tcp[axis.toLowerCase()].toFixed(1) : '—'}
                                </span>
                            </div>
                        ))}
                    </div>

                    <div style={{ fontSize: '0.69rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 8 }}>
                        Joints
                    </div>
                    <div style={{ display: 'grid', gap: 6, minHeight: 0 }}>
                        {['J1', 'J2', 'J3', 'J4', 'J5', 'J6'].map((axis, i) => (
                            <div key={axis} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, fontSize: '0.78rem', borderBottom: i === 5 ? 'none' : '1px solid var(--border-light)', paddingBottom: 4 }}>
                                <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{axis}</span>
                                <span style={{ color: 'var(--text-1)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                                    {joints && joints[i] !== undefined ? joints[i].toFixed(1) : '—'}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="card" style={{ padding: '14px 16px', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                    <div className="card-title" style={{ marginBottom: 12 }}>Job List</div>
                    <div
                        style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr',
                            gap: 8,
                            flex: 1,
                            overflowY: 'auto',
                            alignContent: 'start'
                        }}
                    >
                        {programs.length === 0 && (
                            <div style={{ color: 'var(--text-3)', fontSize: '0.9rem' }}>
                                No programs found. Use the Program tab to create one.
                            </div>
                        )}

                        {programs.map(p => (
                            <button
                                key={p}
                                className={`btn ${selectedProg === p ? 'btn-primary' : 'btn-secondary'}`}
                                onClick={() => setSelectedProg(p)}
                                style={{
                                    padding: '11px 12px',
                                    textAlign: 'left',
                                    fontSize: '0.88rem',
                                    border: selectedProg === p
                                        ? '1px solid var(--accent)'
                                        : '1px solid var(--border)'
                                }}
                            >
                                <span style={{ fontWeight: 700 }}>{p}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div className="card-title" style={{ marginBottom: 0 }}>
                            {selectedProg ? `Operation: ${selectedProg}` : 'Operation'}
                        </div>
                        <span style={{
                            fontSize: '0.76rem',
                            color: running ? (paused ? 'var(--warning)' : 'var(--success)') : 'var(--text-3)',
                            background: 'var(--bg-base)',
                            padding: '4px 10px',
                            borderRadius: 100,
                            border: '1px solid var(--border)',
                            fontWeight: 700
                        }}>
                            {DRL_STATES[drlState] ?? 'Unknown'}
                        </span>
                    </div>
                    <div style={{ display: 'grid', gap: 10, flex: 1, alignContent: 'start' }}>
                        <button className="btn btn-primary" style={{ padding: '11px 16px', fontSize: '0.92rem' }}
                            onClick={handleRun} disabled={!ros || (running && !paused) || !selectedProg}>
                            {running ? 'Restart Program' : 'Run Program'}
                        </button>

                        {paused ? (
                            <button className="btn btn-warning" style={{ padding: '10px 16px', fontSize: '0.9rem', color: '#000' }}
                                onClick={handleResume} disabled={!ros}>Resume</button>
                        ) : (
                            <button className="btn btn-secondary" style={{ padding: '10px 16px', fontSize: '0.9rem' }}
                                onClick={handlePause} disabled={!running}>Pause</button>
                        )}

                        <button className="btn btn-danger" style={{ padding: '10px 16px', fontSize: '0.9rem' }}
                            onClick={handleStop} disabled={!running}>Stop</button>

                        <div style={{ fontSize: '0.83rem', color: selectedProg ? 'var(--text-2)' : 'var(--text-3)', background: 'var(--bg-base)', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border-light)' }}>
                            {selectedProg
                                ? <><strong style={{ color: 'var(--accent)' }}>Program selected.</strong> Press Run to execute on the robot.</>
                                : 'Select a program from the job list before running it.'}
                        </div>
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 0.9fr) minmax(320px, 1.1fr)', gap: 14, minHeight: 0 }}>
                <div className="card" style={{ padding: '14px 16px' }}>
                    <div className="card-title">Robot Speed Override</div>
                    <div style={{ color: 'var(--text-3)', fontSize: '0.78rem', marginBottom: 12 }}>
                        Operation speed is limited to a maximum of 25%.
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 74px', gap: 12, alignItems: 'center' }}>
                        <input
                            type="range"
                            min="1"
                            max="25"
                            value={uiSpeed}
                            onChange={(e) => setSpeed(Math.max(1, Math.min(25, parseInt(e.target.value, 10) || 1)))}
                            onMouseUp={(e) => commitSpeed(e.target.value)}
                            onTouchEnd={(e) => commitSpeed(e.target.value)}
                            style={{ width: '100%' }}
                        />
                        <input
                            type="number"
                            min="1"
                            max="25"
                            value={uiSpeed}
                            onChange={(e) => setSpeed(Math.max(1, Math.min(25, parseInt(e.target.value, 10) || 1)))}
                            onBlur={(e) => commitSpeed(e.target.value)}
                            style={{ width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text-1)', fontWeight: 700, textAlign: 'center' }}
                        />
                    </div>
                </div>

                <div className="card" style={{ padding: '12px 14px', height: '100%' }}>
                    <div className="card-title" style={{ marginBottom: 10 }}>Current TCP Offset</div>
                    <div style={{
                        fontSize: '0.98rem',
                        fontWeight: 800,
                        color: 'var(--accent)',
                        background: 'var(--bg-base)',
                        padding: '9px 12px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        textAlign: 'center',
                        marginBottom: 10
                    }}>
                        {activeTcpLabel}
                    </div>
                    <div style={{ color: 'var(--text-3)', fontSize: '0.76rem', marginBottom: 10 }}>
                        Showing the configured TCP definition for the active robot TCP.
                    </div>
                    {activeTcpOffsets ? (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px 10px', background: 'var(--bg-card2)', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)' }}>
                            {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((axis, i) => (
                                <div key={axis} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.79rem' }}>
                                    <span style={{ color: 'var(--text-3)', fontWeight: 600 }}>{axis}</span>
                                    <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text-1)' }}>
                                        {activeTcpOffsets[i]}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div style={{ color: 'var(--text-3)', fontSize: '0.86rem' }}>
                            No TCP offset data available for the active TCP.
                        </div>
                    )}
                </div>
            </div>

            <div className="card" style={{ minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div className="card-title" style={{ marginBottom: 0 }}>Operation Log</div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-secondary" style={{ padding: '7px 14px', fontSize: '0.88rem' }} onClick={handleClearLog}>
                            Clear
                        </button>
                        <button className="btn btn-primary" style={{ padding: '7px 14px', fontSize: '0.88rem' }} onClick={handleSaveLog}>
                            Save
                        </button>
                    </div>
                </div>
                <div ref={logRef} className="log-entries" style={{ flex: 1, minHeight: 0, overflowY: 'auto', background: 'var(--bg-base)', padding: 12, borderRadius: 6, border: '1px solid var(--border)' }}>
                    {log.length === 0 && <div className="log-entry">Waiting for operations...</div>}
                    {log.map((l, i) => (
                        <div key={i} className={`log-entry ${l.type}`}>
                            [{new Date(l.ts).toLocaleTimeString('en-GB', { hour12: false })}] {l.msg}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
