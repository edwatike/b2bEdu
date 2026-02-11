"use client"

import { motion } from "framer-motion"

interface FlinstonesWheelProps {
  progress: number // 0-100
  size?: number // px
  label?: string
  sublabel?: string
  isActive?: boolean
}

/**
 * Flintstones-style hexagonal stone wheel progress indicator.
 * The wheel "struggles" to roll forward, wobbling and bumping on its flat edges.
 */
export function FlinstonesWheel({
  progress,
  size = 64,
  label,
  sublabel,
  isActive = true,
}: FlinstonesWheelProps) {
  const radius = size / 2
  const strokeWidth = size * 0.08
  const hexRadius = radius - strokeWidth - 2
  const center = radius

  // Build hexagon path
  const hexPoints = Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 2
    return {
      x: center + hexRadius * Math.cos(angle),
      y: center + hexRadius * Math.sin(angle),
    }
  })
  const hexPath = hexPoints.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ") + " Z"

  // Progress arc (circumscribed circle for measuring)
  const circumference = 2 * Math.PI * (hexRadius * 0.85)
  const dashOffset = circumference - (progress / 100) * circumference

  // Stone crack lines for texture
  const cracks = [
    { x1: center - hexRadius * 0.3, y1: center - hexRadius * 0.2, x2: center + hexRadius * 0.1, y2: center + hexRadius * 0.3 },
    { x1: center + hexRadius * 0.2, y1: center - hexRadius * 0.4, x2: center + hexRadius * 0.05, y2: center + hexRadius * 0.1 },
    { x1: center - hexRadius * 0.1, y1: center + hexRadius * 0.2, x2: center - hexRadius * 0.4, y2: center + hexRadius * 0.05 },
  ]

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Ground shadow */}
        {isActive && (
          <motion.div
            className="absolute rounded-full bg-stone-400/20"
            style={{
              width: size * 0.7,
              height: size * 0.08,
              bottom: -size * 0.04,
              left: size * 0.15,
            }}
            animate={{
              scaleX: [1, 0.85, 1, 0.85, 1],
              opacity: [0.3, 0.2, 0.3, 0.2, 0.3],
            }}
            transition={{
              duration: 1.2,
              repeat: Number.POSITIVE_INFINITY,
              ease: "linear",
            }}
          />
        )}

        {/* Dust particles when active */}
        {isActive &&
          [0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="absolute rounded-full bg-amber-700/30"
              style={{
                width: size * 0.04,
                height: size * 0.04,
                bottom: size * 0.02,
                left: size * 0.3 + i * size * 0.12,
              }}
              animate={{
                y: [0, -size * 0.15, -size * 0.25],
                x: [-size * 0.05 * (i - 1), -size * 0.12 * (i - 1)],
                opacity: [0, 0.6, 0],
                scale: [0.5, 1.2, 0.3],
              }}
              transition={{
                duration: 0.8,
                repeat: Number.POSITIVE_INFINITY,
                delay: i * 0.3,
                ease: "easeOut",
              }}
            />
          ))}

        {/* The wheel itself */}
        <motion.div
          animate={
            isActive
              ? {
                  rotate: [0, -8, 60, 52, 120, 112, 180, 172, 240, 232, 300, 292, 360],
                  y: [0, -2, 0, -2, 0, -2, 0, -2, 0, -2, 0, -2, 0],
                }
              : { rotate: 0, y: 0 }
          }
          transition={
            isActive
              ? {
                  duration: 3,
                  repeat: Number.POSITIVE_INFINITY,
                  ease: [0.25, 0.1, 0.25, 1],
                }
              : undefined
          }
        >
          <svg
            width={size}
            height={size}
            viewBox={`0 0 ${size} ${size}`}
            className="drop-shadow-md"
          >
            {/* Stone texture background */}
            <defs>
              <radialGradient id={`stone-grad-${size}`} cx="40%" cy="35%">
                <stop offset="0%" stopColor="#d4c5a9" />
                <stop offset="50%" stopColor="#b8a88a" />
                <stop offset="100%" stopColor="#8c7c64" />
              </radialGradient>
              <filter id={`stone-texture-${size}`}>
                <feTurbulence
                  type="fractalNoise"
                  baseFrequency="0.9"
                  numOctaves="4"
                  result="noise"
                />
                <feColorMatrix
                  in="noise"
                  type="saturate"
                  values="0"
                  result="gray"
                />
                <feBlend in="SourceGraphic" in2="gray" mode="multiply" />
              </filter>
            </defs>

            {/* Hex body */}
            <path
              d={hexPath}
              fill={`url(#stone-grad-${size})`}
              stroke="#7a6b55"
              strokeWidth={strokeWidth * 0.7}
              strokeLinejoin="round"
            />

            {/* Cracks for stone texture */}
            {cracks.map((c, i) => (
              <line
                key={i}
                x1={c.x1}
                y1={c.y1}
                x2={c.x2}
                y2={c.y2}
                stroke="#9a8a70"
                strokeWidth={0.8}
                opacity={0.5}
                strokeLinecap="round"
              />
            ))}

            {/* Center hole */}
            <circle
              cx={center}
              cy={center}
              r={hexRadius * 0.2}
              fill="#6b5c48"
              stroke="#5a4d3b"
              strokeWidth={strokeWidth * 0.5}
            />
            <circle
              cx={center}
              cy={center}
              r={hexRadius * 0.12}
              fill="#8c7c64"
            />

            {/* Progress ring overlay */}
            <circle
              cx={center}
              cy={center}
              r={hexRadius * 0.85}
              fill="none"
              stroke="#3b82f6"
              strokeWidth={strokeWidth * 1.2}
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              opacity={0.7}
              transform={`rotate(-90 ${center} ${center})`}
              className="transition-all duration-500"
            />

            {/* Progress text */}
            <text
              x={center}
              y={center + size * 0.02}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={size * 0.2}
              fontWeight="bold"
              fill="#ffffff"
              stroke="#5a4d3b"
              strokeWidth={size * 0.015}
              paintOrder="stroke"
              className="font-mono"
            >
              {Math.round(progress)}%
            </text>
          </svg>
        </motion.div>

        {/* Effort sweat drops when active */}
        {isActive && progress < 100 && (
          <>
            <motion.div
              className="absolute"
              style={{
                top: -size * 0.05,
                right: size * 0.1,
                width: size * 0.06,
                height: size * 0.1,
                background: "#60a5fa",
                borderRadius: "50% 50% 50% 50% / 60% 60% 40% 40%",
                opacity: 0.7,
              }}
              animate={{
                y: [0, -size * 0.08, -size * 0.15],
                opacity: [0, 0.7, 0],
                scale: [0.5, 1, 0.3],
              }}
              transition={{
                duration: 1.5,
                repeat: Number.POSITIVE_INFINITY,
                delay: 0.3,
              }}
            />
            <motion.div
              className="absolute"
              style={{
                top: size * 0.05,
                left: -size * 0.02,
                width: size * 0.05,
                height: size * 0.08,
                background: "#60a5fa",
                borderRadius: "50% 50% 50% 50% / 60% 60% 40% 40%",
                opacity: 0.6,
              }}
              animate={{
                y: [0, -size * 0.1, -size * 0.18],
                x: [-size * 0.02, -size * 0.06],
                opacity: [0, 0.6, 0],
                scale: [0.5, 1, 0.2],
              }}
              transition={{
                duration: 1.8,
                repeat: Number.POSITIVE_INFINITY,
                delay: 0.8,
              }}
            />
          </>
        )}
      </div>

      {/* Labels */}
      {label && (
        <span className="text-xs font-semibold text-stone-700 text-center leading-tight">
          {label}
        </span>
      )}
      {sublabel && (
        <span className="text-[10px] text-stone-500 text-center leading-tight">
          {sublabel}
        </span>
      )}
    </div>
  )
}

/**
 * A horizontal progress bar with a small Flintstones wheel rolling along it.
 */
export function FlinstonesProgressBar({
  progress,
  label,
  color = "blue",
  total,
  current,
  isActive,
}: {
  progress: number
  label?: string
  color?: "blue" | "emerald" | "amber" | "red"
  total?: number
  current?: number
  isActive?: boolean
}) {
  const colorMap = {
    blue: {
      bar: "bg-blue-500",
      track: "bg-blue-100",
      text: "text-blue-700",
      glow: "shadow-blue-500/30",
    },
    emerald: {
      bar: "bg-emerald-500",
      track: "bg-emerald-100",
      text: "text-emerald-700",
      glow: "shadow-emerald-500/30",
    },
    amber: {
      bar: "bg-amber-500",
      track: "bg-amber-100",
      text: "text-amber-700",
      glow: "shadow-amber-500/30",
    },
    red: {
      bar: "bg-red-500",
      track: "bg-red-100",
      text: "text-red-700",
      glow: "shadow-red-500/30",
    },
  }

  const c = colorMap[color]
  const active = isActive ?? (progress > 0 && progress < 100)

  return (
    <div className="w-full">
      {label && (
        <div className="flex items-center justify-between mb-1.5">
          <span className={`text-xs font-medium ${c.text}`}>{label}</span>
          <span className="text-xs text-stone-500 font-mono">
            {current !== undefined && total !== undefined
              ? `${current}/${total}`
              : `${Math.round(progress)}%`}
          </span>
        </div>
      )}
      <div className={`relative w-full h-3 ${c.track} rounded-full overflow-visible`}>
        {/* Filled portion */}
        <motion.div
          className={`h-full ${c.bar} rounded-full relative shadow-sm ${c.glow}`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, progress)}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />

        {/* Mini rolling hexagonal wheel at the end of the bar */}
        {active && (
          <motion.div
            className="absolute top-1/2"
            style={{
              left: `${Math.min(97, progress)}%`,
              transform: "translateY(-50%)",
            }}
            animate={{
              x: [-1, 1, -1],
            }}
            transition={{
              duration: 0.4,
              repeat: Number.POSITIVE_INFINITY,
              ease: "linear",
            }}
          >
            <motion.svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              className="drop-shadow-sm"
              animate={{
                rotate: [0, 60, 120, 180, 240, 300, 360],
              }}
              transition={{
                duration: 1.5,
                repeat: Number.POSITIVE_INFINITY,
                ease: [0.25, 0.1, 0.25, 1],
              }}
            >
              {/* Mini stone hexagon */}
              <polygon
                points={Array.from({ length: 6 }, (_, i) => {
                  const angle = (Math.PI / 3) * i - Math.PI / 2
                  return `${9 + 7 * Math.cos(angle)},${9 + 7 * Math.sin(angle)}`
                }).join(" ")}
                fill="#b8a88a"
                stroke="#7a6b55"
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
              <circle cx="9" cy="9" r="2" fill="#6b5c48" stroke="#5a4d3b" strokeWidth="0.8" />
            </motion.svg>
          </motion.div>
        )}
      </div>
    </div>
  )
}
