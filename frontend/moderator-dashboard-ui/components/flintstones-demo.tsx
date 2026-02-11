"use client"

import { useState, useEffect } from "react"
import { FlinstonesWheel, FlinstonesProgressBar } from "./flintstones-wheel"

/**
 * Demo component showing how to use Flintstones Wheel components
 */
export function FlintstonesDemo() {
  const [progress, setProgress] = useState(0)
  const [isRunning, setIsRunning] = useState(false)

  useEffect(() => {
    if (isRunning && progress < 100) {
      const timer = setTimeout(() => {
        setProgress(prev => Math.min(100, prev + Math.random() * 15))
      }, 800)
      return () => clearTimeout(timer)
    } else if (progress >= 100) {
      setIsRunning(false)
    }
  }, [progress, isRunning])

  const handleStart = () => {
    setProgress(0)
    setIsRunning(true)
  }

  const handleReset = () => {
    setProgress(0)
    setIsRunning(false)
  }

  return (
    <div className="p-8 space-y-8 bg-stone-50 rounded-lg border border-stone-200">
      <div>
        <h3 className="text-lg font-semibold text-stone-800 mb-4">Flintstones Wheel Demo</h3>
        
        {/* Controls */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={handleStart}
            disabled={isRunning}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            Start Progress
          </button>
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-stone-500 text-white rounded hover:bg-stone-600"
          >
            Reset
          </button>
        </div>

        {/* Grid of different wheel configurations */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Basic wheel */}
          <div className="flex flex-col items-center space-y-4">
            <FlinstonesWheel 
              progress={progress} 
              size={80}
              label="Parsing"
              sublabel={`${Math.round(progress)}%`}
              isActive={isRunning}
            />
          </div>

          {/* Completed wheel */}
          <div className="flex flex-col items-center space-y-4">
            <FlinstonesWheel 
              progress={100} 
              size={80}
              label="Completed"
              sublabel="Done!"
              isActive={false}
            />
          </div>

          {/* Small wheel */}
          <div className="flex flex-col items-center space-y-4">
            <FlinstonesWheel 
              progress={progress} 
              size={48}
              label="Mini"
              isActive={isRunning}
            />
          </div>
        </div>

        {/* Progress bars with wheels */}
        <div className="space-y-4">
          <h4 className="text-md font-medium text-stone-700">Progress Bars with Wheels</h4>
          
          <FlinstonesProgressBar
            progress={progress}
            label="Domain Processing"
            color="blue"
            current={Math.round(progress * 0.27)}
            total={27}
          />

          <FlinstonesProgressBar
            progress={Math.min(100, progress * 1.2)}
            label="Supplier Extraction"
            color="emerald"
          />

          <FlinstonesProgressBar
            progress={Math.min(100, progress * 0.8)}
            label="Error Handling"
            color="red"
          />
        </div>
      </div>
    </div>
  )
}
