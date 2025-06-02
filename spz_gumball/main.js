import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

let scene, camera, renderer, controls, transformControls, raycaster;
let selectedObject = null;
let statusElement;
let isDragging = false;  // Add this global variable
let selectedAxis = null; // Add this global variable too
let highlightMaterial = new THREE.MeshBasicMaterial({ 
  color: 0x00ff00,  // Bright green
  wireframe: true,
  transparent: true,
  opacity: 0.3
});
let originalMaterials = new Map(); // Store original materials
let currentTransformMode = 'translate'; // Default transform mode
let ignoreNextClick = false; // Add this variable at the top of your file with other globals
let pointerDownOnGizmo = false; // Add this variable to track pointer down state

init();

function init() {
  // Scene setup
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x222222); // Darker background for better contrast
  
  // Improved camera settings
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(5, 3, 7); // Better initial view angle
  
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true; // Enable shadows
  renderer.shadowMap.type = THREE.PCFSoftShadowMap; // Softer shadows
  document.body.appendChild(renderer.domElement);

  // Enhanced orbit controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.screenSpacePanning = true;
  controls.minDistance = 1;
  controls.maxDistance = 50;
  controls.maxPolarAngle = Math.PI / 1.5; // Prevent going below the ground

  // Replace simple transforms with proper TransformControls
  transformControls = createCustomTransformGizmo(camera, renderer, scene);
  transformControls.setMode(currentTransformMode || 'translate');
  
  // Add debugging code to verify creation
  console.log("Transform controls initialized:", transformControls);
  
  transformControls.visible = false; // Hide until something is selected
  
  // Disable orbit controls when using transform controls
  transformControls.addEventListener('dragging-changed', function(event) {
    controls.enabled = !event.value;
  });
  
  // Update mode when pressing keys (optional)
  window.addEventListener('keydown', function(event) {
    switch (event.key) {
      case 'g': // translate (grab)
        transformControls.setMode('translate');
        currentTransformMode = 'translate';
        updateStatus(`Mode: Translate (G)`);
        break;
      case 'r': // rotate
        transformControls.setMode('rotate');
        currentTransformMode = 'rotate';
        updateStatus(`Mode: Rotate (R)`);
        break;
      case 's': // scale
        transformControls.setMode('scale');
        currentTransformMode = 'scale';
        updateStatus(`Mode: Scale (S)`);
        break;
    }
  });

  // Better lighting
  scene.add(new THREE.AmbientLight(0xffffff, 0.4));
  
  const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight1.position.set(5, 10, 7.5);
  dirLight1.castShadow = true;
  dirLight1.shadow.camera.near = 0.1;
  dirLight1.shadow.camera.far = 500;
  dirLight1.shadow.camera.right = 17;
  dirLight1.shadow.camera.left = -17;
  dirLight1.shadow.camera.top = 17;
  dirLight1.shadow.camera.bottom = -17;
  scene.add(dirLight1);
  
  const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
  dirLight2.position.set(-5, 5, -7.5);
  scene.add(dirLight2);

  // Ground/Grid for reference
  const gridHelper = new THREE.GridHelper(20, 20, 0x555555, 0x333333);
  scene.add(gridHelper);

  // Raycaster
  raycaster = new THREE.Raycaster();
  window.addEventListener('pointerdown', onClick);

  // Resize
  window.addEventListener('resize', onWindowResize);

  // Status element
  statusElement = document.getElementById('status');
  
  // Upload
  document.getElementById('upload').addEventListener('change', handleUpload);
  
  // Remove the call to addTransformButtons() - we won't need UI buttons
  // addTransformButtons();
  
  // Setup a dynamic context menu for transform mode changes
  setupContextMenu();
  
  // Initial status
  updateStatus("Ready. Upload a 3D model to begin.");

  // Do the first render to initialize everything
  renderer.render(scene, camera);
  
  // Start animation loop
  animate();
}

// Add this function to create a context menu for changing transform modes
function setupContextMenu() {
  // Create a custom context menu
  const contextMenu = document.createElement('div');
  contextMenu.id = 'transform-context-menu';
  contextMenu.style.position = 'absolute';
  contextMenu.style.display = 'none';
  contextMenu.style.backgroundColor = 'rgba(40, 40, 40, 0.9)';
  contextMenu.style.border = '1px solid #555';
  contextMenu.style.borderRadius = '4px';
  contextMenu.style.padding = '5px';
  contextMenu.style.zIndex = '1000';
  contextMenu.style.boxShadow = '0 0 10px rgba(0,0,0,0.5)';
  
  // Add transform mode options
  const modes = [
    { name: 'translate', icon: '↔', key: 'G' },
    { name: 'rotate', icon: '↻', key: 'R' },
    { name: 'scale', icon: '⤧', key: 'S' }
  ];
  
  modes.forEach(mode => {
    const option = document.createElement('div');
    option.textContent = `${mode.icon} ${mode.name.charAt(0).toUpperCase() + mode.name.slice(1)} (${mode.key})`;
    option.style.padding = '8px 12px';
    option.style.cursor = 'pointer';
    option.style.color = '#fff';
    
    // Highlight on hover
    option.addEventListener('mouseover', () => {
      option.style.backgroundColor = '#4CAF50';
    });
    
    option.addEventListener('mouseout', () => {
      option.style.backgroundColor = 'transparent';
    });
    
    // Change transform mode on click
    option.addEventListener('click', () => {
      transformControls.setMode(mode.name);
      currentTransformMode = mode.name;
      updateStatus(`Mode: ${mode.name}`);
      contextMenu.style.display = 'none';
    });
    
    contextMenu.appendChild(option);
  });
  
  // Add separator
  const separator = document.createElement('div');
  separator.style.height = '1px';
  separator.style.backgroundColor = '#555';
  separator.style.margin = '5px 0';
  contextMenu.appendChild(separator);
  
  // Add delete option
  const deleteOption = document.createElement('div');
  deleteOption.textContent = '🗑️ Delete (Del)';
  deleteOption.style.padding = '8px 12px';
  deleteOption.style.cursor = 'pointer';
  deleteOption.style.color = '#ff5555';
  
  deleteOption.addEventListener('mouseover', () => {
    deleteOption.style.backgroundColor = '#ff5555';
    deleteOption.style.color = '#fff';
  });
  
  deleteOption.addEventListener('mouseout', () => {
    deleteOption.style.backgroundColor = 'transparent';
    deleteOption.style.color = '#ff5555';
  });
  
  deleteOption.addEventListener('click', () => {
    if (selectedObject) {
      let toDelete = selectedObject;
      while (toDelete.parent && !toDelete.parent.isScene) {
        toDelete = toDelete.parent;
      }
      scene.remove(toDelete);
      transformControls.detach();
      selectedObject = null;
      updateStatus("Object deleted");
      contextMenu.style.display = 'none';
    }
  });
  
  contextMenu.appendChild(deleteOption);
  document.body.appendChild(contextMenu);
  
  // Show context menu on right-click
  window.addEventListener('contextmenu', (event) => {
    if (selectedObject) {
      event.preventDefault();
      contextMenu.style.left = event.clientX + 'px';
      contextMenu.style.top = event.clientY + 'px';
      contextMenu.style.display = 'block';
    }
  });
  
  // Hide context menu when clicking elsewhere
  window.addEventListener('click', () => {
    contextMenu.style.display = 'none';
  });

  // Add additional keyboard shortcut for delete
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Delete' && selectedObject) {
      let toDelete = selectedObject;
      while (toDelete.parent && !toDelete.parent.isScene) {
        toDelete = toDelete.parent;
      }
      scene.remove(toDelete);
      transformControls.detach();
      selectedObject = null;
      updateStatus("Object deleted");
    }
  });
}

// Replace your handleUpload function with this enhanced version:

function handleUpload(event) {
  const file = event.target.files[0];
  if (!file) {
    updateStatus("No file selected");
    return;
  }
  
  updateStatus(`Loading ${file.name}...`);

  const reader = new FileReader();
  reader.onload = function (e) {
    updateStatus("Parsing model...");
    const contents = e.target.result;
    const loader = new GLTFLoader();
    
    loader.parse(contents, '', 
      function (gltf) {
        updateStatus(`${file.name} loaded successfully. Click on any building to select and manipulate.`);
        
        const flattenedScene = new THREE.Group();
        flattenedScene.name = "FlattenedCity";
        
        // Original bounding box for calculating overall centering and scaling
        const originalBox = new THREE.Box3().setFromObject(gltf.scene);
        const originalSize = originalBox.getSize(new THREE.Vector3());
        const originalMaxDim = Math.max(originalSize.x, originalSize.y, originalSize.z);
        const normalizationScale = (originalMaxDim > 0) ? (5 / originalMaxDim) : 1; // Scale to reasonable size, avoid division by zero

        // Apply overall normalization scale and centering to the main gltf.scene
        // This ensures node.matrixWorld will be correct later
        gltf.scene.scale.set(normalizationScale, normalizationScale, normalizationScale);
        const scaledCenter = originalBox.getCenter(new THREE.Vector3()).multiplyScalar(normalizationScale);
        gltf.scene.position.sub(scaledCenter); // Center the entire gltf.scene at world origin

        // Update the world matrix of gltf.scene and all its children
        gltf.scene.updateMatrixWorld(true);

        let meshCounter = 0;
        gltf.scene.traverse(function(node) {
          if (node.isMesh) {
            const clonedMesh = node.clone();
            
            if (!clonedMesh.name || clonedMesh.name === '') {
              clonedMesh.name = `Building_${meshCounter++}`;
            }
            
            // Get the final world matrix of the original node
            // (which already includes the normalizationScale and centering applied to gltf.scene)
            const worldMatrix = node.matrixWorld;
            
            // Decompose the world matrix to get world position, quaternion, and scale
            const worldPosition = new THREE.Vector3();
            const worldQuaternion = new THREE.Quaternion();
            const worldScale = new THREE.Vector3();
            worldMatrix.decompose(worldPosition, worldQuaternion, worldScale);
            
            // Apply these decomposed world transforms directly to the cloned mesh's local transforms
            // since it will be a direct child of flattenedScene (which is at world origin initially)
            clonedMesh.position.copy(worldPosition);
            clonedMesh.quaternion.copy(worldQuaternion);
            clonedMesh.scale.copy(worldScale);
            
            if (clonedMesh.material) {
              if (Array.isArray(clonedMesh.material)) {
                clonedMesh.material = clonedMesh.material.map(mat => mat.clone());
              } else {
                clonedMesh.material = clonedMesh.material.clone();
              }
            }
            
            clonedMesh.castShadow = true;
            clonedMesh.receiveShadow = true;
            
            clonedMesh.matrixAutoUpdate = true; // Ensure matrices update if properties change
            // No need to call clonedMesh.updateMatrix() here, it will be handled by the renderer
            
            flattenedScene.add(clonedMesh);
          }
        });
        
        // flattenedScene is already effectively centered because its children
        // were placed using their final world coordinates (after gltf.scene was centered).
        // So, flattenedScene itself should remain at the origin.
        scene.add(flattenedScene);
        
        controls.target.copy(new THREE.Vector3(0, 0, 0)); // Focus camera on origin
        controls.update();
        
        renderer.render(scene, camera);
      },
      function (error) {
        updateStatus(`Error loading model: ${error.message}`);
        console.error("Error parsing GLTF:", error);
      }
    );
  };
  
  reader.onerror = function() {
    updateStatus(`File read error: ${reader.error}`);
    console.error("FileReader error:", reader.error);
  };
  
  reader.readAsArrayBuffer(file);
}

function onClick(event) {
  // Skip if right-click
  if (event.button === 2) return;
  
  // IMPROVED LOGIC: Use both flags for more reliable detection
  if (isDragging || ignoreNextClick) {
    console.log("Ignoring click event immediately after drag");
    return;
  }
  
  const mouse = new THREE.Vector2(
    (event.clientX / window.innerWidth) * 2 - 1,
    -(event.clientY / window.innerHeight) * 2 + 1
  );

  raycaster.setFromCamera(mouse, camera);
  
  // First check if we're clicking on the gizmo itself
  let clickedGizmo = false;
  
  if (transformControls && transformControls.visible) {
    // Get all parts of the transform controls
    const gizmoParts = [];
    transformControls.traverse(object => {
      if (object.isMesh) gizmoParts.push(object);
    });
    
    const gizmoIntersects = raycaster.intersectObjects(gizmoParts);
    if (gizmoIntersects.length > 0) {
      clickedGizmo = true;
      console.log("Clicked on gizmo part");
      return; // Important: Exit here to prevent deselection when clicking on gizmo
    }
  }
  
  // Only proceed with selection if we didn't click on the gizmo
  if (!clickedGizmo) {
    // Get all meshes in the scene but exclude helpers, wireframes, and grid
    const meshesToTest = [];
    scene.traverse((object) => {
      if (object.isMesh && 
          !object.userData.isHelper && 
          object.name !== "currentSelectionWireframe" &&
          object.type !== "GridHelper" &&
          object.parent && object.parent.name !== "CustomTransformGizmo") {
        meshesToTest.push(object);
      }
    });
    
    // Test intersection with all meshes
    const intersects = raycaster.intersectObjects(meshesToTest, false); // false = don't check descendants
    
    if (intersects.length > 0) {
      const object = intersects[0].object;
      console.log("Selected mesh:", object.name, object);
      
      // If we're selecting a different object than what's currently selected
      if (object !== selectedObject) {
        // First detach controls from previous object
        if (transformControls) {
          transformControls.detach();
          // Force removal from the scene
          if (transformControls.parent) {
            transformControls.parent.remove(transformControls);
          }
        }
        
        // Reset previous selection highlight
        if (selectedObject) {
          removeHighlight();
        }
        
        // Find the proper parent object to transform
        const transformableObject = findTransformableParent(object);
        console.log("Will transform:", transformableObject.name || "Unnamed object");
        
        // Update selection (keep track of both the selected mesh and the transformable parent)
        selectedObject = object;
        selectedObject.userData.transformTarget = transformableObject;
        
        // Highlight the originally selected mesh to show what was clicked
        addHighlightToMesh(object);
        
        // CRITICAL: Add to scene first, make visible, then attach to TRANSFORMABLE PARENT
        scene.add(transformControls);
        transformControls.visible = true;
        transformControls.attach(transformableObject);  // <-- This is the key change!
        
        // Get world position of the transformable parent
        const worldPos = new THREE.Vector3();
        transformableObject.getWorldPosition(worldPos);
        transformControls.position.copy(worldPos);
        
        // Force update
        if (transformControls.userData && transformControls.userData.update) {
          transformControls.userData.update();
        }
        
        // Add debug visuals
        console.log("Gizmo added to scene:", transformControls.parent === scene);
        console.log("Gizmo visible:", transformControls.visible);
        console.log("Gizmo attached to:", transformableObject.name || "Unnamed parent");
        
        updateStatus(`Selected: ${object.name || "Unnamed mesh"} (controlling: ${transformableObject.name || "parent group"})`);
      }
    } else {
      // Only deselect when clicking on empty space
      if (selectedObject) {
        transformControls.detach();
        removeHighlight();
        selectedObject = null;
        updateStatus("No object selected");
      }
    }
  }
}

// Replace the existing addHighlightToMesh function with this enhanced version:

function addHighlightToMesh(mesh) {
  // Store original material (this part is fine)
  if (Array.isArray(mesh.material)) {
    originalMaterials.set(mesh, [...mesh.material]);
    mesh.userData.originalMaterials = [...mesh.material];
    mesh.material.forEach(mat => {
      mat.emissive = new THREE.Color(0x00ff00);
      mat.emissiveIntensity = 0.7; // Brighter highlight for city models
    });
  } else {
    originalMaterials.set(mesh, mesh.material);
    
    if (mesh.material.emissive) {
      mesh.userData.originalEmissive = mesh.material.emissive.clone();
      mesh.userData.originalEmissiveIntensity = mesh.material.emissiveIntensity;
      mesh.material.emissive.set(0x00ff00);
      mesh.material.emissiveIntensity = 0.7; // Brighter highlight
    } else {
      // For materials without emissive property, create a new material
      const newMaterial = mesh.material.clone();
      newMaterial.emissive = new THREE.Color(0x00ff00);
      newMaterial.emissiveIntensity = 0.7;
      mesh.material = newMaterial;
    }
  }
  
  // FIXED: Create wireframe as separate scene object instead of child
  // This prevents issues with selection and hierarchy
  if (!scene.getObjectByName("currentSelectionWireframe")) {
    const wireframeGeometry = mesh.geometry.clone();
    const wireframeMesh = new THREE.Mesh(
      wireframeGeometry,
      new THREE.MeshBasicMaterial({
        color: 0x00ff00,
        wireframe: true,
        transparent: true,
        opacity: 0.5,
        depthTest: false
      })
    );
    
    // Important: Copy transform from the selected mesh
    wireframeMesh.position.copy(mesh.position);
    wireframeMesh.rotation.copy(mesh.rotation);
    wireframeMesh.scale.copy(mesh.scale);
    
    wireframeMesh.name = "currentSelectionWireframe";
    wireframeMesh.userData.isHelper = true;
    wireframeMesh.renderOrder = 999; // Draw on top
    
    // Use the same matrix world as the original mesh to maintain correct position
    wireframeMesh.matrixWorld.copy(mesh.matrixWorld);
    
    // Add to scene instead of as child of mesh
    scene.add(wireframeMesh);
    
    // Store reference to the original mesh
    wireframeMesh.userData.parentMesh = mesh;
  }

  // Make selected building "pop" by slightly scaling it up
  mesh.userData.originalScale = mesh.scale.clone();
  mesh.scale.multiplyScalar(1.01); // 1% larger to make it stand out
}

// And update the removeHighlight function to handle these enhancements:

function removeHighlight() {
  if (!selectedObject) return;
  
  try {
    // FIXED: Remove wireframe from scene instead of from mesh
    const wireframe = scene.getObjectByName("currentSelectionWireframe");
    if (wireframe) {
      scene.remove(wireframe);
    }
    
    // Restore original scale
    if (selectedObject.userData.originalScale) {
      selectedObject.scale.copy(selectedObject.userData.originalScale);
      delete selectedObject.userData.originalScale;
    }
    
    // Restore original material
    if (originalMaterials.has(selectedObject)) {
      const mesh = selectedObject;
      
      if (Array.isArray(mesh.material)) {
        // Restore original array of materials
        mesh.material = mesh.userData.originalMaterials;
      } else {
        // Restore single material
        mesh.material = originalMaterials.get(mesh);
        
        // Restore original emissive properties if they existed
        if (mesh.userData.originalEmissive) {
          mesh.material.emissive = mesh.userData.originalEmissive;
          mesh.material.emissiveIntensity = mesh.userData.originalEmissiveIntensity;
          delete mesh.userData.originalEmissive;
          delete mesh.userData.originalEmissiveIntensity;
        }
      }
    }
  } catch (e) {
    console.error("Error during highlight removal:", e);
  }
  
  originalMaterials.clear();
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function updateStatus(message) {
  if (statusElement) {
    statusElement.textContent = message;
  }
  console.log(message);
}

// Replace your animate function:

function animate() {
  requestAnimationFrame(animate);
  
  // Keep transform controls visible and synchronized
  if (transformControls && transformControls.targetObject) {
    // Force visibility on every frame
    transformControls.visible = true;
    
    // Keep transform controls positioned at target object
    const targetPos = new THREE.Vector3();
    transformControls.targetObject.getWorldPosition(targetPos);
    transformControls.position.copy(targetPos);
    
    // Update visual appearance
    if (transformControls.userData && transformControls.userData.update) {
      transformControls.userData.update();
    }
    
    // Make sure transform controls are in the scene
    if (!transformControls.parent) {
      console.log("Adding transform controls to scene");
      scene.add(transformControls);
    }
  }
  
  controls.update();
  renderer.render(scene, camera);
}

// Replace your TransformControls import and initialization with this workaround:

// 1. First, replace the import at the top of your file
// import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'; // Comment this out

// 2. Add this function at the top of your file to create a custom transform gizmo
function createCustomTransformGizmo(camera, renderer, scene) {
  // Create a group to hold our gizmo elements
  const gizmoGroup = new THREE.Group();
  gizmoGroup.name = "CustomTransformGizmo";
  gizmoGroup.mode = 'translate'; // Default mode
  
  // For drag handling
  // REMOVE THESE LOCAL VARIABLES:
  // let isDragging = false;
  // let selectedAxis = null;
  
  // Keep these other variables as local
  let startPoint = new THREE.Vector3();
  let startPosition = new THREE.Vector3();
  let startScale = new THREE.Vector3();
  let startRotation = new THREE.Euler();
  let dragPlane = new THREE.Plane();
  let startQuaternion = new THREE.Quaternion();
  
  // Colors matching Rhino gumball - MAKE BRIGHTER FOR TESTING
  const xColor = 0xff5555;  // Brighter red
  const yColor = 0x55ff55;  // Brighter green
  const zColor = 0x5555ff;  // Brighter blue
  const centerColor = 0xffff55; // Brighter yellow
  const arcColor = 0xffaa33;  // Brighter orange
  
  // Create axes for the gizmo - thicker and more visible
  const axisLength = 1.5;  // Even longer axes
  const axisWidth = 0.06;  // Thicker axes
  const arrowSize = 0.2;   // Bigger arrows
  
  // ===== X AXIS (RED) =====
  // Shaft
  const xAxisGeom = new THREE.CylinderGeometry(axisWidth, axisWidth, axisLength - arrowSize, 12);
  xAxisGeom.rotateZ(Math.PI/2);
  const xAxis = new THREE.Mesh(
    xAxisGeom,
    new THREE.MeshBasicMaterial({ 
      color: xColor,
      depthTest: false,
      transparent: false
    })
  );
  xAxis.position.set((axisLength - arrowSize)/2, 0, 0);
  xAxis.userData.axis = 'x';
  xAxis.userData.isHelper = true;
  gizmoGroup.add(xAxis);
  
  // Arrow cone
  const xConeGeom = new THREE.ConeGeometry(arrowSize*1.5, arrowSize*2, 12);
  xConeGeom.rotateZ(-Math.PI/2);
  const xCone = new THREE.Mesh(
    xConeGeom,
    new THREE.MeshBasicMaterial({ color: xColor, depthTest: false })
  );
  xCone.position.set(axisLength - arrowSize/2, 0, 0);
  xCone.userData.axis = 'x';
  xCone.userData.isHelper = true;
  gizmoGroup.add(xCone);
  
  // ===== Y AXIS (GREEN) =====
  // Shaft
  const yAxisGeom = new THREE.CylinderGeometry(axisWidth, axisWidth, axisLength - arrowSize, 12);
  const yAxis = new THREE.Mesh(
    yAxisGeom,
    new THREE.MeshBasicMaterial({ 
      color: yColor,
      depthTest: false,
      transparent: false
    })
  );
  yAxis.position.set(0, (axisLength - arrowSize)/2, 0);
  yAxis.userData.axis = 'y';
  yAxis.userData.isHelper = true;
  gizmoGroup.add(yAxis);
  
  // Arrow cone
  const yConeGeom = new THREE.ConeGeometry(arrowSize*1.5, arrowSize*2, 12);
  const yCone = new THREE.Mesh(
    yConeGeom,
    new THREE.MeshBasicMaterial({ color: yColor, depthTest: false })
  );
  yCone.position.set(0, axisLength - arrowSize/2, 0);
  yCone.userData.axis = 'y';
  yCone.userData.isHelper = true;
  gizmoGroup.add(yCone);
  
  // ===== Z AXIS (BLUE) =====
  // Shaft
  const zAxisGeom = new THREE.CylinderGeometry(axisWidth, axisWidth, axisLength - arrowSize, 12);
  zAxisGeom.rotateX(Math.PI/2);
  const zAxis = new THREE.Mesh(
    zAxisGeom, 
    new THREE.MeshBasicMaterial({ 
      color: zColor,
      depthTest: false,
      transparent: false
    })
  );
  zAxis.position.set(0, 0, (axisLength - arrowSize)/2);
  zAxis.userData.axis = 'z';
  zAxis.userData.isHelper = true;
  gizmoGroup.add(zAxis);
  
  // Arrow cone
  const zConeGeom = new THREE.ConeGeometry(arrowSize*1.5, arrowSize*2, 12);
  zConeGeom.rotateX(Math.PI/2);
  const zCone = new THREE.Mesh(
    zConeGeom,
    new THREE.MeshBasicMaterial({ color: zColor, depthTest: false })
  );
  zCone.position.set(0, 0, axisLength - arrowSize/2);
  zCone.userData.axis = 'z';
  zCone.userData.isHelper = true;
  gizmoGroup.add(zCone);

  // ===== PLANE HANDLES (like Rhino) =====
  const planeSize = 0.3;
  const planeOpacity = 0.6;
  
  // XY Plane (blue)
  const xyPlaneGeom = new THREE.PlaneGeometry(planeSize, planeSize);
  const xyPlane = new THREE.Mesh(
    xyPlaneGeom,
    new THREE.MeshBasicMaterial({ 
      color: 0x9999ff, 
      transparent: true, 
      opacity: planeOpacity,
      depthTest: false,
      side: THREE.DoubleSide 
    })
  );
  xyPlane.position.set(planeSize/2, planeSize/2, 0);
  xyPlane.userData.axis = 'xy';
  xyPlane.userData.isHelper = true;
  gizmoGroup.add(xyPlane);
  
  // XZ Plane (green)
  const xzPlaneGeom = new THREE.PlaneGeometry(planeSize, planeSize);
  xzPlaneGeom.rotateX(Math.PI/2);
  const xzPlane = new THREE.Mesh(
    xzPlaneGeom,
    new THREE.MeshBasicMaterial({ 
      color: 0x99ff99, 
      transparent: true, 
      opacity: planeOpacity,
      depthTest: false,
      side: THREE.DoubleSide 
    })
  );
  xzPlane.position.set(planeSize/2, 0, planeSize/2);
  xzPlane.userData.axis = 'xz';
  xzPlane.userData.isHelper = true;
  gizmoGroup.add(xzPlane);
  
  // YZ Plane (red)
  const yzPlaneGeom = new THREE.PlaneGeometry(planeSize, planeSize);
  yzPlaneGeom.rotateY(Math.PI/2);
  const yzPlane = new THREE.Mesh(
    yzPlaneGeom,
    new THREE.MeshBasicMaterial({ 
      color: 0xff9999, 
      transparent: true, 
      opacity: planeOpacity,
      depthTest: false,
      side: THREE.DoubleSide 
    })
  );
  yzPlane.position.set(0, planeSize/2, planeSize/2);
  yzPlane.userData.axis = 'yz';
  yzPlane.userData.isHelper = true;
  gizmoGroup.add(yzPlane);
  
  // ===== ROTATION HANDLES =====
  // Create rotation rings for each axis
  const arcRadius = 0.8;
  const arcThickness = 0.03;
  const arcSegments = 32;
  
  // X rotation ring (red)
  const xArcGeometry = new THREE.TorusGeometry(arcRadius, arcThickness, 8, arcSegments, Math.PI * 1.5);
  xArcGeometry.rotateY(Math.PI/2);
  const xArc = new THREE.Mesh(
    xArcGeometry,
    new THREE.MeshBasicMaterial({ color: xColor, depthTest: false })
  );
  xArc.userData.axis = 'rotateX';
  xArc.userData.isHelper = true;
  xArc.visible = false; // Only shown in rotation mode
  gizmoGroup.add(xArc);
  
  // Y rotation ring (green)
  const yArcGeometry = new THREE.TorusGeometry(arcRadius, arcThickness, 8, arcSegments, Math.PI * 1.5);
  const yArc = new THREE.Mesh(
    yArcGeometry,
    new THREE.MeshBasicMaterial({ color: yColor, depthTest: false })
  );
  yArc.userData.axis = 'rotateY';
  yArc.userData.isHelper = true;
  yArc.visible = false; // Only shown in rotation mode
  gizmoGroup.add(yArc);
  
  // Z rotation ring (blue)
  const zArcGeometry = new THREE.TorusGeometry(arcRadius, arcThickness, 8, arcSegments, Math.PI * 1.5);
  zArcGeometry.rotateX(Math.PI/2);
  const zArc = new THREE.Mesh(
    zArcGeometry,
    new THREE.MeshBasicMaterial({ color: zColor, depthTest: false })
  );
  zArc.userData.axis = 'rotateZ';
  zArc.userData.isHelper = true;
  zArc.visible = false; // Only shown in rotation mode
  gizmoGroup.add(zArc);
  
  // ===== SCALE HANDLES =====
  // Add scale cubes for scale mode
  const cubeSize = 0.15;
  
  // X scale cube
  const xCubeGeom = new THREE.BoxGeometry(cubeSize, cubeSize, cubeSize);
  const xCube = new THREE.Mesh(
    xCubeGeom,
    new THREE.MeshBasicMaterial({ color: xColor, depthTest: false })
  );
  xCube.position.set(axisLength, 0, 0);
  xCube.userData.axis = 'scaleX';
  xCube.userData.isHelper = true;
  xCube.visible = false; // Only shown in scale mode
  gizmoGroup.add(xCube);
  
  // Y scale cube
  const yCubeGeom = new THREE.BoxGeometry(cubeSize, cubeSize, cubeSize);
  const yCube = new THREE.Mesh(
    yCubeGeom,
    new THREE.MeshBasicMaterial({ color: yColor, depthTest: false })
  );
  yCube.position.set(0, axisLength, 0);
  yCube.userData.axis = 'scaleY';
  yCube.userData.isHelper = true;
  yCube.visible = false; // Only shown in scale mode
  gizmoGroup.add(yCube);
  
  // Z scale cube
  const zCubeGeom = new THREE.BoxGeometry(cubeSize, cubeSize, cubeSize);
  const zCube = new THREE.Mesh(
    zCubeGeom,
    new THREE.MeshBasicMaterial({ color: zColor, depthTest: false })
  );
  zCube.position.set(0, 0, axisLength);
  zCube.userData.axis = 'scaleZ';
  zCube.userData.isHelper = true;
  zCube.visible = false; // Only shown in scale mode
  gizmoGroup.add(zCube);
  
  // Center cube for uniform scale
  const centerCubeGeom = new THREE.BoxGeometry(cubeSize*1.2, cubeSize*1.2, cubeSize*1.2);
  const centerCube = new THREE.Mesh(
    centerCubeGeom,
    new THREE.MeshBasicMaterial({ color: centerColor, depthTest: false })
  );
  centerCube.userData.axis = 'scaleXYZ';
  centerCube.userData.isHelper = true;
  centerCube.visible = false; // Only shown in scale mode
  gizmoGroup.add(centerCube);
  
  // Center sphere for translation/rotation pivot
  const centerSphere = new THREE.Mesh(
    new THREE.SphereGeometry(0.08, 16, 16),
    new THREE.MeshBasicMaterial({ 
      color: centerColor,
      depthTest: false
    })
  );
  centerSphere.userData.axis = 'center';
  centerSphere.userData.isHelper = true;
  gizmoGroup.add(centerSphere);
  
  // Make gizmo always face camera and stay visible
  gizmoGroup.userData.update = function() {
    if (this.targetObject) {
      // Update position to match target object
      this.position.copy(this.targetObject.position);
      
      // Make gizmo size consistent regardless of distance from camera
      const distance = camera.position.distanceTo(this.position);
      const scale = distance / 18; // Slightly smaller overall for better feel
      this.scale.set(scale, scale, scale);
      
      // Ensure it's always visible on top of scene
      this.children.forEach(child => {
        if (child.material) {
          child.material.depthTest = false;
          child.renderOrder = 999;
        }
      });
      
      // Show different controls based on mode
      this.children.forEach(child => {
        const axis = child.userData.axis || '';
        
        // Handle visibility based on mode
        if (this.mode === 'translate') {
          child.visible = !axis.includes('rotate') && !axis.includes('scale');
        } else if (this.mode === 'rotate') {
          // Show only rotation elements in rotation mode
          child.visible = axis.includes('rotate') || axis === 'center';
          // Also show regular axes with lower opacity as reference
          if (axis === 'x' || axis === 'y' || axis === 'z') {
            child.visible = true;
            if (child.material) {
              child.material.opacity = 0.3;
              child.material.transparent = true;
            }
          }
        } else if (this.mode === 'scale') {
          // Show only scale elements in scale mode
          child.visible = axis.includes('scale') || axis === 'center';
          // Also show regular axes with lower opacity as reference
          if (axis === 'x' || axis === 'y' || axis === 'z') {
            child.visible = true;
            if (child.material) {
              child.material.opacity = 0.3;
              child.material.transparent = true;
            }
          }
        }
      });
    }
  };
  
  // Add methods that mimic TransformControls
  gizmoGroup.attach = function(object) {
    if (!object) {
      console.error("Cannot attach to null object");
      return;
    }
    
    console.log("Attaching gizmo to:", object.name);
    this.targetObject = object;
    this.visible = true;
    
    // Position at target object's world position
    const worldPosition = new THREE.Vector3();
    object.getWorldPosition(worldPosition);
    this.position.copy(worldPosition);
    
    // Add event handlers for the gizmo
    setupGizmoEvents();
    
    // Update visuals
    this.userData.update();
  };
  
  gizmoGroup.detach = function() {
    this.targetObject = null;
    this.visible = false;
    
    // Remove from scene
    if (this.parent) {
      this.parent.remove(this);
    }
    
    // Remove event handlers
    cleanupGizmoEvents();
  };
  
  gizmoGroup.setMode = function(mode) {
    this.mode = mode;
    // Update gizmo visuals immediately
    if (this.targetObject) {
      this.userData.update();
    }
  };
  
  // Add event dispatcher capability to the gizmo group - proper way
  Object.assign(gizmoGroup, THREE.EventDispatcher.prototype);
  
  // Add event handlers for actual transformations
  function setupGizmoEvents() {
    // Add these handlers to the renderer's domElement
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerup', onPointerUp);
  }
  
  function cleanupGizmoEvents() {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown);
    renderer.domElement.removeEventListener('pointermove', onPointerMove);
    renderer.domElement.removeEventListener('pointerup', onPointerUp);
  }
  
  function onPointerDown(event) {
    if (!gizmoGroup.targetObject) return;

    console.log("Pointer down on gizmo", event);
    
    const mouse = new THREE.Vector2(
      (event.clientX / window.innerWidth) * 2 - 1,
      -(event.clientY / window.innerHeight) * 2 + 1
    );
    
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);
    
    const gizmoMeshes = [];
    gizmoGroup.traverse(object => {
        if (object.isMesh && object.visible) gizmoMeshes.push(object);
    });
    
    const intersects = raycaster.intersectObjects(gizmoMeshes, false);

    if (intersects.length > 0) {
      pointerDownOnGizmo = true;
      
      // CRITICAL FIX: Prevent event from reaching window's click handler
      event.stopPropagation();
      event.preventDefault();
      
      // Disable orbit controls during transform
      controls.enabled = false;
      
      // Get the clicked axis and start dragging
      isDragging = true;
      selectedAxis = intersects[0].object.userData.axis || '';
      console.log("Starting drag on axis:", selectedAxis);
      
      // Create event to notify dragging started
      gizmoGroup.dispatchEvent({ type: 'dragging-changed', value: true });
      
      // Store starting states
      startPosition.copy(gizmoGroup.targetObject.position);
      startQuaternion.copy(gizmoGroup.targetObject.quaternion);
      
      // CRITICAL FIX: Store reference to prevent loss during drag
      gizmoGroup.userData.activeTransform = true;
      
      // SIMPLER DRAG PLANE: Just use a plane perpendicular to the camera 
      // that contains the object position
      const objPos = gizmoGroup.position.clone();
      
      // Choose appropriate plane based on axis
      if (selectedAxis === 'x') {
        dragPlane.setFromNormalAndCoplanarPoint(
          new THREE.Vector3(0, 0, 1),  // Use fixed normal for more stability
          objPos
        );
      } else if (selectedAxis === 'y') {
        dragPlane.setFromNormalAndCoplanarPoint(
          new THREE.Vector3(1, 0, 0),  // Use fixed normal for more stability
          objPos
        );
      } else if (selectedAxis === 'z') {
        dragPlane.setFromNormalAndCoplanarPoint(
          new THREE.Vector3(0, 1, 0),  // Use fixed normal for more stability
          objPos
        );
      } else {
        // For planes and center, use camera-facing plane
        dragPlane.setFromNormalAndCoplanarPoint(
          raycaster.ray.direction.clone().negate(),
          objPos
        );
      }
      
      // Get starting point on plane with fallback
      if (raycaster.ray.intersectPlane(dragPlane, startPoint)) {
        console.log("Got valid start point:", startPoint.clone());
      } else {
        console.warn("Couldn't intersect with drag plane, using object position");
        startPoint.copy(objPos);
      }
    }
  }
  
  function onPointerMove(event) {
    if (!isDragging || !selectedAxis || !gizmoGroup.targetObject) return;
    
    const mouse = new THREE.Vector2(
      (event.clientX / window.innerWidth) * 2 - 1,
      -(event.clientY / window.innerHeight) * 2 + 1
    );
    
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);
    
    // IMPROVED FALLBACK: If no plane intersection, use screen-space movement
    const intersection = new THREE.Vector3();
    let validIntersection = raycaster.ray.intersectPlane(dragPlane, intersection);
    
    if (validIntersection) {
      console.log("Move: Got intersection with drag plane");
      
      // Calculate movement delta
      const delta = new THREE.Vector3().subVectors(intersection, startPoint);
      
      if (gizmoGroup.mode === 'translate') {
        applyTranslation(delta);
      } else if (gizmoGroup.mode === 'scale') {
        applyScaling(delta, intersection);
      } else if (gizmoGroup.mode === 'rotate') {
        applyRotation(delta, intersection);
      }
    } else {
      // FALLBACK: Calculate screen-space movement and apply it
      console.log("Using fallback movement method");
      
      // Get a point at a fixed distance along the ray
      const rayPoint = new THREE.Vector3();
      rayPoint.copy(raycaster.ray.direction).multiplyScalar(10).add(raycaster.ray.origin);
      
      // Calculate a simple directional delta based on the axis
      let delta = new THREE.Vector3();
      
      if (selectedAxis === 'x') {
        delta.set((event.movementX) * 0.01, 0, 0);
      } else if (selectedAxis === 'y') {
        delta.set(0, -(event.movementY) * 0.01, 0);
      } else if (selectedAxis === 'z') {
        delta.set(0, 0, (event.movementX + event.movementY) * 0.01);
      } else if (selectedAxis === 'center' || selectedAxis === 'xy') {
        delta.set((event.movementX) * 0.01, -(event.movementY) * 0.01, 0);
      } else if (selectedAxis === 'xz') {
        delta.set((event.movementX) * 0.01, 0, (event.movementY) * 0.01);
      } else if (selectedAxis === 'yz') {
        delta.set(0, -(event.movementX) * 0.01, (event.movementY) * 0.01);
      }
      
      if (gizmoGroup.mode === 'translate') {
        applyTranslation(delta);
      }
      // For scale and rotate, we'll just skip as they need proper plane intersection
    }
    
    // Always update the gizmo to follow the object
    gizmoGroup.position.copy(gizmoGroup.targetObject.position);
    gizmoGroup.userData.update();
    
    // Force a render
    renderer.render(scene, camera);
  }
  
  // 1. First, update the applyTranslation function to properly update child mesh positions:

  function applyTranslation(delta) {
    const obj = gizmoGroup.targetObject;
    if (!obj) return;
    
    console.log("Applying translation with delta:", delta);
    
    // Apply translation based on the selected axis
    if (selectedAxis === 'xy') {
      obj.position.x = startPosition.x + delta.x;
      obj.position.y = startPosition.y + delta.y;
    } 
    else if (selectedAxis === 'yz') {
      obj.position.y = startPosition.y + delta.y;
      obj.position.z = startPosition.z + delta.z;
    } 
    else if (selectedAxis === 'xz') {
      obj.position.x = startPosition.x + delta.x;
      obj.position.z = startPosition.z + delta.z;
    } 
    else if (selectedAxis === 'x') {
      obj.position.x = startPosition.x + delta.x;
    } 
    else if (selectedAxis === 'y') {
      obj.position.y = startPosition.y + delta.y;
    } 
    else if (selectedAxis === 'z') {
      obj.position.z = startPosition.z + delta.z;
    } 
    else if (selectedAxis === 'center') {
      obj.position.x = startPosition.x + delta.x;
      obj.position.y = startPosition.y + delta.y;
      obj.position.z = startPosition.z + delta.z;
    }
    
    console.log("New object position:", obj.position.clone());
    
    // CRITICAL FIX: Force matrix updates to propagate to children
    obj.updateMatrix();
    obj.updateMatrixWorld(true);
    
    // Force scene update to ensure ALL objects update
    scene.updateMatrixWorld(true);
    
    // Update wireframe position if it exists
    const wireframe = scene.getObjectByName("currentSelectionWireframe");
    if (wireframe && selectedObject) {
      const worldPos = new THREE.Vector3();
      selectedObject.getWorldPosition(worldPos);
      wireframe.position.copy(worldPos);
      wireframe.quaternion.copy(selectedObject.quaternion);
      wireframe.scale.copy(selectedObject.scale);
    }
    
    // Update gizmo position to match
    gizmoGroup.position.copy(obj.position);
  }
  
  function applyScaling(delta, intersection) {
    const obj = gizmoGroup.targetObject;
    
    // For uniform scaling (center cube)
    if (selectedAxis === 'scaleXYZ') {
      const startDistance = startPoint.distanceTo(gizmoGroup.position);
      const currentDistance = intersection.distanceTo(gizmoGroup.position);
      const scaleFactor = Math.max(0.01, currentDistance / startDistance);
      
      // Apply uniform scaling
      obj.scale.set(
        startScale.x * scaleFactor,
        startScale.y * scaleFactor,
        startScale.z * scaleFactor
      );
    } 
    // For axis scaling (individual axes)
    else {
      // Project delta onto the relevant axis
      const axisVector = new THREE.Vector3();
      let direction = 1;
      
      if (selectedAxis === 'scaleX') {
        axisVector.set(1, 0, 0);
        direction = delta.dot(axisVector) >= 0 ? 1 : -1; 
      } else if (selectedAxis === 'scaleY') {
        axisVector.set(0, 1, 0);
        direction = delta.dot(axisVector) >= 0 ? 1 : -1;
      } else if (selectedAxis === 'scaleZ') {
        axisVector.set(0, 0, 1);
        direction = delta.dot(axisVector) >= 0 ? 1 : -1;
      }
      
      // Calculate scale based on projected distance
      const projectedDistance = Math.abs(delta.dot(axisVector));
      const scaleFactor = Math.max(0.01, 1 + direction * projectedDistance * 2);
      
      // Apply axis-specific scaling
      if (selectedAxis === 'scaleX') {
        obj.scale.x = startScale.x * scaleFactor;
      } else if (selectedAxis === 'scaleY') {
        obj.scale.y = startScale.y * scaleFactor;
      } else if (selectedAxis === 'scaleZ') {
        obj.scale.z = startScale.z * scaleFactor;
      }
    }
    
    // Force update object's matrix
    obj.updateMatrix();
    obj.updateMatrixWorld(true);
  }
  
  function applyRotation(delta, intersection) {
    const obj = gizmoGroup.targetObject;
    const center = gizmoGroup.position;
    
    // Get vectors from center to start and current intersection points
    const startVec = new THREE.Vector3().subVectors(startPoint, center).normalize();
    const currentVec = new THREE.Vector3().subVectors(intersection, center).normalize();
    
    // Handle axis-specific rotation
    if (selectedAxis === 'rotateX' || selectedAxis === 'rotateY' || selectedAxis === 'rotateZ') {
      // Set rotation axis
      const rotAxis = new THREE.Vector3();
      if (selectedAxis === 'rotateX') rotAxis.set(1, 0, 0);
      else if (selectedAxis === 'rotateY') rotAxis.set(0, 1, 0);
      else rotAxis.set(0, 0, 1);
      
      // Project vectors onto plane perpendicular to rotation axis
      const projStartVec = new THREE.Vector3().copy(startVec);
      const projCurrentVec = new THREE.Vector3().copy(currentVec);
      
      // Zero out component along rotation axis
      if (selectedAxis === 'rotateX') {
        projStartVec.x = 0;
        projCurrentVec.x = 0;
      } else if (selectedAxis === 'rotateY') {
        projStartVec.y = 0;
        projCurrentVec.y = 0;
      } else {
        projStartVec.z = 0;
        projCurrentVec.z = 0;
      }
      
      projStartVec.normalize();
      projCurrentVec.normalize();
      
      // Calculate angle between these two projected vectors
      let angle = Math.acos(Math.max(-1, Math.min(1, projStartVec.dot(projCurrentVec))));
      
      // Determine rotation direction (clockwise/counterclockwise)
      const cross = new THREE.Vector3().crossVectors(projStartVec, projCurrentVec);
      if (cross.dot(rotAxis) < 0) angle = -angle;
      
      // Create quaternion for this rotation
      const quaternion = new THREE.Quaternion().setFromAxisAngle(rotAxis, angle);
      
      // Apply rotation from start quaternion
      obj.quaternion.copy(startQuaternion).multiply(quaternion);
    }
    
    // Update object matrix
    obj.updateMatrix();
    obj.updateMatrixWorld(true);
  }
  
  function onPointerUp(event) {
    if (!isDragging) return;
    
    // CRITICAL FIX: Reset pointerDownOnGizmo flag
    pointerDownOnGizmo = false;
    
    // Set ignoreNextClick to prevent the click event from deselecting
    ignoreNextClick = true;
    setTimeout(() => {
        ignoreNextClick = false;
    }, 100);
    
    // Re-enable orbit controls
    controls.enabled = true;
    
    // Notify drag ended
    gizmoGroup.dispatchEvent({ type: 'dragging-changed', value: false });
    
    // CRITICAL FIX: Use a more reliable way to maintain selection
    if (gizmoGroup.targetObject) {
        const obj = gizmoGroup.targetObject;
        
        // Ensure transform controls stay attached
        setTimeout(() => {
            if (obj && !gizmoGroup.parent) {
                scene.add(gizmoGroup);
                gizmoGroup.attach(obj);
                gizmoGroup.visible = true;
                
                // Update status to confirm selection maintained
                updateStatus(`Selected: ${obj.name}`);
            }
        }, 0);
    }
    
    // Reset drag state with delay
    setTimeout(() => {
        isDragging = false;
        selectedAxis = null;
        gizmoGroup.userData.activeTransform = false;
    }, 100);
    
    // Force a render
    renderer.render(scene, camera);
  }
  
  // Add event dispatcher capability to the gizmo group
  gizmoGroup.addEventListener = THREE.EventDispatcher.prototype.addEventListener;
  gizmoGroup.hasEventListener = THREE.EventDispatcher.prototype.hasEventListener;
  gizmoGroup.removeEventListener = THREE.EventDispatcher.prototype.removeEventListener;
  gizmoGroup.dispatchEvent = THREE.EventDispatcher.prototype.dispatchEvent;
  
  // Make the gizmo not visible by default
  gizmoGroup.visible = false;
  
  return gizmoGroup;
}

// 3. In your init function, replace the TransformControls setup with:
// transformControls = createCustomTransformGizmo(camera, renderer, scene);
// transformControls.setMode(currentTransformMode);

// 4. Update your animate function to update the custom gizmo
// function animate() {
//   requestAnimationFrame(animate);
  
//   // Update the custom gizmo if it has a target
//   if (transformControls && transformControls.targetObject) {
//     transformControls.userData.update();z
//   }
  
//   controls.update();
//   renderer.render(scene, camera);
// }

// Add this helper function to find the transformable parent
function findTransformableParent(object) {
  // Start with the selected object
  let current = object;
  let parent = object.parent;
  
  // If this is already a top-level object or direct child of the scene, use it
  if (!parent || parent.isScene) {
    return current;
  }

  // For models loaded from GLTF, the proper transformable parent is usually:
  // 1. The first parent with a name that isn't an empty string
  // 2. The first parent that contains multiple mesh children
  // 3. The highest level before reaching the scene
  let foundNamedParent = false;
  
  while (parent && !parent.isScene) {
    // Track if we found a proper named parent
    if (parent.name && parent.name !== "") {
      foundNamedParent = true;
    }
    
    // Check if this is a "container" node with multiple children
    const hasManyChildren = parent.children && parent.children.length > 1;
    
    // Stop if we've found a parent with a name and multiple children
    if (foundNamedParent && hasManyChildren) {
      return parent;
    }
    
    // Move up the hierarchy
    current = parent;
    parent = parent.parent;
  }
  
  // Return the highest non-scene parent if we got here
  return current;
}

// Add this debug function somewhere in your code
function debugObjectHierarchy(object, indent = 0) {
  const spaces = ' '.repeat(indent);
  console.log(`${spaces}${object.name || "unnamed"} (${object.type})`);
  
  if (object.children && object.children.length > 0) {
    object.children.forEach(child => {
      debugObjectHierarchy(child, indent + 2);
    });
  }
}

// Call it when needed:
// debugObjectHierarchy(scene);

// 3. Add this to handle events that might be lost between window contexts

// Add this to your window event listeners
window.addEventListener('blur', function() {
  // If we lose focus during a drag, clean up properly
  if (isDragging) {
    isDragging = false;
    selectedAxis = null;
    controls.enabled = true;
    
    // Make sure transform controls stay attached
    if (transformControls && transformControls.targetObject) {
      // Ensure gizmo is visible and in the scene
      transformControls.visible = true;
      if (!transformControls.parent) {
        scene.add(transformControls);
      }
    }
  }
});
