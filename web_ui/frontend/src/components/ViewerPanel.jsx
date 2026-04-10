import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { ColladaLoader } from 'three/examples/jsm/loaders/ColladaLoader.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import * as ROSLIB from 'roslib'

const VIEWER_HEIGHT = 480

function stripPackageUrl(uri = '') {
    return uri.startsWith('package://') ? uri.slice('package://'.length) : uri
}

function applyRosPose(object, pose) {
    if (!object || !pose) return

    object.position.set(
        pose.position?.x ?? 0,
        pose.position?.y ?? 0,
        pose.position?.z ?? 0,
    )
    object.quaternion.set(
        pose.orientation?.x ?? 0,
        pose.orientation?.y ?? 0,
        pose.orientation?.z ?? 0,
        pose.orientation?.w ?? 1,
    )
}

function createPrimitiveMesh(geometry, material) {
    if (!geometry) return null

    if (geometry.dimension) {
        return new THREE.Mesh(
            new THREE.BoxGeometry(geometry.dimension.x, geometry.dimension.y, geometry.dimension.z),
            material,
        )
    }

    if (typeof geometry.radius === 'number' && typeof geometry.length === 'number') {
        const mesh = new THREE.Mesh(
            new THREE.CylinderGeometry(geometry.radius, geometry.radius, geometry.length, 24),
            material,
        )
        mesh.rotation.x = Math.PI / 2
        return mesh
    }

    if (typeof geometry.radius === 'number') {
        return new THREE.Mesh(
            new THREE.SphereGeometry(geometry.radius, 24, 24),
            material,
        )
    }

    return null
}

function createLinkFallbackSegment(joint) {
    const x = joint.origin?.position?.x ?? 0
    const y = joint.origin?.position?.y ?? 0
    const z = joint.origin?.position?.z ?? 0
    const target = new THREE.Vector3(x, y, z)
    const length = target.length()

    if (length < 0.001) return null

    const radius = Math.min(Math.max(length * 0.08, 0.025), 0.08)
    const mesh = new THREE.Mesh(
        new THREE.CylinderGeometry(radius, radius, length, 16),
        new THREE.MeshStandardMaterial({
            color: new THREE.Color('#6ea4c7'),
            metalness: 0.2,
            roughness: 0.75,
            transparent: true,
            opacity: 0.9,
        }),
    )

    const direction = target.clone().normalize()
    const midpoint = target.clone().multiplyScalar(0.5)
    const up = new THREE.Vector3(0, 1, 0)
    mesh.quaternion.setFromUnitVectors(up, direction)
    mesh.position.copy(midpoint)
    return mesh
}

function createJointMarker() {
    return new THREE.Mesh(
        new THREE.SphereGeometry(0.035, 18, 18),
        new THREE.MeshStandardMaterial({
            color: new THREE.Color('#f97316'),
            metalness: 0.1,
            roughness: 0.55,
        }),
    )
}

export default function ViewerPanel({ currentTcpName = 'tcp_gripper_A' }) {
    const viewerRef = useRef(null)
    const effectRunIdRef = useRef(0)
    const currentTcpNameRef = useRef(currentTcpName)
    const refreshToolVisualRef = useRef(null)
    const loadToolOffsetsRef = useRef(null)
    const toolOffsetsRef = useRef({})
    const linkNodesRef = useRef(new Map())
    const toolVisualGroupRef = useRef(null)
    const [rosbridgeStatus, setRosbridgeStatus] = useState('connecting')
    const [viewerStatus, setViewerStatus] = useState('Waiting for robot model...')
    const [debugLines, setDebugLines] = useState([])

    useEffect(() => {
        currentTcpNameRef.current = currentTcpName
        if (loadToolOffsetsRef.current) {
            void loadToolOffsetsRef.current()
        } else {
            refreshToolVisualRef.current?.()
        }
    }, [currentTcpName])

    useEffect(() => {
        if (!viewerRef.current) return

        const runId = ++effectRunIdRef.current
        let renderer = null
        let scene = null
        let camera = null
        let controls = null
        let resizeObserver = null
        let animationFrame = null
        let ros = null
        let jointTopic = null
        let fallbackTried = false
        let cleanedUp = false

        const jointNodes = new Map()
        const latestJointPositions = new Map()
        const linkNodes = linkNodesRef.current
        const colladaLoader = new ColladaLoader()
        const stlLoader = new STLLoader()
        linkNodes.clear()
        const pushDebug = (line) => {
            setDebugLines((prev) => [...prev.slice(-1), line])
        }
        const isActiveRun = () => !cleanedUp && effectRunIdRef.current === runId

        const sameOriginProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const sameOriginUrl = `${sameOriginProtocol}//${window.location.host}/rosbridge`
        const directUrl = `ws://${window.location.hostname}:9090`
        const meshBaseUrl = `${window.location.origin}/`

        const buildStlFallbackUrl = (resource) => {
            const fileName = resource.split('/').pop()
            if (!fileName || !fileName.toLowerCase().endsWith('.dae')) return null
            const stem = fileName.slice(0, -4)
            return `${window.location.origin}/dsr_description2/mujoco_assets/h2017/assets/${stem}.stl`
        }

        const refreshToolVisual = () => {
            if (!isActiveRun()) return
            const link6 = linkNodes.get('link_6')
            if (!link6) return

            if (toolVisualGroupRef.current) {
                link6.remove(toolVisualGroupRef.current)
            }

            const tcpName = currentTcpNameRef.current
            const offsets = toolOffsetsRef.current?.[tcpName] ?? [0, 0, 120, 0, 0, 0]
            const [xMm = 0, yMm = 0, zMm = 120, rxDeg = 0, ryDeg = 0, rzDeg = 0] = offsets
            const rawTcpVector = new THREE.Vector3(xMm / 1000, yMm / 1000, zMm / 1000)
            const outwardAxis = new THREE.Vector3(0, 0, 1)
            const tcpVector =
                rawTcpVector.lengthSq() > 1e-8 && rawTcpVector.dot(outwardAxis) < 0
                    ? rawTcpVector.clone().negate()
                    : rawTcpVector
            const length = Math.max(Math.min(tcpVector.length(), 0.45), 0.04)

            const group = new THREE.Group()
            group.name = 'tcp-visual'

            const shaft = new THREE.Mesh(
                new THREE.CylinderGeometry(0.028, 0.028, length, 18),
                new THREE.MeshStandardMaterial({
                    color: new THREE.Color('#cdd6df'),
                    metalness: 0.45,
                    roughness: 0.45,
                }),
            )
            const shaftDirection = tcpVector.lengthSq() > 1e-8
                ? tcpVector.clone().normalize()
                : new THREE.Vector3(0, 0, 1)
            shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), shaftDirection)
            shaft.position.copy(shaftDirection.clone().multiplyScalar(length * 0.5))
            group.add(shaft)

            const tip = new THREE.Mesh(
                new THREE.BoxGeometry(0.05, 0.05, 0.045),
                new THREE.MeshStandardMaterial({
                    color: new THREE.Color('#f97316'),
                    metalness: 0.15,
                    roughness: 0.5,
                }),
            )
            tip.position.copy(tcpVector)
            tip.rotation.set(
                THREE.MathUtils.degToRad(rxDeg),
                THREE.MathUtils.degToRad(ryDeg),
                THREE.MathUtils.degToRad(rzDeg),
            )
            group.add(tip)

            const tcpMarker = new THREE.Mesh(
                new THREE.SphereGeometry(0.014, 16, 16),
                new THREE.MeshStandardMaterial({
                    color: new THREE.Color('#22c55e'),
                    metalness: 0.1,
                    roughness: 0.4,
                }),
            )
            tcpMarker.position.copy(tcpVector)
            group.add(tcpMarker)

            toolVisualGroupRef.current = group
            link6.add(group)
            pushDebug(`TCP visual: ${tcpName} (${xMm.toFixed?.(1) ?? xMm}, ${yMm.toFixed?.(1) ?? yMm}, ${zMm.toFixed?.(1) ?? zMm} mm)`)
        }
        refreshToolVisualRef.current = refreshToolVisual

        const loadToolOffsets = async () => {
            try {
                const response = await fetch('/api/tools/offsets', { credentials: 'include' })
                const data = await response.json()
                if (!isActiveRun()) return
                if (!response.ok || !data.success) return
                toolOffsetsRef.current = data.offsets ?? {}
                if (data.live?.name && Array.isArray(data.live.offsets)) {
                    pushDebug(`Live TCP offset: ${data.live.name} -> ${data.live.offsets.join(', ')}`)
                }
                refreshToolVisual()
            } catch {
                if (!isActiveRun()) return
                toolOffsetsRef.current = {}
                refreshToolVisual()
            }
        }
        loadToolOffsetsRef.current = loadToolOffsets

        const renderLoop = () => {
            if (cleanedUp || !renderer || !scene || !camera) return
            controls?.update()
            renderer.render(scene, camera)
            animationFrame = window.requestAnimationFrame(renderLoop)
        }

        const initThreeViewer = () => {
            if (!viewerRef.current || renderer || !isActiveRun()) return

            scene = new THREE.Scene()
            scene.background = new THREE.Color('#060a14')

            camera = new THREE.PerspectiveCamera(
                45,
                (viewerRef.current.clientWidth || 400) / VIEWER_HEIGHT,
                0.01,
                100,
            )
            camera.position.set(2.8, 2.2, 1.8)
            camera.up.set(0, 0, 1)

            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
            renderer.setPixelRatio(window.devicePixelRatio || 1)
            renderer.setSize(viewerRef.current.clientWidth || 400, VIEWER_HEIGHT)
            viewerRef.current.innerHTML = ''
            viewerRef.current.appendChild(renderer.domElement)

            controls = new OrbitControls(camera, renderer.domElement)
            controls.enableDamping = true
            controls.target.set(0, 0, 0.6)
            controls.update()

            scene.add(new THREE.AmbientLight(0xffffff, 1.3))

            const keyLight = new THREE.DirectionalLight(0xffffff, 1.4)
            keyLight.position.set(3, 4, 5)
            scene.add(keyLight)

            const fillLight = new THREE.DirectionalLight(0x8fb3ff, 0.6)
            fillLight.position.set(-3, -2, 4)
            scene.add(fillLight)

            const grid = new THREE.GridHelper(4, 20, 0x315a8d, 0x213448)
            grid.rotation.x = Math.PI / 2
            scene.add(grid)

            const axes = new THREE.AxesHelper(0.4)
            scene.add(axes)

            resizeObserver = new ResizeObserver(() => {
                if (!viewerRef.current || !renderer || !camera) return
                const width = viewerRef.current.clientWidth || 400
                camera.aspect = width / VIEWER_HEIGHT
                camera.updateProjectionMatrix()
                renderer.setSize(width, VIEWER_HEIGHT)
            })
            resizeObserver.observe(viewerRef.current)

            renderLoop()
            pushDebug('3D viewer ready')
        }

        const ensureFallbackForLink = (linkRoot) => {
            if (!linkRoot || linkRoot.userData.fallbackAdded) return

            const childJoints = linkRoot.userData.childJoints ?? []
            if (childJoints.length > 0) {
                childJoints.forEach((joint) => {
                    const fallbackSegment = createLinkFallbackSegment(joint)
                    if (fallbackSegment) {
                        linkRoot.add(fallbackSegment)
                    }
                })
            }

            if (!linkRoot.userData.jointMarkerAdded) {
                linkRoot.add(createJointMarker())
                linkRoot.userData.jointMarkerAdded = true
            }

            linkRoot.userData.fallbackAdded = true
        }

        const loadVisualIntoLink = async (linkRoot, visual) => {
            if (!visual?.geometry || !isActiveRun()) return

            const visualRoot = new THREE.Group()
            applyRosPose(visualRoot, visual.origin)
            linkRoot.add(visualRoot)

            const color = visual.material?.color
            const material = new THREE.MeshStandardMaterial({
                color: color
                    ? new THREE.Color(color.r ?? 0.7, color.g ?? 0.7, color.b ?? 0.7)
                    : new THREE.Color('#c9d4e3'),
                transparent: Boolean(color && typeof color.a === 'number' && color.a < 1),
                opacity: color && typeof color.a === 'number' ? color.a : 1,
                metalness: 0.15,
                roughness: 0.7,
            })

            if (visual.geometry.filename) {
                const resource = stripPackageUrl(visual.geometry.filename)
                const meshUrl = `${meshBaseUrl}${resource}`
                try {
                    const preflight = await fetch(meshUrl, { method: 'GET', credentials: 'include' })
                    if (!isActiveRun()) return
                    if (!preflight.ok) {
                        pushDebug(`Mesh HTTP ${preflight.status}: ${resource.split('/').slice(-1)[0]}`)
                        ensureFallbackForLink(linkRoot)
                        return
                    }
                } catch (error) {
                    pushDebug(`Mesh fetch error: ${error.message || 'unknown error'}`)
                    ensureFallbackForLink(linkRoot)
                    return
                }

                colladaLoader.load(
                    meshUrl,
                    (collada) => {
                        if (!isActiveRun()) return
                        const model = collada.scene
                        if (visual.geometry.scale) {
                            model.scale.set(
                                visual.geometry.scale.x ?? 1,
                                visual.geometry.scale.y ?? 1,
                                visual.geometry.scale.z ?? 1,
                            )
                        }

                        model.traverse((child) => {
                            if (child.isMesh) {
                                child.material = material
                            }
                        })

                        visualRoot.add(model)
                        linkRoot.userData.hasVisualMesh = true
                    },
                    undefined,
                    (error) => {
                        if (!isActiveRun()) return
                        const msg =
                            error?.message ||
                            error?.target?.src ||
                            error?.currentTarget?.src ||
                            'unknown collada error'
                        pushDebug(`Mesh parse error: ${msg}`)

                        const stlUrl = buildStlFallbackUrl(resource)
                        if (!stlUrl) {
                            ensureFallbackForLink(linkRoot)
                            return
                        }

                        stlLoader.load(
                            stlUrl,
                            (geometry) => {
                                if (!isActiveRun()) return
                                geometry.computeVertexNormals()
                                const stlMesh = new THREE.Mesh(geometry, material)
                                if (visual.geometry.scale) {
                                    stlMesh.scale.set(
                                        visual.geometry.scale.x ?? 1,
                                        visual.geometry.scale.y ?? 1,
                                        visual.geometry.scale.z ?? 1,
                                    )
                                }
                                visualRoot.add(stlMesh)
                                linkRoot.userData.hasVisualMesh = true
                            },
                            undefined,
                            () => {
                                if (!isActiveRun()) return
                                pushDebug(`STL load failed: ${stlUrl}`)
                                ensureFallbackForLink(linkRoot)
                            },
                        )
                    },
                )
                return
            }

            const primitive = createPrimitiveMesh(visual.geometry, material)
            if (primitive) {
                visualRoot.add(primitive)
                linkRoot.userData.hasVisualMesh = true
            } else {
                ensureFallbackForLink(linkRoot)
            }
        }

        const applyJointStates = () => {
            for (const [jointName, value] of latestJointPositions.entries()) {
                const jointNode = jointNodes.get(jointName)
                if (!jointNode) continue

                jointNode.quaternion.copy(jointNode.userData.baseQuaternion)

                const axis = jointNode.userData.axis
                if (!axis || axis.lengthSq() === 0) continue

                const q = new THREE.Quaternion().setFromAxisAngle(axis, value)
                jointNode.quaternion.multiply(q)
            }
        }

        const buildRobotFromUrdf = (urdfText) => {
            if (!isActiveRun()) return
            initThreeViewer()
            jointNodes.clear()
            linkNodes.clear()

            const urdfModel = new ROSLIB.UrdfModel({ string: urdfText })
            const robotRoot = new THREE.Group()
            robotRoot.name = 'robot-root'
            scene.add(robotRoot)

            const jointsByParent = new Map()
            const childLinkSet = new Set()

            Object.values(urdfModel.links).forEach((link) => {
                if (['tool_changer_base', 'tcp_gripper_A', 'tcp_gripper_B', 'cell_link', 'world'].includes(link.name)) {
                    return
                }
                const linkRoot = new THREE.Group()
                linkRoot.name = link.name
                linkRoot.userData.hasVisualMesh = false
                linkRoot.userData.fallbackAdded = false
                linkRoot.userData.jointMarkerAdded = false
                link.visuals.forEach((visual) => {
                    void loadVisualIntoLink(linkRoot, visual)
                })
                linkNodes.set(link.name, linkRoot)
            })

            Object.values(urdfModel.joints).forEach((joint) => {
                if (!joint.parent || !joint.child) return
                if (!linkNodes.has(joint.parent) || !linkNodes.has(joint.child)) return

                childLinkSet.add(joint.child)

                const list = jointsByParent.get(joint.parent) ?? []
                list.push(joint)
                jointsByParent.set(joint.parent, list)
            })

            const attachLink = (linkName, parentObject) => {
                const linkRoot = linkNodes.get(linkName)
                if (!linkRoot) return

                parentObject.add(linkRoot)

                const childJoints = jointsByParent.get(linkName) ?? []
                linkRoot.userData.childJoints = childJoints
                if (linkRoot.children.length === 0) {
                    ensureFallbackForLink(linkRoot)
                } else if (!linkRoot.userData.jointMarkerAdded) {
                    linkRoot.add(createJointMarker())
                    linkRoot.userData.jointMarkerAdded = true
                }

                childJoints.forEach((joint) => {
                    const jointOriginNode = new THREE.Group()
                    jointOriginNode.name = `${joint.name}-origin`
                    applyRosPose(jointOriginNode, joint.origin)

                    const jointMotionNode = new THREE.Group()
                    jointMotionNode.name = `${joint.name}-motion`
                    jointMotionNode.userData.axis = new THREE.Vector3(
                        joint.axis?.x ?? 1,
                        joint.axis?.y ?? 0,
                        joint.axis?.z ?? 0,
                    ).normalize()
                    jointMotionNode.userData.baseQuaternion = jointMotionNode.quaternion.clone()

                    jointNodes.set(joint.name, jointMotionNode)

                    jointOriginNode.add(jointMotionNode)
                    linkRoot.add(jointOriginNode)
                    attachLink(joint.child, jointMotionNode)
                })
            }

            const rootLinks = [...linkNodes.keys()].filter((linkName) => !childLinkSet.has(linkName))
            const preferredRoot = rootLinks.includes('world')
                ? ['world']
                : rootLinks.includes('base_link')
                    ? ['base_link']
                    : rootLinks

            preferredRoot.forEach((rootLinkName) => attachLink(rootLinkName, robotRoot))

            applyJointStates()
            refreshToolVisual()

            pushDebug(`URDF parsed: ${Object.keys(urdfModel.links).length} links, ${Object.keys(urdfModel.joints).length} joints`)
            setViewerStatus('Robot model loaded')
        }

        const requestRobotDescription = async () => {
            if (!isActiveRun()) return
            setViewerStatus('Requesting URDF from backend...')

            try {
                const response = await fetch('/api/robot/urdf', { credentials: 'include' })
                const data = await response.json()

                if (!isActiveRun()) return

                if (!response.ok || !data.success || typeof data.urdf !== 'string') {
                    pushDebug(`URDF fetch error: ${data.error || response.status}`)
                    setViewerStatus('Failed to load URDF')
                    return
                }

                setViewerStatus('Building robot model...')
                buildRobotFromUrdf(data.urdf)
            } catch (error) {
                pushDebug(`URDF fetch exception: ${error.message || 'unknown error'}`)
                setViewerStatus('URDF request failed')
            }
        }

        const subscribeJointStates = () => {
            jointTopic = new ROSLIB.Topic({
                ros,
                name: '/joint_states',
                messageType: 'sensor_msgs/msg/JointState',
            })

            jointTopic.subscribe((msg) => {
                if (!msg?.name || !msg?.position) return

                msg.name.forEach((name, index) => {
                    latestJointPositions.set(name, msg.position[index] ?? 0)
                })

                applyJointStates()
            })

            pushDebug('Joint state stream active')
        }

        const connectRos = (url, allowFallback) => {
            if (cleanedUp) return

            setRosbridgeStatus('connecting')
            setViewerStatus(`Connecting to rosbridge... (${url})`)

            const nextRos = new ROSLIB.Ros({ url })
            ros = nextRos

            nextRos.on('connection', () => {
                if (!isActiveRun() || ros !== nextRos) return
                setRosbridgeStatus('connected')
                pushDebug(`Rosbridge connected`)
                subscribeJointStates()
                void loadToolOffsets()
                void requestRobotDescription()
            })

            nextRos.on('error', () => {
                if (!isActiveRun() || ros !== nextRos) return
                pushDebug(`Rosbridge error: ${url}`)

                if (allowFallback && !fallbackTried) {
                    fallbackTried = true
                    setViewerStatus(`Proxy failed, trying direct 9090... (${url})`)
                    try { nextRos.close() } catch { }
                    connectRos(directUrl, false)
                    return
                }

                setRosbridgeStatus('error')
                setViewerStatus(`Rosbridge connection error (${url})`)
            })

            nextRos.on('close', () => {
                if (!isActiveRun() || ros !== nextRos) return
                pushDebug(`Rosbridge closed`)

                if (allowFallback && !fallbackTried) {
                    fallbackTried = true
                    setViewerStatus(`Proxy closed, trying direct 9090... (${url})`)
                    connectRos(directUrl, false)
                    return
                }

                setRosbridgeStatus('disconnected')
                setViewerStatus(`Rosbridge connection closed (${url})`)
            })
        }

        connectRos(sameOriginUrl, true)

        return () => {
            refreshToolVisualRef.current = null
            loadToolOffsetsRef.current = null
            toolVisualGroupRef.current = null
            linkNodes.clear()
            cleanedUp = true
            jointTopic?.unsubscribe?.()
            resizeObserver?.disconnect()
            if (animationFrame) window.cancelAnimationFrame(animationFrame)
            controls?.dispose?.()
            renderer?.dispose?.()
            if (viewerRef.current) viewerRef.current.innerHTML = ''
            try { ros?.close() } catch { }
        }
    }, [])
    const rosBadgeColor =
        rosbridgeStatus === 'connected'
            ? 'var(--success)'
            : rosbridgeStatus === 'error'
                ? 'var(--danger)'
                : 'var(--warning)'

    return (
        <div style={{ position: 'relative', width: '100%', display: 'flex', flexDirection: 'column' }}>
            <div
                id="robot-viewer"
                ref={viewerRef}
                style={{
                    width: '100%',
                    height: VIEWER_HEIGHT,
                    background: '#060a14',
                    borderRadius: 8,
                    overflow: 'hidden',
                    border: '1px solid var(--border)',
                }}
            />

            <div
                style={{
                    position: 'absolute',
                    top: 10,
                    left: 10,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    pointerEvents: 'none',
                }}
            >
                <div
                    style={{
                        background: 'rgba(0,0,0,0.72)',
                        padding: '4px 8px',
                        borderRadius: 4,
                        fontSize: '0.75rem',
                        color: rosBadgeColor,
                    }}
                >
                    ROS bridge: {rosbridgeStatus}
                </div>

                <div
                    style={{
                        background: 'rgba(0,0,0,0.56)',
                        padding: '4px 8px',
                        borderRadius: 4,
                        fontSize: '0.72rem',
                        color: 'var(--text-2)',
                        maxWidth: 320,
                    }}
                >
                    View: `joint_states + robot_description` | {viewerStatus}
                </div>

                {debugLines.length > 0 && (
                    <div
                        style={{
                            background: 'rgba(0,0,0,0.48)',
                            padding: '4px 8px',
                            borderRadius: 4,
                            fontSize: '0.68rem',
                            color: '#b7c4d7',
                            maxWidth: 320,
                            whiteSpace: 'pre-wrap',
                            lineHeight: 1.35,
                        }}
                    >
                        {debugLines.join('\n')}
                    </div>
                )}
            </div>
        </div>
    )
}
