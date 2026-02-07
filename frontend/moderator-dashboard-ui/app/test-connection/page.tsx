"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CheckCircle2, XCircle, Loader2, RefreshCw } from "lucide-react"

interface TestResult {
  endpoint: string
  status: "success" | "error" | "loading"
  message: string
  data?: any
  responseTime?: number
}

export default function TestConnectionPage() {
  const [results, setResults] = useState<TestResult[]>([])
  const [isTestingAll, setIsTestingAll] = useState(false)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://hobnailed-ballistically-jolie.ngrok-free.dev"

  const endpoints = [
    { path: "/health", method: "GET", label: "Health Check" },
    { path: "/api/auth/status", method: "GET", label: "Auth Status" },
    { path: "/api/auth/me", method: "GET", label: "Auth Me" },
    { path: "/api/suppliers", method: "GET", label: "Suppliers" },
  ]

  const testEndpoint = async (endpoint: { path: string; method: string; label: string }) => {
    const startTime = Date.now()
    
    try {
      const response = await fetch(`${API_URL}${endpoint.path}`, {
        method: endpoint.method,
        headers: {
          "ngrok-skip-browser-warning": "true",
          "Content-Type": "application/json",
        },
        credentials: "include",
      })

      const responseTime = Date.now() - startTime
      const data = await response.json().catch(() => null)

      if (response.ok) {
        return {
          endpoint: endpoint.label,
          status: "success" as const,
          message: `${response.status} OK`,
          data,
          responseTime,
        }
      } else {
        return {
          endpoint: endpoint.label,
          status: "error" as const,
          message: `${response.status} ${response.statusText}`,
          data,
          responseTime,
        }
      }
    } catch (error) {
      const responseTime = Date.now() - startTime
      return {
        endpoint: endpoint.label,
        status: "error" as const,
        message: error instanceof Error ? error.message : "Unknown error",
        responseTime,
      }
    }
  }

  const testAllEndpoints = async () => {
    setIsTestingAll(true)
    setResults([])

    for (const endpoint of endpoints) {
      setResults((prev) => [
        ...prev,
        {
          endpoint: endpoint.label,
          status: "loading",
          message: "Testing...",
        },
      ])

      const result = await testEndpoint(endpoint)

      setResults((prev) =>
        prev.map((r) => (r.endpoint === endpoint.label ? result : r))
      )
    }

    setIsTestingAll(false)
  }

  useEffect(() => {
    testAllEndpoints()
  }, [])

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold">Backend Connection Test</h1>
          <p className="text-muted-foreground">
            Testing connection to FastAPI backend via ngrok
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>API Configuration</CardTitle>
                <CardDescription>Current backend URL</CardDescription>
              </div>
              <Button onClick={testAllEndpoints} disabled={isTestingAll}>
                {isTestingAll ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Test All
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg bg-muted p-4">
              <code className="text-sm">{API_URL}</code>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <h2 className="text-2xl font-semibold">Endpoint Tests</h2>
          {results.map((result) => (
            <Card key={result.endpoint}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{result.endpoint}</CardTitle>
                  {result.status === "loading" && (
                    <Badge variant="outline" className="gap-1">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Testing
                    </Badge>
                  )}
                  {result.status === "success" && (
                    <Badge variant="default" className="gap-1 bg-green-600">
                      <CheckCircle2 className="h-3 w-3" />
                      Success
                    </Badge>
                  )}
                  {result.status === "error" && (
                    <Badge variant="destructive" className="gap-1">
                      <XCircle className="h-3 w-3" />
                      Failed
                    </Badge>
                  )}
                </div>
                <CardDescription>{result.message}</CardDescription>
                {result.responseTime && (
                  <p className="text-xs text-muted-foreground">
                    Response time: {result.responseTime}ms
                  </p>
                )}
              </CardHeader>
              {result.data && (
                <CardContent>
                  <div className="rounded-lg bg-muted p-4">
                    <pre className="overflow-auto text-xs">
                      {JSON.stringify(result.data, null, 2)}
                    </pre>
                  </div>
                </CardContent>
              )}
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Configuration Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h3 className="mb-2 font-semibold">Endpoints Being Tested:</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {endpoints.map((endpoint) => (
                  <li key={endpoint.path}>
                    <code>
                      {endpoint.method} {endpoint.path}
                    </code>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-2 font-semibold">Headers:</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                <li>
                  <code>ngrok-skip-browser-warning: true</code>
                </li>
                <li>
                  <code>Content-Type: application/json</code>
                </li>
                <li>
                  <code>credentials: include</code>
                </li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
