import Vue from 'vue';

export const projectStore = Vue.observable({
  currentProject: null,
  loading: false,
  error: null
});

export function setCurrentProject(project) {
  projectStore.currentProject = project || null;
}

export function updateProjectReferences(references) {
  if (!projectStore.currentProject) return;
  projectStore.currentProject = {
    ...projectStore.currentProject,
    references: {
      ...(projectStore.currentProject.references || {}),
      ...(references || {})
    }
  };
}

export function resetProjectStore() {
  projectStore.currentProject = null;
  projectStore.loading = false;
  projectStore.error = null;
}
