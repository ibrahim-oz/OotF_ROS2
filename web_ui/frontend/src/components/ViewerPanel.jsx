import { useEffect, useRef, useState } from 'react';
import * as ROSLIB from 'roslib';
import * as ROS3D from 'ros3d';

export default function ViewerPanel() {
    const viewerRef = useRef(null);
    const [status, setStatus] = useState('connecting');

    useEffect(() => {
        if (!viewerRef.current) return;

        // Connect to rosbridge
        const ros = new ROSLIB.Ros({
            url: `ws://${window.location.hostname}:9090`
        });

        ros.on('connection', () => setStatus('connected'));
        ros.on('error', () => setStatus('error'));
        ros.on('close', () => setStatus('disconnected'));

        // Initialize the 3D viewer
        const viewer = new ROS3D.Viewer({
            divID: viewerRef.current.id,
            width: viewerRef.current.clientWidth || 400,
            height: 480,
            antialias: true,
            background: '#060a14'
        });

        // Add a grid
        viewer.addObject(new ROS3D.Grid({ color: '#1e3a8a', size: 2, num_cells: 10 }));

        // Setup TF Client
        const tfClient = new ROSLIB.TFClient({
            ros: ros,
            angularThres: 0.01,
            transThres: 0.01,
            rate: 20.0,
            fixedFrame: 'world' // MoveIt uses 'world' as fixed frame
        });

        // Setup URDF Client
        const urdfClient = new ROS3D.UrdfClient({
            ros: ros,
            tfClient: tfClient,
            path: `http://${window.location.hostname}:8000/`, // FastAPI serves /dsr_description2/meshes
            rootObject: viewer.scene,
            loader: ROS3D.COLLADA_LOADER_2
        });

        // Setup Interactive Marker Client for MoveIt target/source points
        const imClient = new ROS3D.InteractiveMarkerClient({
            ros: ros,
            tfClient: tfClient,
            topic: '/rviz_moveit_motion_planning_display/robot_interaction_interactive_marker_topic',
            camera: viewer.camera,
            rootObject: viewer.selectableObjects
        });

        // Setup Marker Client for planned paths & goal points
        const markerClient = new ROS3D.MarkerClient({
            ros: ros,
            tfClient: tfClient,
            topic: '/visualization_marker',
            rootObject: viewer.scene
        });

        const onResize = () => {
            if (viewerRef.current) viewer.resize(viewerRef.current.clientWidth, 480);
        };
        window.addEventListener('resize', onResize);

        // Cleanup
        return () => {
            window.removeEventListener('resize', onResize);
            if (viewerRef.current) viewerRef.current.innerHTML = '';
            ros.close();
        };
    }, []);

    return (
        <div style={{ position: 'relative', width: '100%', display: 'flex', flexDirection: 'column' }}>
            <div
                id="ros3d-viewer"
                ref={viewerRef}
                style={{ width: '100%', height: 480, background: '#060a14', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)' }}
            />
            {status !== 'connected' && (
                <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(0,0,0,0.7)', padding: '4px 8px', borderRadius: 4, fontSize: '0.75rem', color: 'var(--warning)' }}>
                    rosbridge: {status}
                </div>
            )}
        </div>
    );
}
