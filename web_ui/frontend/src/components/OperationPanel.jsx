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
            else addLog('✘ Pause failed.', 'error')
        } catch { addLog('✘ Pause API error.', 'error') }
    }

    const handleResume = async () => {
        try {
            const r = await fetch('/api/program/resume', { method: 'POST' })
            const d = await r.json()
            if (d.success) { setPaused(false); setDrlState(1); addLog('▶ Resumed.', 'success') }
            else addLog('✘ Resume failed.', 'error')
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

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(320px, 0.95fr)', gap: 20, alignItems: 'stretch' }}>
                <div className="card" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 18px 0 18px', gap: 12 }}>
                        <div className="card-title" style={{ marginBottom: 12 }}>3D Robot Viewer</div>
                        <div style={{
                            fontSize: '0.74rem',
                            color: 'var(--text-2)',
                            background: 'var(--bg-base)',
                            border: '1px solid var(--border)',
                            borderRadius: 999,
                            padding: '5px 10px',
                            marginBottom: 12,
                        }}>
                            Active TCP: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{activeTcpLabel}</span>
                        </div>
                    </div>
                    <ViewerPanel currentTcpName={currentTcpName} />
                </div>

                <div style={{ display: 'grid', gap: 14, height: '100%', gridTemplateRows: 'auto auto 1fr auto' }}>
                    <div className="card">
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
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <button className="btn btn-danger" style={{ padding: '8px 16px', fontSize: '0.9rem' }}
                                onClick={handleStop} disabled={!running}>Stop</button>

                            {paused ? (
                                <button className="btn btn-warning" style={{ padding: '8px 16px', fontSize: '0.9rem', color: '#000' }}
                                    onClick={handleResume} disabled={!ros}>Resume</button>
                            ) : (
                                <button className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.9rem' }}
                                    onClick={handlePause} disabled={!running}>Pause</button>
                            )}

                            <button className="btn btn-primary" style={{ gridColumn: '1 / -1', padding: '9px 16px', fontSize: '0.92rem' }}
                                onClick={handleRun} disabled={!ros || (running && !paused) || !selectedProg}>
                                {running ? 'Restart Program' : 'Run Program'}
                            </button>
                        </div>
                        <div style={{ fontSize: '0.83rem', color: selectedProg ? 'var(--text-2)' : 'var(--text-3)', background: 'var(--bg-base)', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border-light)', marginTop: 12 }}>
                            {selectedProg
                                ? <><strong style={{ color: 'var(--accent)' }}>Program selected.</strong> Press Run to execute on the robot.</>
                                : 'Select a program below to execute it on the robot.'}
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-title">Robot Speed Override</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <input
                                type="range" min="1" max="100" value={speed}
                                onChange={(e) => setSpeed(parseInt(e.target.value))}
                                onMouseUp={async (e) => {
                                    if (!ros) return addLog('Not connected to ROS', 'error')
                                    const val = parseInt(e.target.value)
                                    try {
                                        const r = await fetch('/api/speed', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ speed: val })
                                        })
                                        const d = await r.json()
                                        if (d.success) addLog(`Speed set to ${val}%`, 'info')
                                        else addLog('Failed to set speed', 'error')
                                    } catch { addLog('Speed request failed', 'error') }
                                }}
                                style={{ flex: 1 }}
                            />
                            <span id="op-speed-label" style={{ fontWeight: 700, minWidth: 44, textAlign: 'right' }}>{speed}%</span>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignItems: 'stretch' }}>
                        <div className="card" style={{ padding: '14px 16px', height: '100%' }}>
                            <div className="card-title" style={{ marginBottom: 10 }}>Live TCP</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 10px' }}>
                                {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((k) => (
                                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 3, fontSize: '0.82rem' }}>
                                        <span style={{ color: 'var(--text-2)' }}>{k}</span>
                                        <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                                            {tcp && tcp[k.toLowerCase()] !== undefined ? tcp[k.toLowerCase()].toFixed(1) : '—'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="card" style={{ padding: '14px 16px', height: '100%' }}>
                            <div className="card-title" style={{ marginBottom: 10 }}>Live Joints</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 10px' }}>
                                {['J1', 'J2', 'J3', 'J4', 'J5', 'J6'].map((k, i) => (
                                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 3, fontSize: '0.82rem' }}>
                                        <span style={{ color: 'var(--text-2)' }}>{k}</span>
                                        <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                                            {joints && joints[i] !== undefined ? joints[i].toFixed(1) : '—'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="card" style={{ padding: '14px 16px' }}>
                        <div className="card-title" style={{ marginBottom: 10 }}>Active TCP Offset</div>
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
                        {activeTcpOffsets && (
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
                        )}
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 0.85fr) minmax(0, 1.15fr)', gap: 20, alignItems: 'stretch' }}>
                <div className="card" style={{ padding: '16px 18px', minHeight: 320, maxHeight: 320, display: 'flex', flexDirection: 'column' }}>
                    <div className="card-title" style={{ marginBottom: 12 }}>Tasks / Programs</div>


                    <div
                        style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: 6,
                            flex: 1,
                            overflowY: 'auto'
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
                                    padding: '10px 12px',
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

                <div className="card" style={{ minHeight: 320, maxHeight: 320, display: 'flex', flexDirection: 'column' }}>
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
                    <div ref={logRef} className="log-entries" style={{ flex: 1, overflowY: 'auto', background: 'var(--bg-base)', padding: 12, borderRadius: 6, border: '1px solid var(--border)' }}>
                        {log.length === 0 && <div className="log-entry">Waiting for operations...</div>}
                        {log.map((l, i) => (
                            <div key={i} className={`log-entry ${l.type}`}>
                                [{new Date(l.ts).toLocaleTimeString('en-GB', { hour12: false })}] {l.msg}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
