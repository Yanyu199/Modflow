import * as THREE from 'three';

export function detectWebGLCapabilities(renderer) {
  const gl = renderer && renderer.getContext ? renderer.getContext() : null;
  if (!gl) {
    return { available: false, maxTextureSize: 0, maxVertexUniforms: 0 };
  }
  return {
    available: true,
    maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
    maxVertexUniforms: gl.getParameter(gl.MAX_VERTEX_UNIFORM_VECTORS),
    precision: renderer.capabilities ? renderer.capabilities.precision : null,
    isWebGL2: renderer.capabilities ? renderer.capabilities.isWebGL2 : false
  };
}

export function createBaseScene() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf0f9ff);
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(500, 2000, 1000);
  dirLight.castShadow = true;
  scene.add(dirLight);
  return scene;
}
