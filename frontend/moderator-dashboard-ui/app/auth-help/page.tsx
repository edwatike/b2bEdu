"use client"

import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowLeft, CheckCircle2, Lock, Mail, Key, Users } from "lucide-react"
import Link from "next/link"

export default function AuthHelpPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Кнопка назад */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6"
        >
          <Link href="/login">
            <Button variant="ghost" className="text-slate-400 hover:text-white">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Назад к входу
            </Button>
          </Link>
        </motion.div>

        {/* Заголовок */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-center mb-10"
        >
          <h1 className="text-4xl font-bold text-white mb-3">🔐 Помощь по авторизации</h1>
          <p className="text-slate-400 text-lg">Как войти в систему управления поставщиками</p>
        </motion.div>

        {/* Способы входа */}
        <div className="grid gap-6 mb-8">
          {/* Способ 1: Логин/Пароль */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Card className="bg-white/5 backdrop-blur-xl border-white/10">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-500/20">
                    <Lock className="h-6 w-6 text-blue-400" />
                  </div>
                  <div>
                    <CardTitle className="text-white">Способ 1: Логин и Пароль</CardTitle>
                    <CardDescription className="text-slate-400">Стандартный способ авторизации</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
                  <p className="text-sm text-slate-300 mb-3 font-semibold">Демо-доступ для тестирования:</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Логин:</p>
                      <code className="text-emerald-400 font-mono text-lg">admin</code>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Пароль:</p>
                      <code className="text-emerald-400 font-mono text-lg">admin123</code>
                    </div>
                  </div>
                </div>
                <div className="flex items-start gap-2 text-sm text-slate-400">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <span>Работает всегда, не требует дополнительных настроек</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Способ 2: Яндекс OAuth */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <Card className="bg-white/5 backdrop-blur-xl border-white/10">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-red-500/20">
                    <Mail className="h-6 w-6 text-red-400" />
                  </div>
                  <div>
                    <CardTitle className="text-white">Способ 2: Вход через Яндекс</CardTitle>
                    <CardDescription className="text-slate-400">Авторизация через Яндекс ID (опционально)</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-start gap-2 text-sm text-slate-400">
                    <CheckCircle2 className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <span>Быстрый вход без запоминания пароля</span>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-400">
                    <CheckCircle2 className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <span>Автоматическое создание аккаунта при первом входе</span>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-400">
                    <CheckCircle2 className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <span>Требует настройки OAuth приложения на oauth.yandex.ru</span>
                  </div>
                </div>
                
                <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                  <p className="text-xs text-yellow-400 mb-2 font-semibold">⚠️ Примечание:</p>
                  <p className="text-xs text-slate-400">
                    Кнопка "Войти через Яндекс" появится на странице входа только после настройки переменных окружения 
                    <code className="mx-1 text-yellow-400">YANDEX_CLIENT_ID</code> и 
                    <code className="ml-1 text-yellow-400">YANDEX_CLIENT_SECRET</code>
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Инструкция по настройке OAuth */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
          <Card className="bg-white/5 backdrop-blur-xl border-white/10">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-purple-500/20">
                  <Key className="h-6 w-6 text-purple-400" />
                </div>
                <div>
                  <CardTitle className="text-white">Настройка Яндекс OAuth</CardTitle>
                  <CardDescription className="text-slate-400">Шаги для включения авторизации через Яндекс</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ol className="space-y-4 text-slate-300">
                <li className="flex gap-3">
                  <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-semibold">
                    1
                  </span>
                  <div>
                    <p className="font-medium">Создайте приложение на Яндекс</p>
                    <p className="text-sm text-slate-400 mt-1">
                      Перейдите на{" "}
                      <a
                        href="https://oauth.yandex.ru/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:underline"
                      >
                        oauth.yandex.ru
                      </a>{" "}
                      и создайте новое приложение
                    </p>
                  </div>
                </li>

                <li className="flex gap-3">
                  <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-semibold">
                    2
                  </span>
                  <div>
                    <p className="font-medium">Укажите Callback URL</p>
                    <div className="mt-2 p-3 rounded bg-slate-800/50 border border-slate-700">
                      <code className="text-xs text-emerald-400 break-all">
                        https://hobnailed-ballistically-jolie.ngrok-free.dev/api/yandex/callback
                      </code>
                    </div>
                  </div>
                </li>

                <li className="flex gap-3">
                  <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-semibold">
                    3
                  </span>
                  <div>
                    <p className="font-medium">Настройте права доступа</p>
                    <p className="text-sm text-slate-400 mt-1">
                      Выберите: <code className="text-blue-400">login:email</code> и <code className="text-blue-400">login:info</code>
                    </p>
                  </div>
                </li>

                <li className="flex gap-3">
                  <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-semibold">
                    4
                  </span>
                  <div>
                    <p className="font-medium">Добавьте учетные данные в .env.local</p>
                    <div className="mt-2 p-3 rounded bg-slate-800/50 border border-slate-700">
                      <pre className="text-xs text-slate-300">
                        <code>{`YANDEX_CLIENT_ID=ваш_client_id
YANDEX_CLIENT_SECRET=ваш_client_secret`}</code>
                      </pre>
                    </div>
                  </div>
                </li>

                <li className="flex gap-3">
                  <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-semibold">
                    5
                  </span>
                  <div>
                    <p className="font-medium">Перезапустите приложение</p>
                    <p className="text-sm text-slate-400 mt-1">После изменения .env.local перезапустите Next.js</p>
                  </div>
                </li>
              </ol>

              <div className="mt-6 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <p className="text-sm text-blue-400 flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Подробная инструкция доступна в файле <code className="mx-1">YANDEX_OAUTH_SETUP.md</code>
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Кнопка возврата */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="mt-8 text-center"
        >
          <Link href="/login">
            <Button size="lg" className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700">
              Вернуться к входу
            </Button>
          </Link>
        </motion.div>
      </div>
    </div>
  )
}
