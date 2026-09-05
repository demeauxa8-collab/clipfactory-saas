"use client"

import * as React from "react"
import { useEffect, useRef } from "react"
import * as THREE from "three"

/**
 * Pulse Grid — a lattice of circuit traces where individual segments light up,
 * hold, and fade back into the board. Sourced from Originkit.
 *
 * Every segment of the grid is one instance of a single quad, so a grid of any
 * density is one draw call: what changes per frame is the instance colour
 * buffer, written in place. A segment is a tiny state machine — dark, charging,
 * decaying — and each frame it either rolls to start charging or advances the
 * state it is already in, which is what makes the board read as traffic on a
 * circuit rather than as a repeating animation.
 */

const DEFAULTS = {
    boardColor: "#000000",
    cellSize: 10,
    thickness: 3,
    lineColor: "#222222",
    palette: ["#00FFFF", "#FF0080", "#FFFF00", "#00FF80"],
    intensity: 10,
    fadeIn: 20,
    fadeOut: 5,
    brightness: 100,
}

const BRIGHTNESS_PER_PERCENT = 0.2

const DARK = 0
const CHARGING = 1
const DECAYING = -1

const MAX_COLORS = 5

type Config = {
    boardColor: string
    cellSize: number
    thickness: number
    lineColor: string
    palette: string[]
    intensity: number
    fadeIn: number
    fadeOut: number
    brightness: number
}

function clamp(v: number, lo: number, hi: number, fallback: number): number {
    const n = typeof v === "number" && isFinite(v) ? v : fallback
    return Math.max(lo, Math.min(hi, n))
}

function settingsFor(cfg: Config) {
    return {
        boardColor: cfg.boardColor || DEFAULTS.boardColor,
        cellSize: Math.round(clamp(cfg.cellSize, 10, 200, DEFAULTS.cellSize)),
        thickness: clamp(cfg.thickness, 1, 10, DEFAULTS.thickness) * 0.5,
        lineColor: cfg.lineColor || DEFAULTS.lineColor,
        intensity: clamp(cfg.intensity, 1, 20, DEFAULTS.intensity) * 0.035,
        attack: 0.5 + clamp(cfg.fadeIn, 1, 20, DEFAULTS.fadeIn) * 0.5,
        decay: 0.6 + clamp(cfg.fadeOut, 1, 20, DEFAULTS.fadeOut) * 0.35,
        brightness:
            clamp(cfg.brightness, 1, 100, DEFAULTS.brightness) *
            BRIGHTNESS_PER_PERCENT,
    }
}

function paletteOf(value: unknown): string[] {
    const list = (Array.isArray(value) ? value : DEFAULTS.palette)
        .slice(0, MAX_COLORS)
        .filter((c): c is string => typeof c === "string" && !!c)
    return list.length ? list : DEFAULTS.palette
}

class PulseScene {
    private container: HTMLElement
    private cfg: Config

    private renderer: THREE.WebGLRenderer
    private scene = new THREE.Scene()
    private camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1000)
    private geometry = new THREE.PlaneGeometry(1, 1)
    private material: THREE.MeshBasicMaterial
    private mesh: THREE.InstancedMesh | null = null

    private brightness = new Float32Array(0)
    private phase = new Int8Array(0)
    private colorIndex = new Int32Array(0)
    private count = 0

    private palette: THREE.Color[] = []
    private base = new THREE.Color()

    private width = 0
    private height = 0
    private frameId = 0
    private lastT = 0
    private disposed = false

    constructor(container: HTMLElement, cfg: Config) {
        this.container = container
        this.cfg = cfg

        this.renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: true,
            powerPreference: "high-performance",
        })
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
        this.renderer.setClearColor(0x000000, 0)
        this.renderer.outputColorSpace = THREE.SRGBColorSpace
        const el = this.renderer.domElement
        el.style.position = "absolute"
        el.style.inset = "0"
        el.style.width = "100%"
        el.style.height = "100%"
        el.style.display = "block"
        container.appendChild(el)

        this.material = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
        })
        this.camera.position.z = 100
        this.applyColors()
    }

    private applyColors() {
        const S = settingsFor(this.cfg)
        this.base.set(S.lineColor)
        this.palette = paletteOf(this.cfg.palette).map(
            (hex) => new THREE.Color(hex)
        )
    }

    private build() {
        const S = settingsFor(this.cfg)
        const w = this.width
        const h = this.height
        if (!w || !h) return

        const stroke = S.thickness
        const safeW = Math.max(1, w - stroke)
        const safeH = Math.max(1, h - stroke)
        const pad = stroke / 2

        const cols = Math.max(1, Math.floor(safeW / S.cellSize))
        const rows = Math.max(1, Math.floor(safeH / S.cellSize))

        const cellW = safeW / cols
        const cellH = safeH / rows
        const total = (cols + 1) * rows + (rows + 1) * cols

        this.disposeMesh()

        const mesh = new THREE.InstancedMesh(
            this.geometry,
            this.material,
            total
        )
        mesh.instanceMatrix.setUsage(THREE.StaticDrawUsage)
        mesh.instanceColor = new THREE.InstancedBufferAttribute(
            new Float32Array(total * 3),
            3
        )
        mesh.instanceColor.setUsage(THREE.DynamicDrawUsage)
        mesh.frustumCulled = false
        this.scene.add(mesh)
        this.mesh = mesh

        this.brightness = new Float32Array(total)
        this.phase = new Int8Array(total)
        this.colorIndex = new Int32Array(total)
        this.count = total

        const dummy = new THREE.Object3D()
        let idx = 0
        const place = (x: number, y: number, sx: number, sy: number) => {
            dummy.position.set(x - w / 2, -(y - h / 2), 0)
            dummy.scale.set(sx, sy, 1)
            dummy.updateMatrix()
            mesh.setMatrixAt(idx, dummy.matrix)
            this.colorIndex[idx] = Math.floor(
                Math.random() * this.palette.length
            )
            idx++
        }

        for (let i = 0; i <= cols; i++)
            for (let j = 0; j < rows; j++)
                place(
                    pad + i * cellW,
                    pad + j * cellH + cellH / 2,
                    stroke,
                    cellH + stroke * 0.5
                )

        for (let j = 0; j <= rows; j++)
            for (let i = 0; i < cols; i++)
                place(
                    pad + i * cellW + cellW / 2,
                    pad + j * cellH,
                    cellW + stroke * 0.5,
                    stroke
                )

        mesh.instanceMatrix.needsUpdate = true

        const colors = mesh.instanceColor.array as Float32Array
        for (let i = 0; i < total; i++) {
            colors[i * 3] = this.base.r
            colors[i * 3 + 1] = this.base.g
            colors[i * 3 + 2] = this.base.b
        }
        mesh.instanceColor.needsUpdate = true
    }

    private disposeMesh() {
        if (!this.mesh) return
        this.scene.remove(this.mesh)
        this.mesh.dispose()
        this.mesh = null
    }

    setSize(width: number, height: number) {
        if (this.disposed || width <= 0 || height <= 0) return
        this.width = width
        this.height = height
        this.renderer.setSize(width, height, false)
        this.camera.left = -width / 2
        this.camera.right = width / 2
        this.camera.top = height / 2
        this.camera.bottom = -height / 2
        this.camera.updateProjectionMatrix()
        this.build()
    }

    updateConfig(cfg: Config) {
        if (this.disposed) return
        const prev = this.cfg
        this.cfg = cfg
        this.applyColors()

        if (
            cfg.cellSize !== prev.cellSize ||
            cfg.thickness !== prev.thickness
        ) {
            this.build()
            return
        }

        const n = this.palette.length
        for (let i = 0; i < this.count; i++)
            if (this.colorIndex[i] >= n) this.colorIndex[i] = this.colorIndex[i] % n
    }

    start() {
        this.lastT = performance.now()
        const loop = () => {
            this.frameId = requestAnimationFrame(loop)
            this.step()
        }
        loop()
    }

    private step() {
        if (this.disposed) return
        const now = performance.now()
        let dt = (now - this.lastT) / 1000
        this.lastT = now
        if (!isFinite(dt) || dt < 0) dt = 0
        if (dt > 0.05) dt = 0.05

        const mesh = this.mesh
        if (!mesh || !mesh.instanceColor) {
            this.renderer.render(this.scene, this.camera)
            return
        }

        const S = settingsFor(this.cfg)
        const colors = mesh.instanceColor.array as Float32Array
        const palette = this.palette
        const base = this.base
        const spark = 1 - Math.exp(-S.intensity * dt)
        const decay = Math.exp(-S.decay * dt)
        const attack = S.attack * dt

        for (let i = 0; i < this.count; i++) {
            const p = this.phase[i]
            if (p === DARK) {
                if (Math.random() < spark) {
                    this.phase[i] = CHARGING
                    this.colorIndex[i] = Math.floor(
                        Math.random() * palette.length
                    )
                } else {
                    continue
                }
            } else if (p === CHARGING) {
                this.brightness[i] += attack
                if (this.brightness[i] >= 1) {
                    this.brightness[i] = 1
                    this.phase[i] = DECAYING
                }
            } else {
                this.brightness[i] *= decay
                if (this.brightness[i] < 0.01) {
                    this.brightness[i] = 0
                    this.phase[i] = DARK
                }
            }

            const lit = palette[this.colorIndex[i]] ?? palette[0]
            const t = Math.min(1, this.brightness[i] * S.brightness)
            const o = i * 3
            colors[o] = base.r + (lit.r - base.r) * t
            colors[o + 1] = base.g + (lit.g - base.g) * t
            colors[o + 2] = base.b + (lit.b - base.b) * t
        }

        mesh.instanceColor.needsUpdate = true
        this.renderer.render(this.scene, this.camera)
    }

    dispose() {
        this.disposed = true
        cancelAnimationFrame(this.frameId)
        this.disposeMesh()
        this.geometry.dispose()
        this.material.dispose()
        this.renderer.dispose()
        const el = this.renderer.domElement
        if (el.parentNode === this.container) this.container.removeChild(el)
    }
}

interface PulseGridProps {
    boardColor?: string
    cellSize?: number
    thickness?: number
    lineColor?: string
    palette?: string[]
    intensity?: number
    fadeIn?: number
    fadeOut?: number
    brightness?: number
    style?: React.CSSProperties
}

export default function PulseGrid(props: PulseGridProps) {
    const {
        boardColor = DEFAULTS.boardColor,
        cellSize = DEFAULTS.cellSize,
        thickness = DEFAULTS.thickness,
        lineColor = DEFAULTS.lineColor,
        palette = ["#D4FF00", "#00FF72"],
        intensity = DEFAULTS.intensity,
        fadeIn = DEFAULTS.fadeIn,
        fadeOut = DEFAULTS.fadeOut,
        brightness = DEFAULTS.brightness,
        style,
    } = props

    const containerRef = useRef<HTMLDivElement | null>(null)
    const sceneRef = useRef<PulseScene | null>(null)

    const cfgRef = useRef<Config>(null as any)
    cfgRef.current = {
        boardColor,
        cellSize,
        thickness,
        lineColor,
        palette,
        intensity,
        fadeIn,
        fadeOut,
        brightness,
    }

    useEffect(() => {
        const container = containerRef.current
        if (!container) return
        let scene: PulseScene
        try {
            scene = new PulseScene(container, cfgRef.current)
        } catch {
            return
        }
        sceneRef.current = scene
        scene.setSize(container.clientWidth, container.clientHeight)
        scene.start()

        const ro = new ResizeObserver(() => {
            scene.setSize(container.clientWidth, container.clientHeight)
        })
        ro.observe(container)
        return () => {
            ro.disconnect()
            scene.dispose()
            sceneRef.current = null
        }
    }, [])

    useEffect(() => {
        sceneRef.current?.updateConfig(cfgRef.current)
    }, [
        boardColor,
        cellSize,
        thickness,
        lineColor,
        palette,
        intensity,
        fadeIn,
        fadeOut,
        brightness,
    ])

    return (
        <div
            ref={containerRef}
            role="img"
            aria-label="Pulsing circuit grid"
            style={{
                position: "relative",
                width: "100%",
                height: "100%",
                overflow: "hidden",
                backgroundColor: boardColor,
                ...style,
            }}
        />
    )
}
