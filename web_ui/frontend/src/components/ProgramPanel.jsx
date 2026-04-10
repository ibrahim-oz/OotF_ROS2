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
const PY_KEYWORDS = /\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b/g
const PY_BUILTINS = /\b(abs|all|any|bool|dict|enumerate|float|int|len|list|max|min|print|range|round|set|str|sum|tuple|zip)\b/g
const PY_CUSTOMS = /\b(tp_print|movej|movel|movejx|set_do|wait|get_tcp|set_ref|vacuum)\b/g

const escapeHtml = (text) => text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

const highlightPython = (source) => {
    const lines = source.split('\n')

    return lines.map((line, index) => {
        let html = escapeHtml(line)
        html = html.replace(/(&quot;.*?&quot;|".*?"|'.*?')/g, '<span style="color:#c4b5fd;">$1</span>')
        html = html.replace(/(#.*)$/g, '<span style="color:#6b7280;">$1</span>')
        html = html.replace(/\b(\d+(\.\d+)?)\b/g, '<span style="color:#f59e0b;">$1</span>')
        html = html.replace(PY_KEYWORDS, '<span style="color:#7dd3fc;">$1</span>')
        html = html.replace(PY_BUILTINS, '<span style="color:#fda4af;">$1</span>')
        html = html.replace(PY_CUSTOMS, '<span style="color:#34d399;">$1</span>')
        return html || '&nbsp;'
    }).join('\n')
}

export default function ProgramPanel({ ros }) {
    const [code, setCode] = useState(DEFAULT_PROGRAM)
    const [running, setRunning] = useState(false)
    const [drlState, setDrlState] = useState(0)
    const [log, setLog] = useState([])
    const [programs, setPrograms] = useState([])
    const [progName, setProgName] = useState('')
    const logRef = useRef(null)
    const pollRef = useRef(null)
    const editorRef = useRef(null)
    const highlightRef = useRef(null)

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
        const syncScroll = () => {
            if (highlightRef.current && editorRef.current) {
                highlightRef.current.scrollTop = editorRef.current.scrollTop
                highlightRef.current.scrollLeft = editorRef.current.scrollLeft
            }
        }

        const editor = editorRef.current
        if (!editor) return
        editor.addEventListener('scroll', syncScroll)
        return () => editor.removeEventListener('scroll', syncScroll)
    }, [])

    useEffect(() => {
        fetchPrograms()
        return () => clearInterval(pollRef.current)
    }, [])

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '280px minmax(0, 1fr)', gap: 20, alignItems: 'flex-start' }}>

            {/* ── Library Sidebar ── */}
            <div className="card" style={{ flexShrink: 0, padding: '16px 18px' }}>
                <div className="card-title" style={{ marginBottom: 8 }}>Programs Library</div>
                <div style={{ color: 'var(--text-3)', fontSize: '0.82rem', marginBottom: 12 }}>
                    Save reusable robot programs and reload them quickly.
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <input
                            type="text" className="input" placeholder="Program name..."
                            value={progName} onChange={e => setProgName(e.target.value)}
                            style={{ flex: 1 }}
                        />
                        <button className="btn btn-secondary" onClick={handleSave}>Save</button>
                    </div>

                    <div style={{ marginTop: 8, borderTop: '1px solid var(--border-light)', paddingTop: 12 }}>
                        {programs.length === 0 && <div style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>No saved programs.</div>}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 520, overflowY: 'auto' }}>
                            {programs.map(p => (
                                <div key={p} style={{
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                    padding: '10px 12px',
                                    background: 'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))',
                                    border: '1px solid var(--border)',
                                    borderRadius: 8
                                }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p}.py</div>
                                        <div style={{ fontSize: '0.73rem', color: 'var(--text-3)' }}>Python robot program</div>
                                    </div>
                                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.74rem' }} onClick={() => handleLoad(p)}>Load</button>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>

                {/* ── Editor ── */}
                <div className="card" style={{ padding: '16px 18px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div>
                            <div className="card-title" style={{ marginBottom: 4 }}>Python Program Editor</div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>
                                Syntax-colored editor for DRL helpers and Python flow control.
                            </div>
                        </div>
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

                    <div style={{
                        position: 'relative',
                        minHeight: 420,
                        border: '1px solid var(--border)',
                        borderRadius: 10,
                        overflow: 'hidden',
                        background: 'linear-gradient(180deg, #08101f 0%, #050914 100%)'
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '10px 14px',
                            borderBottom: '1px solid rgba(255,255,255,0.06)',
                            background: 'rgba(255,255,255,0.03)'
                        }}>
                            <div style={{ display: 'flex', gap: 7 }}>
                                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#fb7185', display: 'inline-block' }}></span>
                                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }}></span>
                                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#34d399', display: 'inline-block' }}></span>
                            </div>
                            <div style={{ fontSize: '0.76rem', color: 'var(--text-3)', fontFamily: 'monospace' }}>
                                {progName ? `${progName}.py` : 'untitled_program.py'}
                            </div>
                        </div>

                        <div style={{ position: 'relative', minHeight: 378 }}>
                            <pre
                                ref={highlightRef}
                                aria-hidden="true"
                                style={{
                                    margin: 0,
                                    padding: 16,
                                    minHeight: 378,
                                    overflow: 'auto',
                                    whiteSpace: 'pre',
                                    fontFamily: "'Courier New', monospace",
                                    fontSize: '0.9rem',
                                    lineHeight: 1.7,
                                    color: '#c8d3f5',
                                    pointerEvents: 'none'
                                }}
                                dangerouslySetInnerHTML={{ __html: highlightPython(code) }}
                            />
                            <textarea
                                ref={editorRef}
                                value={code}
                                onChange={e => setCode(e.target.value)}
                                spellCheck={false}
                                style={{
                                    position: 'absolute',
                                    inset: 0,
                                    width: '100%',
                                    minHeight: 378,
                                    background: 'transparent',
                                    color: 'transparent',
                                    caretColor: '#f8fafc',
                                    fontFamily: "'Courier New', monospace",
                                    fontSize: '0.9rem',
                                    lineHeight: 1.7,
                                    border: 'none',
                                    padding: 16,
                                    resize: 'vertical',
                                    outline: 'none',
                                    whiteSpace: 'pre',
                                    overflow: 'auto'
                                }}
                            />
                        </div>
                    </div>

                    <div style={{ marginTop: 10, fontSize: '0.75rem', color: 'var(--text-3)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        <span>Python Environment</span>
                        <span><code style={{ color: 'var(--accent)' }}>movej()</code> joint move</span>
                        <span><code style={{ color: 'var(--accent)' }}>movel()</code> linear move</span>
                        <span><code style={{ color: '#34d399' }}>movejx()</code> jointx move</span>
                        <span><code style={{ color: 'var(--accent)' }}>set_do(idx, val)</code> set dig. out</span>
                        <span><code style={{ color: 'var(--accent)' }}>tp_print()</code> log</span>
                        <span><code style={{ color: 'var(--accent)' }}>wait(sec)</code> sleep</span>
                    </div>
                </div>

                {/* ── Log ── */}
                <div className="card" style={{ padding: '14px 18px' }}>
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
