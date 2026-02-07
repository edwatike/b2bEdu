'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle, XCircle, Loader2, RefreshCw, AlertCircle } from 'lucide-react'

interface TestResult {
  name: string
  status: 'idle' | 'loading' | 'success' | 'error'
  message: string
  responseTime?: number
}

export default function TestNgrokPage() {
  const [results, setResults] = useState<TestResult[]>([
    { name: 'Health Check', status: 'idle', message: 'Не проверено' },
    { name: 'Auth Status', status: 'idle', message: 'Не проверено' },
    { name: 'Yandex Config', status: 'idle', message: 'Не проверено' },
    { name: 'Suppliers List', status: 'idle', message: 'Не проверено' },
  ])
  const [apiUrl, setApiUrl] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8010'
    setApiUrl(url)
  }, [])

  const testHealth = async () => {
    const startTime = Date.now()
    try {
      const response = await fetch(`${apiUrl}/health`, {
        headers: { 'ngrok-skip-browser-warning': 'true' },
      })
      const responseTime = Date.now() - startTime
      const data = await response.json()
      
      setResults(prev => prev.map(r => 
        r.name === 'Health Check' 
          ? { ...r, status: response.ok ? 'success' : 'error', message: JSON.stringify(data), responseTime }
          : r
      ))
    } catch (error) {
      const responseTime = Date.now() - startTime
      setResults(prev => prev.map(r => 
        r.name === 'Health Check' 
          ? { ...r, status: 'error', message: error instanceof Error ? error.message : 'Неизвестная ошибка', responseTime }
          : r
      ))
    }
  }

  const testAuthStatus = async () => {
    const startTime = Date.now()
    try {
      const response = await fetch(`${apiUrl}/api/auth/status`, {
        headers: { 'ngrok-skip-browser-warning': 'true' },
      })
      const responseTime = Date.now() - startTime
      const data = await response.json()
      
      setResults(prev => prev.map(r => 
        r.name === 'Auth Status' 
          ? { ...r, status: response.ok ? 'success' : 'error', message: JSON.stringify(data), responseTime }
          : r
      ))
    } catch (error) {
      const responseTime = Date.now() - startTime
      setResults(prev => prev.map(r => 
        r.name === 'Auth Status' 
          ? { ...r, status: 'error', message: error instanceof Error ? error.message : 'Неизвестная ошибка', responseTime }
          : r
      ))
    }
  }

  const testYandexConfig = async () => {
    const startTime = Date.now()
    try {
      const response = await fetch(`/api/yandex/config`)
      const responseTime = Date.now() - startTime
      const data = await response.json()
      
      setResults(prev => prev.map(r => 
        r.name === 'Yandex Config' 
          ? { ...r, status: response.ok ? 'success' : 'error', message: JSON.stringify(data), responseTime }
          : r
      ))
    } catch (error) {
      const responseTime = Date.now() - startTime
      setResults(prev => prev.map(r => 
        r.name === 'Yandex Config' 
          ? { ...r, status: 'error', message: error instanceof Error ? error.message : 'Неизвестная ошибка', responseTime }
          : r
      ))
    }
  }

  const testSuppliers = async () => {
    const startTime = Date.now()
    try {
      const response = await fetch(`${apiUrl}/api/suppliers`, {
        headers: { 'ngrok-skip-browser-warning': 'true' },
      })
      const responseTime = Date.now() - startTime
      const data = await response.json()
      
      setResults(prev => prev.map(r => 
        r.name === 'Suppliers List' 
          ? { ...r, status: response.ok ? 'success' : 'error', message: `Найдено поставщиков: ${Array.isArray(data) ? data.length : 0}`, responseTime }
          : r
      ))
    } catch (error) {
      const responseTime = Date.now() - startTime
      setResults(prev => prev.map(r => 
        r.name === 'Suppliers List' 
          ? { ...r, status: 'error', message: error instanceof Error ? error.message : 'Неизвестная ошибка', responseTime }
          : r
      ))
    }
  }

  const runAllTests = async () => {
    setLoading(true)
    setResults(prev => prev.map(r => ({ ...r, status: 'loading', message: 'Проверка...' })))
    
    await testHealth()
    await testAuthStatus()
    await testYandexConfig()
    await testSuppliers()
    
    setLoading(false)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-5 w-5 text-emerald-400" />
      case 'error':
        return <XCircle className="h-5 w-5 text-red-400" />
      case 'loading':
        return <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
      default:
        return <AlertCircle className="h-5 w-5 text-slate-400" />
    }
  }

  const allSuccess = results.every(r => r.status === 'success')

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-8">
      <div className="max-w-2xl mx-auto">
        <Card className="bg-white/5 backdrop-blur-xl border-white/10">
          <CardHeader>
            <CardTitle className="text-2xl">Проверка подключения к Backend</CardTitle>
            <CardDescription>Тестирование ngrok подключения</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Backend URL */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">Backend URL:</label>
              <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-700 text-sm font-mono text-blue-400">
                {apiUrl}
              </div>
            </div>

            {/* Status */}
            <div className={`p-4 rounded-lg ${allSuccess ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-slate-900/50 border border-slate-700'}`}>
              <div className="flex items-center gap-2 text-sm">
                {allSuccess ? (
                  <>
                    <CheckCircle className="h-5 w-5 text-emerald-400" />
                    <span className="text-emerald-400 font-medium">Все системы работают!</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-5 w-5 text-slate-400" />
                    <span className="text-slate-400">Запустите тесты для проверки</span>
                  </>
                )}
              </div>
            </div>

            {/* Test Results */}
            <div className="space-y-3">
              {results.map((result) => (
                <div key={result.name} className="p-4 rounded-lg bg-slate-900/50 border border-slate-700 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(result.status)}
                      <span className="font-medium text-slate-200">{result.name}</span>
                    </div>
                    {result.responseTime && (
                      <span className="text-xs text-slate-400">{result.responseTime}ms</span>
                    )}
                  </div>
                  <div className="text-sm text-slate-400 break-all">
                    {result.message}
                  </div>
                </div>
              ))}
            </div>

            {/* Buttons */}
            <div className="flex flex-col gap-2">
              <Button
                onClick={runAllTests}
                disabled={loading}
                className="w-full h-10 bg-blue-600 hover:bg-blue-700 text-white font-medium"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Проверка...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Запустить все тесты
                  </>
                )}
              </Button>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={testHealth}
                  disabled={loading}
                  variant="outline"
                  className="h-9"
                >
                  Health
                </Button>
                <Button
                  onClick={testAuthStatus}
                  disabled={loading}
                  variant="outline"
                  className="h-9"
                >
                  Auth
                </Button>
                <Button
                  onClick={testYandexConfig}
                  disabled={loading}
                  variant="outline"
                  className="h-9"
                >
                  Yandex
                </Button>
                <Button
                  onClick={testSuppliers}
                  disabled={loading}
                  variant="outline"
                  className="h-9"
                >
                  Suppliers
                </Button>
              </div>
            </div>

            {/* Info */}
            <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <p className="text-xs text-blue-300 space-y-1">
                <div>✓ Backend URL берется из переменной окружения NEXT_PUBLIC_API_URL</div>
                <div>✓ Автоматически добавляется заголовок ngrok-skip-browser-warning</div>
                <div>✓ Все запросы проходят через CSP политику</div>
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
