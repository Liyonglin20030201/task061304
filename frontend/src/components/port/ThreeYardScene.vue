<template>
  <div ref="containerRef" class="three-yard-scene"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const props = defineProps({
  containers: { type: Array, default: () => [] },
  equipment: { type: Array, default: () => [] },
  readings: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select-container'])
const containerRef = ref(null)

let scene, camera, renderer, controls, raycaster, mouse
let containerMeshes = []
let craneMeshes = []
let agvMeshes = []
let animationId = null

const YARD_WIDTH = 400
const YARD_DEPTH = 200
const CONTAINER_WIDTH = 6.1
const CONTAINER_HEIGHT = 2.6
const CONTAINER_DEPTH = 2.44
const SCALE = 0.5

const STATUS_COLORS = {
  stacked: 0x67c23a,
  en_route: 0xe6a23c,
  arrived: 0x409eff,
  retrieving: 0xf56c6c,
  departed: 0x909399,
}

function init() {
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a2e)
  scene.fog = new THREE.Fog(0x1a1a2e, 300, 600)

  camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 2000)
  camera.position.set(150, 100, 200)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  containerRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.maxPolarAngle = Math.PI / 2.1

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4)
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLight.position.set(100, 150, 100)
  dirLight.castShadow = true
  scene.add(dirLight)

  createGround()
  createYardGrid()
  createContainers()
  createCranes()
  createAGVs()

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()
  renderer.domElement.addEventListener('click', onMouseClick)
  window.addEventListener('resize', onResize)
}

function createGround() {
  const geometry = new THREE.PlaneGeometry(YARD_WIDTH * SCALE, YARD_DEPTH * SCALE)
  const material = new THREE.MeshLambertMaterial({ color: 0x2d2d3d })
  const ground = new THREE.Mesh(geometry, material)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  const waterGeom = new THREE.PlaneGeometry(YARD_WIDTH * SCALE, 40)
  const waterMat = new THREE.MeshLambertMaterial({ color: 0x1e3a5f, transparent: true, opacity: 0.8 })
  const water = new THREE.Mesh(waterGeom, waterMat)
  water.rotation.x = -Math.PI / 2
  water.position.set(0, -0.1, -YARD_DEPTH * SCALE / 2 - 20)
  scene.add(water)
}

function createYardGrid() {
  const gridHelper = new THREE.GridHelper(YARD_WIDTH * SCALE, 40, 0x444466, 0x333355)
  gridHelper.position.y = 0.01
  scene.add(gridHelper)

  for (let i = 0; i < 4; i++) {
    const blockGeom = new THREE.BoxGeometry(60, 0.1, 40)
    const blockMat = new THREE.MeshLambertMaterial({ color: 0x3d3d5c, transparent: true, opacity: 0.5 })
    const block = new THREE.Mesh(blockGeom, blockMat)
    block.position.set(-60 + i * 45, 0.05, 20)
    scene.add(block)
  }
}

function createContainers() {
  containerMeshes.forEach(m => scene.remove(m))
  containerMeshes = []

  const geometry = new THREE.BoxGeometry(
    CONTAINER_WIDTH * SCALE * 0.3,
    CONTAINER_HEIGHT * SCALE * 0.3,
    CONTAINER_DEPTH * SCALE * 0.3
  )

  props.containers.forEach((c, idx) => {
    const color = STATUS_COLORS[c.status] || 0x909399
    const material = new THREE.MeshLambertMaterial({ color })
    const mesh = new THREE.Mesh(geometry, material)

    const block = c.yard_bay || (idx % 20)
    const row = c.yard_row || Math.floor(idx / 20) % 6
    const tier = c.yard_tier || Math.floor(idx / 120)

    mesh.position.set(
      -80 + block * 4 * SCALE,
      tier * CONTAINER_HEIGHT * SCALE * 0.3 + CONTAINER_HEIGHT * SCALE * 0.15,
      row * 4 * SCALE + 5
    )
    mesh.castShadow = true
    mesh.userData = { type: 'container', data: c }
    scene.add(mesh)
    containerMeshes.push(mesh)
  })
}

function createCranes() {
  const craneEquipment = props.equipment.filter(e => e.equipment_type === 'crane')
  craneEquipment.forEach((eq, idx) => {
    const group = new THREE.Group()

    const legGeom = new THREE.BoxGeometry(1, 25, 1)
    const legMat = new THREE.MeshLambertMaterial({ color: 0xff6600 })
    const leg1 = new THREE.Mesh(legGeom, legMat)
    leg1.position.set(-5, 12.5, 0)
    group.add(leg1)
    const leg2 = new THREE.Mesh(legGeom, legMat)
    leg2.position.set(5, 12.5, 0)
    group.add(leg2)

    const beamGeom = new THREE.BoxGeometry(30, 2, 2)
    const beam = new THREE.Mesh(beamGeom, legMat)
    beam.position.set(0, 25, 0)
    group.add(beam)

    const trolleyGeom = new THREE.BoxGeometry(3, 1, 2)
    const trolleyMat = new THREE.MeshLambertMaterial({ color: 0xffcc00 })
    const trolley = new THREE.Mesh(trolleyGeom, trolleyMat)
    trolley.position.set(0, 24, 0)
    group.add(trolley)

    group.position.set(
      (eq.location_x || idx * 50) * SCALE - 80,
      0,
      (eq.location_y || 0) * SCALE - 50
    )
    group.userData = { type: 'crane', data: eq }
    scene.add(group)
    craneMeshes.push(group)
  })
}

function createAGVs() {
  const agvEquipment = props.equipment.filter(e => e.equipment_type === 'agv')
  agvEquipment.forEach((eq, idx) => {
    const bodyGeom = new THREE.BoxGeometry(4, 1.5, 2.5)
    const bodyMat = new THREE.MeshLambertMaterial({ color: 0x00ccff })
    const body = new THREE.Mesh(bodyGeom, bodyMat)
    body.position.set(
      (eq.location_x || idx * 30) * SCALE - 60,
      0.75,
      (eq.location_y || 50) * SCALE - 20
    )
    body.userData = { type: 'agv', data: eq }
    scene.add(body)
    agvMeshes.push(body)
  })
}

function onMouseClick(event) {
  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(containerMeshes)
  if (intersects.length > 0) {
    const obj = intersects[0].object
    if (obj.userData?.data) {
      emit('select-container', obj.userData.data)
    }
  }
}

function onResize() {
  if (!containerRef.value) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function animate() {
  animationId = requestAnimationFrame(animate)
  controls.update()

  agvMeshes.forEach((agv, idx) => {
    const time = Date.now() * 0.001
    agv.position.x += Math.sin(time + idx) * 0.02
    agv.position.z += Math.cos(time + idx * 0.7) * 0.01
  })

  renderer.render(scene, camera)
}

onMounted(() => {
  init()
  animate()
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  renderer?.domElement.removeEventListener('click', onMouseClick)
  window.removeEventListener('resize', onResize)
  renderer?.dispose()
  scene?.traverse(obj => {
    if (obj.geometry) obj.geometry.dispose()
    if (obj.material) {
      if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose())
      else obj.material.dispose()
    }
  })
})

watch(() => props.containers, () => { createContainers() }, { deep: true })
</script>

<style scoped>
.three-yard-scene {
  width: 100%;
  height: 100%;
  min-height: 500px;
}
</style>
