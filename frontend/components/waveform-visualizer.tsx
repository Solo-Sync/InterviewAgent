"use client"

import { useEffect, useState } from "react"

interface WaveformVisualizerProps {
  isActive: boolean
}

export function WaveformVisualizer({ isActive }: WaveformVisualizerProps) {
  const [bars, setBars] = useState<number[]>(Array(24).fill(20))

  useEffect(() => {
    if (!isActive) {
      setBars(Array(24).fill(20))
      return
    }

    const interval = setInterval(() => {
      setBars((prev) =>
        prev.map(() => Math.random() * 80 + 20)
      )
    }, 80)

    return () => clearInterval(interval)
  }, [isActive])

  return (
    <div className="flex h-12 items-end justify-center gap-[3px]">
      {bars.map((height, i) => (
        <div
          key={i}
          className="w-1 rounded-full bg-destructive/80 transition-all duration-75"
          style={{
            height: `${isActive ? height : 20}%`,
            opacity: isActive ? 0.6 + (height / 100) * 0.4 : 0.3,
          }}
        />
      ))}
    </div>
  )
}
