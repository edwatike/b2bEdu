"use client"

import dynamic from "next/dynamic"
import { Loader2 } from "lucide-react"

const ChartSectionImpl = dynamic(
  () => import("../supplier-card").then((mod) => ({ default: (mod as any).ChartSection })),
  {
    loading: () => (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    ),
    ssr: false,
  }
)

export function ChartSection(props: any) {
  return <ChartSectionImpl {...props} />
}
