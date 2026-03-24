import { useState, useRef, useEffect } from 'react'

const DRL_STATES = { 0: 'Idle', 1: 'Running', 2: 'Paused', 3: 'Error', 4: 'Done' }

export default function OperationPanel({ ros, speed, setSpeed, joints, tcp, currentTool, programLogs }) {
    const [programs, setPrograms] = useState([])
    const [toolOffsets, setToolOffsets] = useState({})
    const [selectedProg, setSelectedProg] = useState(null)
    const [running, setRunning] = useState(false)
    const [paused, setPaused] = useState(false)
    const [drlState, setDrlState] = useState(0)
    const [log, setLog] = useState([])
    const logRef = useRef(null)
    const pollRef = useRef(null)
    const prevLogCountRef = useRef(0)

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
                const { success, ...offsets } = d
                setToolOffsets(offsets)
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

    // Merge incoming programLogs from WebSocket into the local log
    useEffect(() => {
        if (programLogs && programLogs.length > prevLogCountRef.current) {
            const newEntries = programLogs.slice(prevLogCountRef.current)
            // Add to the START of the array for newest-first order
            setLog(prev => [...newEntries.map(e => ({ ts: e.ts, msg: e.msg, type: 'default' })).reverse(), ...prev.slice(0, 99)])
            prevLogCountRef.current = programLogs.length
        }
    }, [programLogs])

    useEffect(() => {
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
    }, [log])

    const startPolling = () => {
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

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 20 }}>
            {/* Left Column */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Program Selection */}
                <div className="card">
                    <div className="card-title">Select Program</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {programs.length === 0 && <div style={{ color: 'var(--text-3)' }}>No programs found. Use "Program" tab to create one.</div>}
                        {programs.map(p => (
                            <button
                                key={p}
                                className={`btn ${selectedProg === p ? 'btn-primary' : 'btn-secondary'}`}
                                onClick={() => setSelectedProg(p)}
                                style={{
                                    padding: '12px 16px',
                                    textAlign: 'left',
                                    fontSize: '0.95rem',
                                    border: selectedProg === p ? '1px solid var(--accent)' : '1px solid var(--border)'
                                }}
                            >
                                <span style={{ fontWeight: 600 }}>{p}</span>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Left Bottom: Speed Control */}
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
                        <span id="op-speed-label" style={{ fontWeight: 600, minWidth: 40, textAlign: 'right' }}>{speed}%</span>
                    </div>
                </div>

                {/* Left Bottom: Active TCP Offset */}
                <div className="card" style={{ flex: 1 }}>
                    <div className="card-title" style={{ marginBottom: 12 }}>Active TCP Offset</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, justifyContent: 'center', height: '100%' }}>
                        <div style={{
                            fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)',
                            background: 'var(--bg-base)', padding: '10px 20px', borderRadius: 8,
                            border: '1px solid var(--border)', textAlign: 'center'
                        }}>
                            {currentTool || '—'}
                        </div>

                        {currentTool && toolOffsets[currentTool] && (
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px 12px', background: 'var(--bg-card2)', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)' }}>
                                {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((axis, i) => (
                                    <div key={axis} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                                        <span style={{ color: 'var(--text-3)', fontWeight: 600 }}>{axis}:</span>
                                        <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--text-1)' }}>
                                            {toolOffsets[currentTool][i]}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Right: Execution Info & Log */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div className="card-title" style={{ marginBottom: 0 }}>
                            {selectedProg ? `Operation: ${selectedProg}` : 'Operation'}
                        </div>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{
                                fontSize: '0.8rem', color: running ? (paused ? 'var(--warning)' : 'var(--success)') : 'var(--text-3)',
                                background: 'var(--bg-base)', padding: '4px 12px', borderRadius: 100,
                                border: '1px solid var(--border)', fontWeight: 600
                            }}>
                                {DRL_STATES[drlState] ?? 'Unknown'}
                            </span>
                            <button className="btn btn-danger" style={{ padding: '8px 20px', fontSize: '0.95rem' }}
                                onClick={handleStop} disabled={!running}>Stop</button>

                            {paused ? (
                                <button className="btn btn-warning" style={{ padding: '8px 24px', fontSize: '0.95rem', color: '#000' }}
                                    onClick={handleResume} disabled={!ros}>Resume</button>
                            ) : (
                                <button className="btn btn-secondary" style={{ padding: '8px 20px', fontSize: '0.95rem' }}
                                    onClick={handlePause} disabled={!running}>Pause</button>
                            )}

                            <button className="btn btn-primary" style={{ padding: '8px 24px', fontSize: '0.95rem' }}
                                onClick={handleRun} disabled={!ros || (running && !paused) || !selectedProg}>
                                {running ? 'Restart' : 'Run'}
                            </button>
                        </div>
                    </div>
                    {selectedProg ? (
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-2)', background: 'var(--bg-base)', padding: '10px 14px', borderRadius: 6, border: '1px solid var(--border-light)' }}>
                            <strong style={{ color: 'var(--accent)' }}>Program Selected.</strong> Press Run to execute on the robot.
                        </div>
                    ) : (
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-3)' }}>
                            Please select a daily program from the list to execute.
                        </div>
                    )}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div className="card" style={{ padding: '12px 16px' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', fontWeight: 600 }}>Live TCP (mm, °)</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '6px 12px' }}>
                            {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((k, i) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 2 }}>
                                    <span style={{ color: 'var(--text-2)', fontSize: '0.8rem' }}>{k}</span>
                                    <span style={{ fontWeight: 600, fontSize: '0.85rem', fontVariantNumeric: 'tabular-nums' }}>
                                        {tcp && tcp[k.toLowerCase()] !== undefined ? tcp[k.toLowerCase()].toFixed(1) : '—'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="card" style={{ padding: '12px 16px' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', fontWeight: 600 }}>Live Joints (°)</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '6px 12px' }}>
                            {['J1', 'J2', 'J3', 'J4', 'J5', 'J6'].map((k, i) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 2 }}>
                                    <span style={{ color: 'var(--text-2)', fontSize: '0.8rem' }}>{k}</span>
                                    <span style={{ fontWeight: 600, fontSize: '0.85rem', fontVariantNumeric: 'tabular-nums' }}>
                                        {joints && joints[i] !== undefined ? joints[i].toFixed(1) : '—'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="card" style={{ flex: 1, maxWidth: 1000, minHeight: 300, maxHeight: 500, display: 'flex', flexDirection: 'column' }}>
                    <div className="card-title">Operation Log</div>
                    <div className="log-entries" style={{ flex: 1, overflowY: 'auto', background: 'var(--bg-base)', padding: 12, borderRadius: 6, border: '1px solid var(--border)' }}>
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
