//web_ui/frontend/src/App.jsx
import { useState, useEffect, useRef, useCallback } from 'react'
import IOPanel from './components/IOPanel.jsx'
import ProgramPanel from './components/ProgramPanel.jsx'
import VariablesPanel from './components/VariablesPanel.jsx'
import ViewerPanel from './components/ViewerPanel.jsx'
import OperationPanel from './components/OperationPanel.jsx'
import ResultsPanel from './components/ResultsPanel.jsx'
import VisionDbPanel from './components/VisionDbPanel.jsx'
import AllImagesPanel from './components/AllImagesPanel.jsx'

// ─── Constants ───────────────────────────────────────────────────
const JOINT_NAMES = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6']
const JOG_SPEED = 10   // % of max speed while button held
const JOG_JOINT_AXES = [0, 1, 2, 3, 4, 5]     // jog_axis values for joints
const JOG_CART_AXES = [6, 7, 8, 9, 10, 11]   // Tx,Ty,Tz,Rx,Ry,Rz
const CART_LABELS = ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']
const CART_UNITS = ['mm', 'mm', 'mm', '°', '°', '°']

// ─── Tiny helpers ────────────────────────────────────────────────
const post = (url, body) => fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
}).then(r => r.json())

function useWS(url, onMsg, enabled = true) {
    const ref = useRef(null)
    const [st, setSt] = useState('disconnected')
    const connect = useCallback(() => {
        if (!enabled) return
        setSt('connecting')
        const ws = new WebSocket(url)
        ref.current = ws
        ws.onopen = () => setSt('connected')
        ws.onmessage = e => { try { onMsg(JSON.parse(e.data)) } catch { } }
        ws.onclose = () => { setSt('disconnected'); setTimeout(connect, 3000) }
        ws.onerror = () => setSt('error')
    }, [url, onMsg, enabled])
    useEffect(() => {
        if (!enabled) {
            setSt('disconnected')
            ref.current?.close()
            return
        }
        connect()
        return () => ref.current?.close()
    }, [connect, enabled])
    return st
}

function LoginScreen({ busy, error, onSubmit }) {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')

    const submit = (e) => {
        e.preventDefault()
        onSubmit({ username, password })
    }

    return (
        <div className="app" style={{ justifyContent: 'center', alignItems: 'center', padding: 24 }}>
            <div className="card" style={{ width: '100%', maxWidth: 420, padding: '28px 30px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                    <div className="card-title" style={{ marginBottom: 6 }}>Secure Login</div>
                    <div style={{ color: 'var(--text-3)', fontSize: '0.88rem' }}>
                        Sign in to access robot control and vision data.
                    </div>
                </div>

                <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <input
                        className="input"
                        type="text"
                        autoComplete="username"
                        placeholder="Username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        style={{ padding: '20px 16px', fontSize: '1rem' }}
                    />
                    <input
                        className="input"
                        type="password"
                        autoComplete="current-password"
                        placeholder="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        style={{ padding: '20px 16px', fontSize: '1rem' }}
                    />
                    {error && (
                        <div style={{ color: 'var(--danger)', fontSize: '0.82rem' }}>
                            {error}
                        </div>
                    )}
                    <button className="btn btn-primary" type="submit" disabled={busy} style={{ padding: '10px 16px' }}>
                        {busy ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>
            </div>
        </div>
    )
}

// ─── Sub-components ──────────────────────────────────────────────

function JointCard({ name, deg }) {
    const pct = Math.min(Math.max((deg + 180) / 360, 0), 1)
    return (
        <div className="joint-item">
            <div className="joint-label">{name}</div>
            <div className="joint-value">{deg.toFixed(1)}<sup>°</sup></div>
            <div className="joint-bar-bg"><div className="joint-bar-fill" style={{ width: `${pct * 100}%` }} /></div>
        </div>
    )
}

function TcpRow({ tcp }) {
    const fields = [
        { k: 'x', c: '#f4460b' }, { k: 'y', c: '#2f5667' }, { k: 'z', c: '#7a9fad' },
        { k: 'rx', c: '#c0340a' }, { k: 'ry', c: '#4a7f94' }, { k: 'rz', c: '#94a3b8' },
    ]
    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 8 }}>
            {fields.map(({ k, c }) => (
                <div key={k} style={{
                    background: 'var(--bg-card2)', border: `1px solid ${c}22`, borderTop: `3px solid ${c}`,
                    borderRadius: 8, padding: '10px 12px', textAlign: 'center'
                }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-2)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>{k.toUpperCase()}</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 700, color: c, fontVariantNumeric: 'tabular-nums' }}>
                        {tcp?.[k] != null ? tcp[k].toFixed(1) : '—'}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', marginTop: 2 }}>{k.startsWith('r') ? '°' : 'mm'}</div>
                </div>
            ))}
        </div>
    )
}

function JogButtons({ joints, tcp, ros }) {
    const [jStep, setJStep] = useState(5)
    const [jogMode, setJogMode] = useState('joint')   // 'joint' | 'cart'
    const [busy, setBusy] = useState(false)
    const [target, setTarget] = useState({
        joint: ['0', '0', '0', '0', '0', '0'],
        tcp: ['0', '0', '0', '0', '0', '0'],
    })
    const [msg, setMsg] = useState('')
    const holdRef = useRef(null)
    const lastAxisRef = useRef(0)  // track which axis to stop

    // axisIdx: 0-5=joints, 6-11=cart. direction: +1 or -1.
    const startJog = (axisIdx, direction) => {
        if (!ros) return
        lastAxisRef.current = axisIdx
        const doJog = () => post('/api/jog', { axis: axisIdx, speed: direction * JOG_SPEED })
        clearInterval(holdRef.current)
        doJog()
        holdRef.current = setInterval(doJog, 180)
    }
    const stopJog = () => {
        clearInterval(holdRef.current)
        // Send speed=0 to the specific axis that was jogging
        post('/api/jog', { axis: lastAxisRef.current, speed: 0 })
    }

    const moveTo = async () => {
        if (!ros) return
        setBusy(true); setMsg('')
        // jogMode 'cart' maps to target key 'tcp'
        const targetKey = jogMode === 'cart' ? 'tcp' : 'joint'
        const vals = target[targetKey].map(Number)
        const endpoint = jogMode === 'joint' ? '/api/move/joint' : '/api/move/tcp'
        const body = jogMode === 'joint'
            ? { pos: vals, vel: 30, acc: 60, sync_type: 1 }
            : { pos: vals, vel: 100, acc: 200, sync_type: 1 }
        const r = await post(endpoint, body)
        setMsg(r.success ? '✔ Move command sent' : '✘ Failed')
        setBusy(false)
    }

    const fillFromRobot = () => {
        if (jogMode === 'joint') setTarget(t => ({ ...t, joint: joints.map(v => v.toFixed(2)) }))
        else if (tcp) setTarget(t => ({ ...t, tcp: [tcp.x, tcp.y, tcp.z, tcp.rx, tcp.ry, tcp.rz].map(v => v.toFixed(2)) }))
    }

    useEffect(() => () => clearInterval(holdRef.current), [])

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Mode selector */}
            <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>
                {['joint', 'cart'].map(m => (
                    <button key={m} className="btn btn-secondary"
                        style={{ padding: '6px 18px', ...(jogMode === m ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}) }}
                        onClick={() => setJogMode(m)}>{m === 'joint' ? 'Joint Jog' : 'Cartesian Jog'}
                    </button>
                ))}
            </div>

            {/* ── Joint Jog ── */}
            {jogMode === 'joint' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
                    {JOINT_NAMES.map((name, i) => (
                        <div key={name} style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                                <span style={{ fontWeight: 600 }}>{name}</span>
                                <span style={{ color: 'var(--text-2)', fontSize: '0.8rem', fontVariantNumeric: 'tabular-nums' }}>{(joints[i] || 0).toFixed(1)}°</span>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                                <button className="btn btn-secondary" style={{ flex: 1, padding: '8px 0', fontSize: '1.2rem' }}
                                    onMouseDown={() => startJog(i, -1)} onMouseUp={stopJog} onMouseLeave={stopJog}
                                    onTouchStart={() => startJog(i, -1)} onTouchEnd={stopJog} disabled={!ros}>−</button>
                                <button className="btn btn-secondary" style={{ flex: 1, padding: '8px 0', fontSize: '1.2rem' }}
                                    onMouseDown={() => startJog(i, +1)} onMouseUp={stopJog} onMouseLeave={stopJog}
                                    onTouchStart={() => startJog(i, +1)} onTouchEnd={stopJog} disabled={!ros}>+</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Cart Jog ── */}
            {jogMode === 'cart' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
                    {CART_LABELS.map((lbl, i) => {
                        const ax = JOG_CART_AXES[i]
                        return (
                            <div key={lbl} style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                                    <span style={{ fontWeight: 600 }}>{lbl}</span>
                                    <span style={{ color: 'var(--text-2)', fontSize: '0.75rem' }}>{CART_UNITS[i]}</span>
                                </div>
                                <div style={{ display: 'flex', gap: 6 }}>
                                    <button className="btn btn-secondary" style={{ flex: 1, padding: '8px 0', fontSize: '1.2rem' }}
                                        onMouseDown={() => startJog(ax, -1)} onMouseUp={stopJog} onMouseLeave={stopJog}
                                        onTouchStart={() => startJog(ax, -1)} onTouchEnd={stopJog} disabled={!ros}>−</button>
                                    <button className="btn btn-secondary" style={{ flex: 1, padding: '8px 0', fontSize: '1.2rem' }}
                                        onMouseDown={() => startJog(ax, +1)} onMouseUp={stopJog} onMouseLeave={stopJog}
                                        onTouchStart={() => startJog(ax, +1)} onTouchEnd={stopJog} disabled={!ros}>+</button>
                                </div>
                            </div>
                        )
                    })}
                </div>
            )}

            {/* ── Move to Target ── */}
            <div style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-2)' }}>
                        Move to Target — {jogMode === 'joint' ? 'Joint Angles (°)' : 'TCP Position (mm/°)'}
                    </span>
                    <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: '0.75rem' }} onClick={fillFromRobot}>
                        From Robot
                    </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 8, marginBottom: 12 }}>
                    {(jogMode === 'joint' ? JOINT_NAMES : CART_LABELS).map((lbl, i) => (
                        <div key={lbl}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4, textAlign: 'center' }}>{lbl}</div>
                            <input type="number" step="0.1"
                                value={target[jogMode === 'cart' ? 'tcp' : 'joint'][i]}
                                onChange={e => {
                                    const tk = jogMode === 'cart' ? 'tcp' : 'joint'
                                    const v = [...target[tk]]; v[i] = e.target.value
                                    setTarget(t => ({ ...t, [tk]: v }))
                                }}
                                style={{
                                    width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)',
                                    borderRadius: 6, padding: '7px 8px', color: 'var(--text-1)', fontFamily: 'inherit',
                                    fontSize: '0.85rem', textAlign: 'center', outline: 'none'
                                }}
                            />
                        </div>
                    ))}
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button className="btn btn-primary" style={{ padding: '8px 24px' }}
                        onClick={moveTo} disabled={!ros || busy}>
                        {busy ? '⏳ Moving…' : '▶ Execute'}
                    </button>
                    {msg && <span style={{ fontSize: '0.82rem', color: msg.startsWith('✔') ? 'var(--success)' : 'var(--danger)' }}>{msg}</span>}
                </div>
            </div>
        </div>
    )
}

// ─── Main App ────────────────────────────────────────────────────

const TABS = [
    { id: 'control', label: 'Control' },
    { id: 'operation', label: 'Operation' },
    { id: 'io', label: 'I/O' },
    { id: 'variables', label: 'Variables' },
    { id: 'program', label: 'Program' },
    { id: 'vision', label: 'Vision TCP' },
    { id: 'vision-db', label: 'Vision DB' },
    { id: 'results', label: 'Results' },
    { id: 'all-images', label: 'All Images' },
]

export default function App() {
    const [authChecked, setAuthChecked] = useState(false)
    const [authenticated, setAuthenticated] = useState(false)
    const [authBusy, setAuthBusy] = useState(false)
    const [authError, setAuthError] = useState('')
    const [tab, setTab] = useState('control')
    const [joints, setJoints] = useState(Array(6).fill(0))
    const [tcp, setTcp] = useState(null)
    const [currentTool, setCurrentTool] = useState('flange')
    const [currentTcpName, setCurrentTcpName] = useState('tcp_gripper_A')
    const [lastTs, setLastTs] = useState(null)
    const [logs, setLogs] = useState([{ ts: Date.now(), text: 'Panel ready.', type: 'info' }])
    const logRef = useRef(null)

    const [visionData, setVisionData] = useState('')
    const [visionBusy, setVisionBusy] = useState(false)
    const [visionCommand, setVisionCommand] = useState('100;1')
    const [visionCommandName, setVisionCommandName] = useState('')
    const [savedVisionCommands, setSavedVisionCommands] = useState([])

    const [rosAlive, setRosAlive] = useState(false)
    const programLogIdRef = useRef(0)

    // Global Speed State (shared between Control and Operation tabs)
    const [globalSpeed, setGlobalSpeed] = useState(25)

    // Program log messages from subprocess (streamed via WebSocket)
    const [programLogs, setProgramLogs] = useState([])

    const addLog = useCallback((text, type = 'default') =>
        setLogs(p => [...p.slice(-49), { ts: Date.now(), text, type }]), [])

    const onMsg = useCallback(d => {
        if (d.type === 'joint_states') { setJoints(d.positions_deg); setLastTs(d.timestamp) }
        if (d.type === 'tcp_pose') setTcp(d)
        if (d.type === 'current_tool' || d.type === 'current_t') setCurrentTool(d.name)
        if (d.type === 'current_tcp') setCurrentTcpName(d.name)
        if (d.type === 'connection_status') setRosAlive(d.connected)
        if (d.type === 'log') {
            const nextId = ++programLogIdRef.current
            setProgramLogs(prev => [...prev.slice(-199), { id: nextId, ts: Date.now(), msg: d.msg, type: 'info' }])
        }
    }, [])

    const ws = useWS(`ws://${location.hostname}:8000/ws`, onMsg, authenticated)
    const ros = ws === 'connected' && rosAlive

    useEffect(() => {
        const loadAuth = async () => {
            try {
                const r = await fetch('/api/auth/status')
                const d = await r.json()
                setAuthenticated(Boolean(d.authenticated))
            } catch {
                setAuthenticated(false)
            } finally {
                setAuthChecked(true)
            }
        }

        loadAuth()
    }, [])

    useEffect(() => {
        if (!authenticated) return
        if (ws === 'connected') addLog('ROS 2 bridge connected.', 'success')
        if (ws === 'disconnected') addLog('Reconnecting…', 'warning')
    }, [ws, addLog, authenticated])

    useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [logs])
    useEffect(() => {
        if (!authenticated) return
        const loadVisionCommands = async () => {
            try {
                const r = await fetch('/api/vision/commands')
                const d = await r.json()
                if (d.success && Array.isArray(d.commands)) {
                    setSavedVisionCommands(d.commands)
                }
            } catch (error) {
                addLog(`Vision commands could not be loaded: ${error.message || 'request failed'}`, 'warning')
            }
        }

        loadVisionCommands()
    }, [addLog, authenticated])

    const doLogin = async ({ username, password }) => {
        setAuthBusy(true)
        setAuthError('')
        try {
            const r = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            })
            const d = await r.json()
            if (!r.ok || !d.success) {
                setAuthError(d.detail || d.error || 'Login failed')
                return
            }
            setAuthenticated(true)
        } catch (error) {
            setAuthError(error.message || 'Login failed')
        } finally {
            setAuthBusy(false)
            setAuthChecked(true)
        }
    }

    const doLogout = async () => {
        try {
            await fetch('/api/auth/logout', { method: 'POST' })
        } catch { }
        setAuthenticated(false)
        setAuthError('')
    }

    const statusLabel = { connected: 'Live', connecting: 'Connecting…', disconnected: 'Offline', error: 'Error' }[ws]
    const fmtTs = ts => ts ? new Date(ts * 1000).toLocaleTimeString('en-GB', { hour12: false }) : '--'

    const doHome = async () => { addLog('HOME…', 'info'); const r = await post('/api/home', {}); addLog(r.success ? '✔ Home sent' : '✘ Failed', r.success ? 'success' : 'error') }
    const doStop = async () => { addLog('STOP!', 'warning'); await post('/api/move/stop', {}); addLog('Stop sent.', 'warning') }
    const doVisionTrigger = async (commandOverride) => {
        const commandToSend = typeof commandOverride === 'string'
            ? commandOverride.trim()
            : visionCommand.trim()

        if (!commandToSend) {
            addLog('Enter a vision command first.', 'warning')
            return
        }

        setVisionBusy(true)
        setVisionCommand(commandToSend)
        addLog(`Sending Vision Command: ${commandToSend}...`, 'info')

        try {
            const r = await post('/api/vision/trigger', { command: commandToSend })
            if (r.success) {
                addLog(`Vision Trigger Success: ${r.message}`, 'success')
                if (r.vision_data) {
                    setVisionData(r.vision_data)
                    addLog(`Vision Array Received: ${r.vision_data}`, 'success')
                }
            } else {
                addLog(`Vision Error: ${r.message}`, 'error')
            }
        } catch (error) {
            addLog(`Vision Error: ${error.message || 'Request failed'}`, 'error')
        } finally {
            setVisionBusy(false)
        }
    }
    const saveVisionCommand = async () => {
        const name = visionCommandName.trim()
        const command = visionCommand.trim()

        if (!name) {
            addLog('Enter a name before saving the command.', 'warning')
            return
        }

        if (!command) {
            addLog('Enter a command before saving it.', 'warning')
            return
        }

        try {
            const r = await post('/api/vision/commands', { name, command })
            if (!r.success) {
                addLog(`Save failed: ${r.error || 'unknown error'}`, 'error')
                return
            }

            setSavedVisionCommands(Array.isArray(r.commands) ? r.commands : [])
            setVisionCommandName('')
            addLog(`Saved vision command "${name}".`, 'success')
        } catch (error) {
            addLog(`Save failed: ${error.message || 'request failed'}`, 'error')
        }
    }
    const removeVisionCommand = async (name) => {
        try {
            const r = await post('/api/vision/commands/delete', { name })
            if (!r.success) {
                addLog(`Delete failed: ${r.error || 'unknown error'}`, 'error')
                return
            }

            setSavedVisionCommands(Array.isArray(r.commands) ? r.commands : [])
            addLog(`Removed saved command "${name}".`, 'warning')
        } catch (error) {
            addLog(`Delete failed: ${error.message || 'request failed'}`, 'error')
        }
    }

    if (!authChecked) {
        return (
            <div className="app" style={{ justifyContent: 'center', alignItems: 'center', padding: 24, color: 'var(--text-2)' }}>
                Checking session...
            </div>
        )
    }

    if (!authenticated) {
        return <LoginScreen busy={authBusy} error={authError} onSubmit={doLogin} />
    }

    return (
        <div className="app">
            {/* Topbar */}
            <header className="topbar">
                <div className="topbar-brand">
                    <div className="logo-box"></div>
                    <div>
                        <h1>Operator of the Future<span style={{ color: 'var(--text-2)', fontWeight: 400 }}> · Affix Engineering B.V.</span></h1>
                        <span>ROS 2 Humble</span>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button className="btn btn-danger" style={{ padding: '7px 14px' }} onClick={doStop}>Stop</button>
                    <button className="btn btn-secondary" style={{ padding: '7px 14px' }} onClick={doLogout}>Logout</button>
                    <div className="status-badge">
                        <div className={`status-dot ${ws}`} />{statusLabel}
                    </div>
                </div>
            </header>

            {/* Tab bar */}
            <div style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)', padding: '0 28px', display: 'flex', gap: 4 }}>
                {TABS.map(t => (
                    <button key={t.id} onClick={() => setTab(t.id)} style={{
                        background: 'none', border: 'none', cursor: 'pointer', padding: '12px 20px',
                        fontFamily: 'inherit', fontSize: '0.85rem', fontWeight: tab === t.id ? 600 : 400,
                        color: tab === t.id ? 'var(--accent)' : 'var(--text-2)',
                        borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
                        transition: 'all 0.15s'
                    }}>{t.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div style={{ flex: 1, padding: '20px 28px', maxWidth: (tab === 'operation' || tab === 'program' || tab === 'all-images' || tab === 'results' || tab === 'vision-db') ? '100%' : 1400, margin: '0 auto', width: '100%', overflow: 'auto' }}>

                {/* ── CONTROL TAB ── */}
                {tab === 'control' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

                        {/* Row 1: Joints + TCP */}
                        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 20 }}>
                            {/* Joints */}
                            <div className="card">
                                <div className="card-title">Joint States</div>
                                <div className="joints-grid">
                                    {JOINT_NAMES.map((n, i) => <JointCard key={n} name={n} deg={joints[i] || 0} />)}
                                </div>
                            </div>
                            {/* TCP + System info */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                <div className="card" style={{ flex: 1 }}>
                                    <div className="card-title">TCP Position</div>
                                    <TcpRow tcp={tcp} />
                                </div>
                                <div className="card">
                                    <div className="card-title">System</div>
                                    <div className="info-row"><span className="label">Mode</span><span className="val" style={{ color: 'var(--success)' }}>Auto-Detect (ROS)</span></div>
                                    <div className="info-row"><span className="label">Robot IP</span><span className="val">Configured in Launch</span></div>
                                    <div className="info-row"><span className="label">Last Tick</span><span className="val">{fmtTs(lastTs)}</span></div>
                                </div>
                                <div className="card">
                                    <div className="card-title">Robot Speed Override</div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                        <input
                                            type="range" min="1" max="100" value={globalSpeed}
                                            onChange={(e) => setGlobalSpeed(parseInt(e.target.value))}
                                            onMouseUp={async (e) => {
                                                if (!ros) return addLog('Not connected to ROS', 'error')
                                                const val = parseInt(e.target.value)
                                                try {
                                                    const r = await post('/api/speed', { speed: val })
                                                    if (r.success) addLog(`Speed set to ${val}%`, 'info')
                                                    else addLog('Failed to set speed', 'error')
                                                } catch { addLog('Speed request failed', 'error') }
                                            }}
                                            style={{ flex: 1 }}
                                        />
                                        <span id="ctrl-speed-label" style={{ fontWeight: 600, minWidth: 40, textAlign: 'right' }}>{globalSpeed}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Row 2: Jog panel + 3D Viewer */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                            <div className="card" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                                <div className="card-title" style={{ padding: '16px 16px 0 16px', marginBottom: 12 }}>3D Robot Simulation</div>
                                <ViewerPanel currentTcpName={currentTcpName} />
                            </div>
                            <div className="card">
                                <div className="card-title">Jogging & Move to Target</div>
                                <JogButtons joints={joints} tcp={tcp} ros={ros} />
                            </div>
                        </div>

                        {/* Row 3: Log */}
                        <div className="card">
                            <div className="card-title">System Log</div>
                            <div className="log-entries" ref={logRef}>
                                {logs.map((l, i) => (
                                    <div key={i} className={`log-entry ${l.type}`}>
                                        [{new Date(l.ts).toLocaleTimeString('en-GB', { hour12: false })}] {l.text}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {tab === 'operation' && <OperationPanel ros={ros} speed={globalSpeed} setSpeed={setGlobalSpeed} joints={joints} tcp={tcp} currentTool={currentTool} currentTcpName={currentTcpName} programLogs={programLogs} />}
                {tab === 'io' && <IOPanel ros={ros} />}
                {tab === 'variables' && <VariablesPanel />}
                {tab === 'program' && <ProgramPanel ros={ros} />}
                {tab === 'vision' && (() => {
                    let parsedUI = null;
                    if (visionData) {
                        const items = visionData.split(';').filter(x => x !== '');
                        if (items.length >= 20) {
                            const pick = items.slice(3, 9).map(Number);
                            const place = items.slice(13, 19).map(Number);
                            const poseCard = (title, values, accent) => (
                                <div style={{
                                    background: 'var(--bg-base)',
                                    border: '1px solid var(--border)',
                                    borderTop: `3px solid ${accent}`,
                                    borderRadius: 8,
                                    padding: 12
                                }}>
                                    <div style={{ fontSize: '0.78rem', color: 'var(--text-2)', textTransform: 'uppercase', marginBottom: 10, fontWeight: 700, letterSpacing: '0.04em' }}>
                                        {title}
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
                                        {['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'].map((label, index) => (
                                            <div key={`${title}-${label}`} style={{
                                                background: 'var(--bg-card2)',
                                                border: '1px solid var(--border)',
                                                borderRadius: 6,
                                                padding: '8px 10px'
                                            }}>
                                                <div style={{ color: 'var(--text-3)', fontSize: '0.68rem', textTransform: 'uppercase', marginBottom: 4 }}>
                                                    {label}
                                                </div>
                                                <div style={{ color: 'var(--text-1)', fontSize: '0.92rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                                                    {values[index]}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )

                            parsedUI = (
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                                    {poseCard('Pick Point', pick, '#f4460b')}
                                    {poseCard('Place Point', place, '#2f5667')}
                                </div>
                            );
                        }
                    }
                    return (
                        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '16px 18px' }}>
                            <div className="card-title">Vision TCP Integration (192.168.137.110:50005)</div>
                            <p style={{ color: 'var(--text-3)', fontSize: '0.82rem', margin: 0 }}>
                                Send a command, keep common ones as saved buttons, and review the latest response below.
                            </p>
                            
                            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 220px) auto minmax(180px, 240px) auto', gap: 10, alignItems: 'center' }}>
                                <input 
                                    type="text" 
                                    value={visionCommand} 
                                    onChange={(e) => setVisionCommand(e.target.value)}
                                    placeholder="Enter command (e.g. 100;1)"
                                    style={{
                                        width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)',
                                        borderRadius: 6, padding: '9px 12px', color: 'var(--text-1)', fontFamily: 'monospace',
                                        fontSize: '0.95rem', outline: 'none'
                                    }}
                                />
                                <button className="btn btn-primary" style={{ padding: '10px 24px', fontSize: '0.95rem' }} onClick={doVisionTrigger} disabled={visionBusy}>
                                    {visionBusy ? '⏳ Waiting for reply...' : '📷 Send Command'}
                                </button>
                                <input
                                    type="text"
                                    value={visionCommandName}
                                    onChange={(e) => setVisionCommandName(e.target.value)}
                                    placeholder="Save as name"
                                    style={{
                                        width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)',
                                        borderRadius: 6, padding: '9px 12px', color: 'var(--text-1)',
                                        fontSize: '0.95rem', outline: 'none'
                                    }}
                                />
                                <button className="btn btn-secondary" style={{ padding: '10px 18px', fontSize: '0.95rem' }} onClick={saveVisionCommand}>
                                    Save Command
                                </button>
                            </div>

                            <div style={{
                                background: 'var(--bg-base)',
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                padding: 12,
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 10
                            }}>
                                <div style={{ fontSize: '0.76rem', color: 'var(--text-2)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.04em' }}>
                                    Saved Commands
                                </div>

                                {savedVisionCommands.length === 0 ? (
                                    <div style={{ color: 'var(--text-3)', fontSize: '0.82rem' }}>
                                        No saved commands yet.
                                    </div>
                                ) : (
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                                        {savedVisionCommands.map((item) => (
                                            <div key={item.name} style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: 8,
                                                padding: '7px 10px',
                                                borderRadius: 9999,
                                                border: '1px solid var(--border)',
                                                background: 'var(--bg-card2)'
                                            }}>
                                                <button
                                                    className="btn btn-secondary"
                                                    style={{ padding: '8px 12px', fontSize: '0.88rem' }}
                                                    onClick={() => doVisionTrigger(item.command)}
                                                    title={`Send command: ${item.command}`}
                                                >
                                                    {item.name}
                                                </button>
                                                <button
                                                    style={{
                                                        background: 'transparent',
                                                        border: 'none',
                                                        color: 'var(--accent)',
                                                        fontSize: '0.85rem',
                                                        fontFamily: 'monospace',
                                                        cursor: 'pointer',
                                                        padding: 0
                                                    }}
                                                    onClick={() => setVisionCommand(item.command)}
                                                    title="Load into input"
                                                >
                                                    {item.command}
                                                </button>
                                                <button
                                                    className="btn btn-danger"
                                                    style={{ padding: '7px 10px', fontSize: '0.8rem' }}
                                                    onClick={() => removeVisionCommand(item.name)}
                                                    title={`Delete ${item.name}`}
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {parsedUI}

                            <div style={{ background: '#0a0f1c', border: '1px solid var(--border)', borderRadius: 8, padding: 14, minHeight: 96 }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', textTransform: 'uppercase', marginBottom: 8, fontWeight: 700, letterSpacing: '0.04em' }}>
                                    Raw Vision Data
                                </div>
                                <div style={{ fontFamily: 'monospace', color: 'var(--success)', fontSize: '1rem', lineHeight: 1.45, wordBreak: 'break-all' }}>
                                    {visionData || <span style={{ color: 'var(--text-3)' }}>No data yet.</span>}
                                </div>
                            </div>
                        </div>
                    );
                })()}
                {tab === 'vision-db' && <VisionDbPanel />}
                {tab === 'results' && <ResultsPanel />}
                {tab === 'all-images' && <AllImagesPanel />}
            </div>
        </div>
    )
}
