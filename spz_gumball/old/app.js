import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

let camera, scene, renderer, orbitControls, transformControls;
let selectedObject = null;

function init() {
    // Scene setup
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f0f0);

    // Camera setup
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(5, 5, 5);
    camera.lookAt(0, 0, 0);

    // Renderer setup
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);

    // Add a grid helper for visualization
    const gridHelper = new THREE.GridHelper(10, 10);
    scene.add(gridHelper);

    // Orbit controls setup with damping disabled to prevent conflicts
    orbitControls = new OrbitControls(camera, renderer.domElement);
    orbitControls.enableDamping = false;

    // Replace the transform controls setup section
    transformControls = new TransformControls(camera, renderer.domElement);
    transformControls.setMode('translate');
    transformControls.setSize(1.5);  // Increased size for better visibility
    transformControls.showX = true;
    transformControls.showY = true;
    transformControls.showZ = true;

    // Add highlight material
    const highlightMaterial = new THREE.MeshStandardMaterial({
        color: 0x00ff00,
        transparent: true,
        opacity: 0.3,
        depthTest: true
    });

    // Store original materials for unhighlighting
    const originalMaterials = new WeakMap();

    // Configure transform controls
    transformControls.setMode('translate');  // Start with translate mode
    transformControls.setSpace('local');     // Use local space by default
    transformControls.setSize(1);            // Set reasonable size for controls
    transformControls.enabled = true;        // Make sure controls are enabled

    // Handle transform and orbit controls interaction
    transformControls.addEventListener('dragging-changed', (event) => {
        orbitControls.enabled = !event.value;
    });

    // Mouse event handlers to prevent orbit/transform conflicts
    transformControls.addEventListener('mouseDown', () => {
        orbitControls.enabled = false;
    });

    transformControls.addEventListener('mouseUp', () => {
        orbitControls.enabled = true;
    });

    scene.add(transformControls);
    transformControls.visible = false;

    // In the init() function, update the lighting
    const ambientLight = new THREE.AmbientLight(0x404040, 2);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 2);
    directionalLight.position.set(5, 5, 5);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    // Enable shadows
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Event listeners
    window.addEventListener('resize', onWindowResize);
    renderer.domElement.addEventListener('click', onClick);

    // File input handler
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', onFileUpload);
}

// Remove the DOMContentLoaded event listener and just call init
init();
animate();

// Modify the onClick function to handle transform controls better

function onClick(event) {
    if (event.target.closest('#upload')) return;

    const rect = renderer.domElement.getBoundingClientRect();
    const mouse = new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);

    // Get meshes excluding transform controls
    const meshes = [];
    scene.traverse((object) => {
        if (object.isMesh && !object.parent?.isTransformControls) {
            meshes.push(object);
        }
    });

    const intersects = raycaster.intersectObjects(meshes, false);

    // Unhighlight previous selection
    if (selectedObject && selectedObject.isMesh) {
        const originalMaterial = originalMaterials.get(selectedObject);
        if (originalMaterial) {
            selectedObject.material = originalMaterial;
        }
    }

    if (intersects.length > 0) {
        const targetObject = intersects[0].object;
        
        if (selectedObject !== targetObject) {
            // Detach controls from previous selection
            transformControls.detach();
            
            // Update selection
            selectedObject = targetObject;
            
            // Store and apply highlight material
            if (selectedObject.isMesh) {
                originalMaterials.set(selectedObject, selectedObject.material);
                selectedObject.material = highlightMaterial.clone();
            }
            
            // Attach transform controls
            transformControls.attach(selectedObject);
            transformControls.visible = true;
            
            // Ensure the gizmo is in front
            transformControls.children.forEach(child => {
                child.renderOrder = 999;
                if (child.material) {
                    child.material.depthTest = false;
                }
            });
            
            console.log('Selected:', selectedObject.name || 'Unnamed mesh');
        }
    } else {
        // Clear selection
        selectedObject = null;
        transformControls.detach();
        transformControls.visible = false;
    }
}

function onFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const loader = new GLTFLoader();
        loader.parse(e.target.result, '', 
            (gltf) => {
                const model = gltf.scene;
                scene.add(model);

                // Center and scale model
                const box = new THREE.Box3().setFromObject(model);
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                const scale = 2 / maxDim;

                model.scale.multiplyScalar(scale);
                model.position.sub(center.multiplyScalar(scale));

                // Setup materials and make selectable
                model.traverse((child) => {
                    if (child.isMesh) {
                        // Ensure material is properly configured
                        if (!(child.material instanceof THREE.MeshStandardMaterial)) {
                            child.material = new THREE.MeshStandardMaterial({
                                color: child.material.color || 0x808080,
                                metalness: 0.5,
                                roughness: 0.5
                            });
                        }
                        child.material.needsUpdate = true;
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }
                });

                // Select the model
                selectedObject = model;
                transformControls.attach(model);
                transformControls.visible = true;

                console.log('Model loaded and ready for transformation');
            },
            (error) => console.error('Error loading model:', error)
        );
    };
    reader.readAsArrayBuffer(file);
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);
    
    // Remove the transform controls check to prevent recursion
    renderer.render(scene, camera);
}

// Add keyboard shortcuts for transform modes
window.addEventListener('keydown', (event) => {
    if (!selectedObject) return;
    
    switch (event.key.toLowerCase()) {
        case 'g':
            transformControls.setMode('translate');
            console.log('Mode: Translate');
            break;
        case 'r':
            transformControls.setMode('rotate');
            console.log('Mode: Rotate');
            break;
        case 's':
            transformControls.setMode('scale');
            console.log('Mode: Scale');
            break;
        case 'space':
            // Toggle between local and world space
            const space = transformControls.getSpace() === 'local' ? 'world' : 'local';
            transformControls.setSpace(space);
            console.log('Space:', space);
            break;
        case 'escape':
            transformControls.detach();
            transformControls.visible = false;
            selectedObject = null;
            break;
    }
});
