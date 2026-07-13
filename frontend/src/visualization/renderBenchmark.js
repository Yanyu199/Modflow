export async function runInstancedMeshBenchmark(THREE, renderer, options = {}) {
  const counts = options.counts || [10000, 50000, 100000, 200000];
  const frames = options.frames || 90;
  const results = [];

  for (const count of counts) {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 1, 100000);
    camera.position.set(500, 500, 500);
    camera.lookAt(0, 0, 0);
    scene.add(new THREE.AmbientLight(0xffffff, 0.8));

    const side = Math.ceil(Math.sqrt(count));
    const geometry = new THREE.BoxGeometry(0.8, 0.8, 0.8);
    const material = new THREE.MeshBasicMaterial({ color: 0x4b8bbe });
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    const dummy = new THREE.Object3D();

    const buildStart = performance.now();
    for (let i = 0; i < count; i += 1) {
      const x = i % side;
      const z = Math.floor(i / side);
      dummy.position.set(x - side / 2, 0, z - side / 2);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    scene.add(mesh);

    const firstFrameStart = performance.now();
    renderer.render(scene, camera);
    const firstFrameMs = performance.now() - firstFrameStart;

    const frameTimes = [];
    let previous = performance.now();
    for (let frame = 0; frame < frames; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const now = performance.now();
      frameTimes.push(now - previous);
      previous = now;
      renderer.render(scene, camera);
    }

    const colorStart = performance.now();
    const color = new THREE.Color();
    for (let i = 0; i < count; i += 1) {
      color.setHSL((i % side) / side, 0.6, 0.5);
      mesh.setColorAt(i, color);
    }
    mesh.instanceColor.needsUpdate = true;
    renderer.render(scene, camera);
    const colorUpdateMs = performance.now() - colorStart;

    const pickingStart = performance.now();
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
    const intersections = raycaster.intersectObject(mesh, false);
    const pickingMs = performance.now() - pickingStart;

    frameTimes.sort((a, b) => a - b);
    const p95 = frameTimes[Math.min(frameTimes.length - 1, Math.floor(frameTimes.length * 0.95))] || 0;
    const avgFrame = frameTimes.reduce((sum, value) => sum + value, 0) / Math.max(frameTimes.length, 1);
    const heapBeforeDispose = performance.memory ? performance.memory.usedJSHeapSize : null;
    const drawCalls = renderer.info.render.calls;
    const triangles = renderer.info.render.triangles;
    const geometryBytes = geometry.attributes.position.array.byteLength + geometry.index.array.byteLength + mesh.instanceMatrix.array.byteLength;

    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
    renderer.renderLists.dispose();
    renderer.info.reset();
    const heapAfterDispose = performance.memory ? performance.memory.usedJSHeapSize : null;

    results.push({
      instances: count,
      renderer: 'InstancedMesh',
      build_ms: performance.now() - buildStart,
      first_frame_ms: firstFrameMs,
      average_fps: avgFrame > 0 ? 1000 / avgFrame : null,
      p95_frame_ms: p95,
      draw_calls: drawCalls,
      triangles,
      geometry_bytes: geometryBytes,
      estimated_gpu_buffer_bytes: geometryBytes,
      picking_ms: pickingMs,
      picking_hits: intersections.length,
      color_update_ms: colorUpdateMs,
      heap_before_dispose: heapBeforeDispose,
      heap_after_dispose: heapAfterDispose,
      heap_delta_after_dispose: heapBeforeDispose !== null && heapAfterDispose !== null ? heapAfterDispose - heapBeforeDispose : null,
    });
  }

  return {
    generated_at: new Date().toISOString(),
    user_agent: navigator.userAgent,
    results,
  };
}
