'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle, AlertCircle, RefreshCw, Server } from 'lucide-react'
import Link from 'next/link'

export default function SettingsAPIPage() {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  const [mockEnabled, setMockEnabled] = useState(false)
  const [fallbackEnabled, setFallbackEnabled] = useState(true)

  useEffect(() => {
    checkBackendStatus()
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
    console.log('[v0] Backend URL:', backendUrl)
  }, [])

  const checkBackendStatus = async () => {
    try {
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
      const response = await fetch(`${backendUrl}/health`, {
        headers: {
          'ngrok-skip-browser-warning': 'true',
        },
      })
      setBackendStatus(response.ok ? 'online' : 'offline')
    } catch (error) {
      setBackendStatus('offline')
    }
  }

  const handleToggleMockMode = () => {
    const newValue = !mockEnabled
    if (newValue) {
      localStorage.setItem('NEXT_PUBLIC_USE_MOCK_DATA', 'true')
    } else {
      localStorage.removeItem('NEXT_PUBLIC_USE_MOCK_DATA')
    }
    setMockEnabled(newValue)
    // Перезагружаем страницу
    setTimeout(() => window.location.reload(), 500)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4 sm:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Заголовок */}
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold text-white mb-2">Настройки API</h1>
          <p className="text-slate-400">Управление подключением к backend и режимом работы</p>
        </div>

        {/* Статус Backend */}
        <Card className="bg-white/5 backdrop-blur-xl border-white/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Статус Backend
            </CardTitle>
            <CardDescription>Проверка доступности сервера</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10">
              <div className="flex items-center gap-3">
                {backendStatus === 'checking' && (
                  <RefreshCw className="h-5 w-5 text-yellow-400 animate-spin" />
                )}
                {backendStatus === 'online' && <CheckCircle className="h-5 w-5 text-emerald-400" />}
                {backendStatus === 'offline' && <AlertCircle className="h-5 w-5 text-red-400" />}
                <div>
                  <p className="font-medium text-white">
                    {backendStatus === 'checking' && 'Проверка...'}
                    {backendStatus === 'online' && 'Backend в сети'}
                    {backendStatus === 'offline' && 'Backend недоступен'}
                  </p>
                  <p className="text-xs text-slate-400">{process.env.NEXT_PUBLIC_API_URL}</p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setBackendStatus('checking')
                  checkBackendStatus()
                }}
              >
                Обновить
              </Button>
            </div>

            {backendStatus === 'offline' && (
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20">
                <p className="text-sm text-red-400">
                  <strong>Backend недоступен!</strong> Но не волнуйтесь - система работает с fallback данными.
                </p>
              </div>
            )}

            {backendStatus === 'online' && (
              <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <p className="text-sm text-emerald-400">
                  Backend доступен. Система использует реальные данные.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Режимы работы */}
        <Card className="bg-white/5 backdrop-blur-xl border-white/10">
          <CardHeader>
            <CardTitle>Режимы работы</CardTitle>
            <CardDescription>Переключение между real API и mock данными</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Mock режим */}
            <div className="p-4 rounded-lg bg-white/5 border border-white/10 flex items-center justify-between">
              <div>
                <p className="font-medium text-white">Mock режим</p>
                <p className="text-sm text-slate-400">Использовать локальные тестовые данные</p>
              </div>
              <Button
                onClick={handleToggleMockMode}
                variant={mockEnabled ? 'default' : 'outline'}
              >
                {mockEnabled ? 'Выключить' : 'Включить'}
              </Button>
            </div>

            {/* Fallback режим */}
            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-medium text-white">Fallback режим</p>
                  <p className="text-sm text-slate-400">Автоматическое переключение на mock при ошибке backend</p>
                </div>
                <CheckCircle className="h-5 w-5 text-emerald-400" />
              </div>
              <p className="text-xs text-slate-400">
                Fallback режим <strong>всегда включен</strong> - система автоматически переключается на mock данные, если backend недоступен.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Информация */}
        <Card className="bg-white/5 backdrop-blur-xl border-white/10">
          <CardHeader>
            <CardTitle>Как это работает</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-300">
            <div>
              <p className="font-medium text-white mb-1">🔄 Fallback режим (активен всегда):</p>
              <p>Система пытается получить данные от backend. Если backend недоступен, автоматически использует mock данные.</p>
            </div>
            <div>
              <p className="font-medium text-white mb-1">🎭 Mock режим (опционально):</p>
              <p>При включении всегда использует локальные тестовые данные, игнорируя backend.</p>
            </div>
            <div>
              <p className="font-medium text-white mb-1">✅ Текущий статус:</p>
              <p>
                Backend: <strong>{backendStatus === 'online' ? 'Доступен' : 'Недоступен'}</strong>
                <br />
                Mock режим: <strong>{mockEnabled ? 'Включен' : 'Отключен'}</strong>
                <br />
                Fallback режим: <strong>Включен (всегда)</strong>
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Кнопка назад */}
        <div className="flex gap-3">
          <Link href="/moderator" className="flex-1">
            <Button className="w-full" variant="outline">
              Вернуться в модератор
            </Button>
          </Link>
          <Link href="/cabinet" className="flex-1">
            <Button className="w-full" variant="outline">
              Вернуться в кабинет
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
