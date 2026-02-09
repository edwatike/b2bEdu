"use server"

export async function handleStartParsing(formData: FormData) {
  const keyword = formData.get("keyword") as string
  const depth = Number.parseInt(formData.get("depth") as string) || 3
  const source = (formData.get("source") as string) || "both"

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

  console.log("🚀 SERVER ACTION: handleStartParsing вызван")
  console.log("📝 Данные формы:", { keyword, depth, source })
  console.log("🌐 API URL:", API_BASE_URL)

  if (!keyword?.trim()) {
    console.log("❌ Ошибка: Пустое ключевое слово")
    throw new Error("Введите ключевое слово")
  }

  if (depth < 1 || depth > 100) {
    console.log("❌ Ошибка: Некорректная глубина:", depth)
    throw new Error("Глубина должна быть от 1 до 100")
  }

  try {
    console.log("🌡️ Отправка запроса к Backend API...")

    const response = await fetch(`${API_BASE_URL}/parsing/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
      },
      body: JSON.stringify({
        keyword: keyword.trim(),
        depth,
        source: source as "google" | "yandex" | "both",
      }),
    })

    console.log("📡 Ответ Backend API:", response.status)

    if (!response.ok) {
      const errorText = await response.text()
      console.log("❌ Ошибка Backend API:", response.status, errorText)
      throw new Error(`Backend error: ${response.status} - ${errorText}`)
    }

    const result = await response.json()
    const runId = result.runId || result.run_id || ""

    console.log("✅ Парсинг успешно запущен!")
    console.log("🔑 RunId:", runId)
    console.log("🔍 Ключевое слово:", keyword.trim())

    return { success: true, runId, keyword: keyword.trim() }
  } catch (error) {
    console.error("❌ Ошибка запуска парсинга:", error)
    throw new Error("Ошибка запуска парсинга")
  }
}
