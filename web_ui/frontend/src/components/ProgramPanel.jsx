/* ── ProgramPanel.jsx ── */
import { useState, useRef, useEffect } from 'react'

const DEFAULT_PROGRAM = [
    '# ──────────────────────────────────────────────────────────────────',
    '# Empty Program',
    '# ──────────────────────────────────────────────────────────────────',
    'tp_print("Hello from Doosan IPC!")',
    '',
].join('\\n')

const DRL_STATES = { 0: 'Idle', 1: 'Running', 2: 'Paused', 3: 'Error', 4: 'Done' }

export default function ProgramPanel({ ros }) {
    const [code, setCode] = useState(DEFAULT_PROGRAM)
    const [running, setRunning] = useState(false)
    const [drlState, setDrlState] = useState(0)
    const [log, setLog] = useState([])
    const [programs, setPrograms] = useState([])
    const [progName, setProgName] = useState('')
    const logRef = useRef(null)
    const pollRef = useRef(null)

    const addLog = (msg, type = 'default') =>
        setLog(prev => [...prev.slice(-99), { ts: Date.now(), msg, type }])

    const startPolling = () => {
        pollRef.current = setInterval(async () => {
            try {
                const r = await fetch('/api/program/state')
                const d = await r.json()
                if (d.success) {
                    setDrlState(d.drl_state)
                    // 1 = Stop (done/stopped), 0 = Play (running)
                    if (d.drl_state === 1) {
                        setRunning(false)
                        clearInterval(pollRef.current)
                        addLog('Program finished / stopped.', 'success')
                    }
                }
            } catch { /* ignore */ }
        }, 1000)
    }

    const handleRun = async () => {
        if (!ros) return addLog('Not connected to ROS.', 'error')
        addLog('Sending Python program to robot backend...', 'info')
        try {
            const r = await fetch('/api/program/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, robot_system: 1 }),
            })
            const d = await r.json()
            if (d.success) {
                addLog('✔ Program started.', 'success')
                setRunning(true)
                startPolling()
            } else {
                addLog(`✘ Failed: ${d.error || 'unknown error'}`, 'error')
            }
        } catch (e) { addLog(`✘ Error: ${e.message}`, 'error') }
    }

    const handleStop = async () => {
        clearInterval(pollRef.current)
        try {
            const r = await fetch('/api/program/stop', { method: 'POST' })
            const d = await r.json()
            addLog(d.success ? '⚠ Program stopped.' : '✘ Stop failed.', d.success ? 'warning' : 'error')
        } catch { addLog('✘ Stop request failed.', 'error') }
        setRunning(false)
    }

    const fetchPrograms = async () => {
        try {
            const r = await fetch('/api/programs')
            const d = await r.json()
            if (d.success) setPrograms(d.programs)
        } catch { }
    }

    const handleSave = async () => {
        if (!progName) return alert('Enter a program name to save')
        try {
            const r = await fetch('/api/programs/save', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: progName, code, robot_system: 1 })
            })
            const d = await r.json()
            if (d.success) {
                addLog(`Saved program: ${progName}.py`, 'success')
                fetchPrograms()
            }
        } catch { addLog('Save failed', 'error') }
    }

    const handleLoad = async (name) => {
        try {
            const r = await fetch(`/api/programs/${name}`)
            const d = await r.json()
            if (d.success) {
                setCode(d.code)
                setProgName(name)
                addLog(`Loaded ${name}.py`, 'info')
            }
        } catch { }
    }

    // Since we need to receive websocket logs ("type": "log"), we listen via window events or similar.
    // In App.jsx, the websocket data is processed. Let's expose a global way to get logs, or just fetch them?
    // Actually, App.jsx might not be passing the raw WS to ProgramPanel.
    // Let's use an effect to hook into a global event if App dispatches one, or we can just open a dedicated WS?
    // Let's rely on App.jsx dispatching a custom event, or we just leave the polling behavior for now.
    // Actually, we can add a simple WS listener here specifically for logs.
    useEffect(() => {
        const ws = new WebSocket(`ws://${window.location.host}/ws`)
        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data)
            if (msg.type === "log") {
                addLog(msg.msg, 'info')
            } else if (msg.type === "connection_status") {
                if (!msg.connected) setRunning(false)
            }
        }
        return () => ws.close()
    }, [])

    useEffect(() => {
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
    }, [log])

    useEffect(() => {
        fetchPrograms()
        return () => clearInterval(pollRef.current)
    }, [])

    return (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

            {/* ── Library Sidebar ── */}
            <div className="card" style={{ width: 260, flexShrink: 0 }}>
                <div className="card-title">Programs Library</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <input
                            type="text" className="input" placeholder="Program name..."
                            value={progName} onChange={e => setProgName(e.target.value)}
                            style={{ flex: 1 }}
                        />
                        <button className="btn btn-secondary" onClick={handleSave}>Save</button>
                    </div>

                    <div style={{ marginTop: 12, borderTop: '1px solid var(--border-light)', paddingTop: 12 }}>
                        {programs.length === 0 && <div style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>No saved programs.</div>}
                        {programs.map(p => (
                            <div key={p} style={{
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 6, marginBottom: 8
                            }}>
                                <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-2)' }}>{p}.py</span>
                                <button className="btn" style={{ padding: '4px 10px', fontSize: '0.75rem' }} onClick={() => handleLoad(p)}>Load</button>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>

                {/* ── Editor ── */}
                <div className="card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div className="card-title" style={{ marginBottom: 0 }}>Python Program Editor</div>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{
                                fontSize: '0.78rem', color: running ? 'var(--success)' : 'var(--text-3)',
                                background: 'var(--bg-base)', padding: '3px 10px', borderRadius: 100,
                                border: '1px solid var(--border)'
                            }}>
                                {DRL_STATES[drlState] ?? 'Unknown'}
                            </span>
                            <button className="btn btn-danger" style={{ padding: '7px 16px' }}
                                onClick={handleStop} disabled={!running}>Stop</button>
                            <button className="btn btn-primary" style={{ padding: '7px 18px' }}
                                onClick={handleRun} disabled={!ros || running}>Run</button>
                        </div>
                    </div>
                    <textarea
                        value={code}
                        onChange={e => setCode(e.target.value)}
                        spellCheck={false}
                        style={{
                            width: '100%', minHeight: 400, background: '#060a14',
                            color: '#c8d3f5', fontFamily: "'Courier New', monospace",
                            fontSize: '0.875rem', lineHeight: 1.7,
                            border: '1px solid var(--border)', borderRadius: 8,
                            padding: 16, resize: 'vertical', outline: 'none',
                        }}
                    />
                    <div style={{ marginTop: 10, fontSize: '0.75rem', color: 'var(--text-3)', display: 'flex', gap: 16 }}>
                        <span>Python Environment</span>
                        <span><code style={{ color: 'var(--accent)' }}>movej()</code> joint move</span>
                        <span><code style={{ color: 'var(--accent)' }}>movel()</code> linear move</span>
                        <span><code style={{ color: 'var(--accent)' }}>set_do(idx, val)</code> set dig. out</span>
                        <span><code style={{ color: 'var(--accent)' }}>tp_print()</code> log</span>
                        <span><code style={{ color: 'var(--accent)' }}>wait(sec)</code> sleep</span>
                    </div>
                </div>

                {/* ── Log ── */}
                <div className="card">
                    <div className="card-title">Execution Log</div>
                    <div className="log-entries" ref={logRef} style={{ height: 120 }}>
                        {log.length === 0 && <div className="log-entry">Ready. Press ▶ Run to execute.</div>}
                        {log.map((l, i) => (
                            <div key={i} className={`log-entry ${l.type}`}>
                                [{new Date(l.ts).toLocaleTimeString('en-GB', { hour12: false })}] {l.msg}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div >
    )
}
