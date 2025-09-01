import { createRouter, createWebHistory } from 'vue-router'
import Upload from '../views/Upload.vue'
import Projects from '../views/Projects.vue'
import Config from '../views/Config.vue'
import ProcessTask from '../views/ProcessTask.vue'

const routes = [
  {
    path: '/',
    redirect: '/upload'
  },
  {
    path: '/upload',
    name: 'Upload',
    component: Upload
  },
  {
    path: '/projects',
    name: 'Projects', 
    component: Projects
  },
  {
    path: '/config',
    name: 'Config',
    component: Config
  },
  {
    path: '/process/:projectId',
    name: 'ProcessTask',
    component: ProcessTask
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router