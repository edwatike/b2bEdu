"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Время жизни кэшированных данных в мс
            staleTime: 1000 * 60 * 5, // 5 минут
            // Время повторной попытки при ошибке
            retry: 1,
            // Рефетч на фокусе окна
            refetchOnWindowFocus: false,
            // Рефетч на reconnect
            refetchOnReconnect: true,
          },
          mutations: {
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  )
}
