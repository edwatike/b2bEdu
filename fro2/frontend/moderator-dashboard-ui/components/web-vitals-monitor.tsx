// Web Vitals monitoring component
"use client"

import { useEffect, useState } from "react"
import type { Metric } from "web-vitals"

interface WebVitalsMetrics {
  lcp?: number
  cls?: number
  fcp?: number
  ttfb?: number
  inp?: number
}

export function WebVitalsMonitor() {
  const [metrics, setMetrics] = useState<WebVitalsMetrics>({})
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    // Only load web-vitals in development or when explicitly enabled
    const env = (globalThis as { process?: { env?: { NODE_ENV?: string; NEXT_PUBLIC_ENABLE_VITALS?: string } } }).process?.env
    if (env?.NODE_ENV === "development" || env?.NEXT_PUBLIC_ENABLE_VITALS === "true") {
      import("web-vitals").then(({ onCLS, onFCP, onLCP, onTTFB, onINP }) => {
        const handleMetric = (name: keyof WebVitalsMetrics) => (metric: Metric) => {
          setMetrics((prev: WebVitalsMetrics) => ({ ...prev, [name]: metric.value }))
          console.log(`${name.toUpperCase()}:`, metric)
        }

        onCLS(handleMetric("cls"))
        onFCP(handleMetric("fcp"))
        onLCP(handleMetric("lcp"))
        onTTFB(handleMetric("ttfb"))
        onINP(handleMetric("inp"))
      })
    }
  }, [])

  // Toggle visibility with Ctrl+Shift+V
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "V") {
        setIsVisible((prev: boolean) => !prev)
      }
    }

    window.addEventListener("keydown", handleKeyPress)
    return () => window.removeEventListener("keydown", handleKeyPress)
  }, [])

  if (!isVisible || Object.keys(metrics).length === 0) {
    return null
  }

  const formatMetric = (value: number, unit: string) => {
    return `${value.toFixed(2)}${unit}`
  }

  const getMetricColor = (metric: keyof WebVitalsMetrics) => {
    const value = metrics[metric]
    if (!value) return "text-gray-500"

    switch (metric) {
      case "lcp":
        return value <= 2500 ? "text-green-600" : value <= 4000 ? "text-yellow-600" : "text-red-600"
      case "inp":
        return value <= 100 ? "text-green-600" : value <= 300 ? "text-yellow-600" : "text-red-600"
      case "cls":
        return value <= 0.1 ? "text-green-600" : value <= 0.25 ? "text-yellow-600" : "text-red-600"
      case "fcp":
        return value <= 1800 ? "text-green-600" : value <= 3000 ? "text-yellow-600" : "text-red-600"
      case "ttfb":
        return value <= 800 ? "text-green-600" : value <= 1800 ? "text-yellow-600" : "text-red-600"
      default:
        return "text-gray-500"
    }
  }

  return (
    <div className="fixed top-4 right-4 bg-black/90 text-white p-4 rounded-lg shadow-lg z-50 font-mono text-sm max-w-xs">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-xs font-bold uppercase tracking-wider">Web Vitals</h3>
        <button
          onClick={() => setIsVisible(false)}
          className="text-gray-400 hover:text-white ml-2"
        >
          ✕
        </button>
      </div>
      
      <div className="space-y-1">
        {metrics.lcp !== undefined && (
          <div className="flex justify-between">
            <span>LCP:</span>
            <span className={getMetricColor("lcp")}>
              {formatMetric(metrics.lcp, "ms")}
            </span>
          </div>
        )}
        
        {metrics.cls !== undefined && (
          <div className="flex justify-between">
            <span>CLS:</span>
            <span className={getMetricColor("cls")}>
              {formatMetric(metrics.cls, "")}
            </span>
          </div>
        )}
        
        {metrics.fcp !== undefined && (
          <div className="flex justify-between">
            <span>FCP:</span>
            <span className={getMetricColor("fcp")}>
              {formatMetric(metrics.fcp, "ms")}
            </span>
          </div>
        )}
        
        {metrics.ttfb !== undefined && (
          <div className="flex justify-between">
            <span>TTFB:</span>
            <span className={getMetricColor("ttfb")}>
              {formatMetric(metrics.ttfb, "ms")}
            </span>
          </div>
        )}
        
        {metrics.inp !== undefined && (
          <div className="flex justify-between">
            <span>INP:</span>
            <span className={getMetricColor("inp")}>
              {formatMetric(metrics.inp, "ms")}
            </span>
          </div>
        )}
      </div>
      
      <div className="text-xs text-gray-400 mt-2 pt-2 border-t border-gray-700">
        Press Ctrl+Shift+V to toggle
      </div>
    </div>
  )
}
