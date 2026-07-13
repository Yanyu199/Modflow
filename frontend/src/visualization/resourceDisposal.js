function disposeMaterial(material) {
  if (!material) return;
  const materials = Array.isArray(material) ? material : [material];
  materials.forEach(item => {
    if (!item) return;
    Object.keys(item).forEach(key => {
      const value = item[key];
      if (value && typeof value.dispose === 'function' && value.isTexture) {
        value.dispose();
      }
    });
    if (typeof item.dispose === 'function') item.dispose();
  });
}

export function disposeObject3D(object) {
  if (!object) return;
  object.traverse(child => {
    if (child.geometry && typeof child.geometry.dispose === 'function') {
      child.geometry.dispose();
    }
    disposeMaterial(child.material);
  });
}

export function removeAndDispose(scene, object) {
  if (!object) return;
  if (scene && scene.remove) scene.remove(object);
  disposeObject3D(object);
}

export function disposeScene(scene) {
  if (!scene) return;
  const children = scene.children ? scene.children.slice() : [];
  children.forEach(child => removeAndDispose(scene, child));
}

export function disposeRenderer(renderer, { forceContextLoss = false } = {}) {
  if (!renderer) return;
  if (renderer.renderLists && renderer.renderLists.dispose) renderer.renderLists.dispose();
  renderer.dispose();
  if (forceContextLoss && renderer.forceContextLoss) renderer.forceContextLoss();
}
