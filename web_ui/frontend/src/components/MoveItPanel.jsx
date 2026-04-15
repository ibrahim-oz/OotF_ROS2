import { useEffect, useMemo, useState } from 'react'
import ViewerPanel from './ViewerPanel.jsx'

const JOINT_NAMES = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6']
const JOINT_LABELS = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6']

function degToRad(value) {
    return (value * Math.PI) / 180
}

function interpolateTrajectory(currentJointsDeg, targetJointsDeg) {
    const samples = [0.2, 0.45, 0.7, 1.0]
    return samples.map((t, index) => ({
        label: `Waypoint ${index + 1}`,
        jointNames: JOINT_NAMES,
        positions: targetJointsDeg.map((targetDeg, jointIndex) => {
            const startDeg = currentJointsDeg[jointIndex] ?? 0
            return degToRad(startDeg + (targetDeg - startDeg) * t)
        }),
    }))
}

export default function MoveItPanel({ joints, tcp, currentTcpName }) {
    const [targetMode, setTargetMode] = useState('joint')
    const [targetJoints, setTargetJoints] = useState(() => Array(6).fill('0'))
    const [targetPose, setTargetPose] = useState(() => Array(6).fill('0'))
    const [positionToleranceMm, setPositionToleranceMm] = useState('10')
    const [orientationToleranceDeg, setOrientationToleranceDeg] = useState('10')
    const [plannedTrajectory, setPlannedTrajectory] = useState([])
    const [status, setStatus] = useState('Viewer is ready for MoveIt trajectory preview.')
    const [moveitReady, setMoveitReady] = useState(false)
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        let alive = true

        const loadStatus = async () => {
            try {
                const r = await fetch('/api/moveit/status')
                const d = await r.json()
                if (!alive) return
                setMoveitReady(Boolean(d.success && d.moveit_service_ready))
                if (d.success) {
                    setStatus(
                        d.moveit_service_ready
                            ? 'MoveIt planning service is ready. Plans in this panel come from the backend.'
                            : 'MoveIt planning service is not ready. Start move_group before testing this panel.',
                    )
                }
            } catch {
                if (!alive) return
                setMoveitReady(false)
                setStatus('MoveIt status check failed.')
            }
        }

        loadStatus()
        return () => {
            alive = false
        }
    }, [])

    const currentJointsDeg = useMemo(
        () => (Array.isArray(joints) && joints.length === 6 ? joints.map((value) => Number(value) || 0) : Array(6).fill(0)),
        [joints],
    )

    const targetJointsDeg = useMemo(
        () => targetJoints.map((value) => Number.parseFloat(value || '0') || 0),
        [targetJoints],
    )

    const setFromRobot = () => {
        if (targetMode === 'joint') {
            setTargetJoints(currentJointsDeg.map((value) => value.toFixed(2)))
            setStatus('Target joints copied from live robot state.')
        } else if (tcp) {
            setTargetPose([
                tcp.x ?? 0,
                tcp.y ?? 0,
                tcp.z ?? 0,
                tcp.rx ?? 0,
                tcp.ry ?? 0,
                tcp.rz ?? 0,
            ].map((value) => Number(value).toFixed(2)))
            setStatus('Target cartesian pose copied from live TCP state.')
        }
    }

    const previewPlan = async () => {
        setBusy(true)
        try {
            const endpoint = targetMode === 'joint' ? '/api/moveit/plan/joint' : '/api/moveit/plan/pose'
            const body = targetMode === 'joint'
                ? {
                    pos: targetJointsDeg,
                    group_name: 'manipulator',
                    allowed_planning_time: 3.0,
                    num_planning_attempts: 1,
                    max_velocity_scaling_factor: 0.25,
                    max_acceleration_scaling_factor: 0.25,
                }
                : {
                    pos: targetPose.map((value) => Number.parseFloat(value || '0') || 0),
                    group_name: 'manipulator',
                    tip_link: currentTcpName || 'tcp_gripper_A',
                    frame_id: 'base_link',
                    position_tolerance_mm: Number.parseFloat(positionToleranceMm || '10') || 10,
                    orientation_tolerance_deg: Number.parseFloat(orientationToleranceDeg || '10') || 10,
                    allowed_planning_time: 3.0,
                    num_planning_attempts: 1,
                    max_velocity_scaling_factor: 0.25,
                    max_acceleration_scaling_factor: 0.25,
                }
            const r = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            })
            const d = await r.json()
            if (!d.success) {
                setPlannedTrajectory([])
                setStatus(`MoveIt plan failed: ${d.error || 'unknown error'}${d.error_code ? ` (code ${d.error_code})` : ''}`)
                return
            }
            const trajectory = Array.isArray(d.preview_waypoints) ? d.preview_waypoints : interpolateTrajectory(currentJointsDeg, targetJointsDeg)
            setPlannedTrajectory(trajectory)
            setMoveitReady(true)
            setStatus(`MoveIt plan ready. ${d.point_count || trajectory.length} trajectory point(s) returned by backend.`)
        } catch (error) {
            setPlannedTrajectory([])
            setStatus(`MoveIt request failed: ${error.message || 'unknown error'}`)
        } finally {
            setBusy(false)
        }
    }

    const clearPlan = async () => {
        setPlannedTrajectory([])
        try {
            await fetch('/api/moveit/clear', { method: 'POST' })
        } catch { }
        setStatus('Preview trajectory cleared.')
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 0.9fr) minmax(0, 1.4fr)', gap: 14, height: 'calc(100vh - 132px)', overflow: 'hidden' }}>
            <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', minHeight: 0, gap: 12 }}>
                <div>
                    <div className="card-title" style={{ marginBottom: 6 }}>MoveIt Test</div>
                    <div style={{ color: 'var(--text-3)', fontSize: '0.84rem', lineHeight: 1.5 }}>
                        This panel is isolated from the existing motion tabs. It currently previews a test trajectory in the 3D viewer and prepares the UI for future MoveIt plan-only integration.
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <button
                        className={`btn ${targetMode === 'joint' ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '9px 14px' }}
                        onClick={() => setTargetMode('joint')}
                        disabled={busy}
                    >
                        Joint Target
                    </button>
                    <button
                        className={`btn ${targetMode === 'pose' ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '9px 14px' }}
                        onClick={() => setTargetMode('pose')}
                        disabled={busy}
                    >
                        Cartesian Target
                    </button>
                </div>

                <div style={{ display: 'grid', gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
                            {targetMode === 'joint' ? 'Target Joint Pose' : 'Target Cartesian Pose'}
                        </div>
                        <button className="btn btn-secondary" style={{ width: 'auto', padding: '5px 9px', fontSize: '0.72rem' }} onClick={setFromRobot} disabled={busy}>
                            From Robot
                        </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
                        {(targetMode === 'joint' ? JOINT_LABELS : ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']).map((label, index) => (
                            <div key={label}>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4, textAlign: 'center' }}>{label}</div>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={targetMode === 'joint' ? targetJoints[index] : targetPose[index]}
                                    onChange={(e) => {
                                        const next = [...(targetMode === 'joint' ? targetJoints : targetPose)]
                                        next[index] = e.target.value
                                        if (targetMode === 'joint') setTargetJoints(next)
                                        else setTargetPose(next)
                                    }}
                                    style={{ width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text-1)', textAlign: 'center' }}
                                />
                            </div>
                        ))}
                    </div>

                    {targetMode === 'pose' && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4, textAlign: 'center' }}>Pos Tol (mm)</div>
                                <input
                                    type="number"
                                    step="0.5"
                                    min="0.5"
                                    value={positionToleranceMm}
                                    onChange={(e) => setPositionToleranceMm(e.target.value)}
                                    style={{ width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text-1)', textAlign: 'center' }}
                                />
                            </div>
                            <div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: 4, textAlign: 'center' }}>Ori Tol (deg)</div>
                                <input
                                    type="number"
                                    step="0.5"
                                    min="0.5"
                                    value={orientationToleranceDeg}
                                    onChange={(e) => setOrientationToleranceDeg(e.target.value)}
                                    style={{ width: '100%', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text-1)', textAlign: 'center' }}
                                />
                            </div>
                        </div>
                    )}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <button className="btn btn-primary" style={{ padding: '10px 14px' }} onClick={previewPlan} disabled={busy || !moveitReady}>
                        {busy ? 'Planning…' : 'Preview Plan'}
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '10px 14px' }} onClick={clearPlan} disabled={busy}>
                        Clear Preview
                    </button>
                </div>

                <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px', fontSize: '0.82rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
                    {status}
                </div>

                <div style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
                    Live robot stays as the solid model. Planned waypoints are shown as a lightweight 3D path overlay in the viewer. Service state: <strong style={{ color: moveitReady ? 'var(--success)' : 'var(--warning)' }}>{moveitReady ? 'ready' : 'not ready'}</strong>
                </div>

                <div style={{ display: 'grid', gap: 6, minHeight: 0, overflow: 'auto' }}>
                    {plannedTrajectory.length === 0 ? (
                        <div style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>
                            No preview trajectory yet.
                        </div>
                    ) : (
                        plannedTrajectory.map((waypoint, index) => (
                            <div key={waypoint.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, borderBottom: '1px solid var(--border-light)', paddingBottom: 6, fontSize: '0.78rem' }}>
                                <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{waypoint.label}</span>
                                <span style={{ color: 'var(--text-1)', fontVariantNumeric: 'tabular-nums' }}>
                                    {targetJointsDeg.map((value, jointIndex) => {
                                        const start = currentJointsDeg[jointIndex] ?? 0
                                        const sample = [0.2, 0.45, 0.7, 1.0][index]
                                        return (start + (value - start) * sample).toFixed(1)
                                    }).join(' / ')}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px 0 14px', gap: 12 }}>
                    <div className="card-title" style={{ marginBottom: 8 }}>3D Trajectory Preview</div>
                    <div style={{
                        fontSize: '0.74rem',
                        color: 'var(--text-2)',
                        background: 'var(--bg-base)',
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '4px 8px',
                        marginBottom: 8,
                    }}>
                        Active TCP: <span style={{ color: 'var(--text-1)', fontWeight: 700 }}>{currentTcpName || 'tcp_gripper_A'}</span>
                    </div>
                </div>
                <div style={{ padding: '0 14px 14px 14px', minHeight: 0 }}>
                    <ViewerPanel
                        currentTcpName={currentTcpName}
                        viewerHeight={Math.max(window.innerHeight - 220, 420)}
                        plannedJointTrajectory={plannedTrajectory}
                        planPreviewLabel={plannedTrajectory.length > 0 ? 'MoveIt test preview' : ''}
                    />
                </div>
            </div>
        </div>
    )
}
