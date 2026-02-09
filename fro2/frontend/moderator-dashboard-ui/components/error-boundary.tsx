/**
 * ErrorBoundary Component
 * 
 * Обработка ошибок на уровне компонентов
 * Предотвращает падение всего приложения при ошибках в отдельных компонентах
 */

"use client"

import React, { Component, ReactNode } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-red-50/30 flex items-center justify-center p-6">
          <Card className="max-w-lg w-full border-red-200">
            <CardHeader>
              <div className="flex items-center gap-3 mb-2">
                <div className="h-12 w-12 rounded-full bg-red-100 flex items-center justify-center">
                  <AlertTriangle className="h-6 w-6 text-red-600" />
                </div>
                <CardTitle className="text-2xl text-red-900">
                  Произошла ошибка
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm font-medium text-red-900 mb-2">
                  Детали ошибки:
                </p>
                <p className="text-sm text-red-700 font-mono">
                  {this.state.error?.message || "Неизвестная ошибка"}
                </p>
              </div>

              <div className="space-y-2">
                <p className="text-sm text-neutral-600">
                  Попробуйте перезагрузить компонент или обновить страницу.
                </p>
                <p className="text-sm text-neutral-600">
                  Если ошибка повторяется, обратитесь к администратору.
                </p>
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={this.handleReset}
                  className="flex-1 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700"
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Попробовать снова
                </Button>
                <Button
                  variant="outline"
                  onClick={() => window.location.reload()}
                  className="flex-1"
                >
                  Обновить страницу
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}
