// Утилиты для работы с доменами

/**
 * Нормализует URL для сравнения (убирает протокол, www, trailing slash, параметры)
 * @param url URL для нормализации
 * @returns Нормализованный URL в нижнем регистре
 */
export function normalizeUrl(url: string): string {
  try {
    // Убираем протокол
    let normalized = url.replace(/^https?:\/\//i, "")
    // Убираем www
    normalized = normalized.replace(/^www\./i, "")
    // Убираем trailing slash
    normalized = normalized.replace(/\/$/, "")
    // Убираем параметры (все после # или ?)
    normalized = normalized.split("#")[0].split("?")[0]
    // Приводим к нижнему регистру
    return normalized.toLowerCase()
  } catch {
    return url.toLowerCase()
  }
}

export function extractRootDomain(url: string): string {
  try {
    // Убираем протокол
    let domain = url.replace(/^https?:\/\//, "").replace(/^www\./, "")

    // Берем только доменную часть (до первого /)
    domain = domain.split("/")[0]

    // Разбиваем на части
    const parts = domain.split(".")

    // Берем root domain:
    // - если 2 части или меньше: это уже root domain
    // - иначе: последние 2 части (example.com)
    let root = parts.length <= 2 ? domain : parts.slice(-2).join(".")

    // Нормализуем региональные суффиксы (kraska-spb.ru -> kraska.ru)
    root = root.replace(/^(.*?)-(spb|ekb)\./i, "$1.")

    return root
  } catch {
    return url
  }
}

export function groupByDomain(
  entries: Array<{
    domain: string
    url: string
    keyword: string
    source?: string | null
    status: string
    createdAt: string
  }>,
): Array<{
  domain: string
  urls: Array<{ url: string; keyword: string; source?: string | null; status: string; createdAt: string }>
  totalUrls: number
}> {
  const groups = new Map<
    string,
    {
      domain: string
      urls: Array<{ url: string; keyword: string; source?: string | null; status: string; createdAt: string }>
      totalUrls: number
    }
  >()

  for (const entry of entries) {
    // Нормализуем домен для группировки (toLowerCase) чтобы избежать дублирования
    const rootDomain = extractRootDomain(entry.domain).toLowerCase()
    const displayDomain = extractRootDomain(entry.domain) // Оригинальный домен для отображения

    if (!groups.has(rootDomain)) {
      groups.set(rootDomain, {
        domain: displayDomain, // Используем оригинальный домен для отображения
        urls: [],
        totalUrls: 0,
      })
    }

    const group = groups.get(rootDomain)!
    group.urls.push({
      url: entry.url,
      keyword: entry.keyword,
      source: entry.source,
      status: entry.status,
      createdAt: entry.createdAt,
    })
    group.totalUrls++
  }

  return Array.from(groups.values())
}

/**
 * Собирает уникальные источники для домена из всех его URL.
 * 
 * Если передан parsingLogs, использует его для определения источников каждого URL
 * (проверяет, есть ли URL в parsingLogs.google.last_links или parsingLogs.yandex.last_links).
 * 
 * Если parsingLogs не передан, использует source из базы данных (fallback).
 * 
 * @param urls Массив URL с информацией об источниках
 * @param parsingLogs Опциональные логи парсинга для точного определения источников
 * @returns Массив уникальных источников (google, yandex)
 */
export function collectDomainSources(
  urls: Array<{ url: string; source?: string | null }>,
  parsingLogs?: {
    google?: { last_links: string[] }
    yandex?: { last_links: string[] }
  } | null
): string[] {
  const sources = new Set<string>()

  for (const urlEntry of urls) {
    const normalizedUrl = normalizeUrl(urlEntry.url)

    if (parsingLogs?.google?.last_links) {
      const foundInGoogle = parsingLogs.google.last_links.some((link) => normalizeUrl(link) === normalizedUrl)
      if (foundInGoogle) {
        sources.add("google")
      }
    }

    if (parsingLogs?.yandex?.last_links) {
      const foundInYandex = parsingLogs.yandex.last_links.some((link) => normalizeUrl(link) === normalizedUrl)
      if (foundInYandex) {
        sources.add("yandex")
      }
    }

    // Всегда используем source из базы данных как fallback, чтобы не терять бейджи
    if (urlEntry.source === "both") {
      sources.add("google")
      sources.add("yandex")
    } else if (urlEntry.source === "google") {
      sources.add("google")
    } else if (urlEntry.source === "yandex") {
      sources.add("yandex")
    }
  }

  // Возвращаем отсортированный массив источников
  return Array.from(sources).sort()
}

export function getLatestUrlCreatedAt(
  urls: Array<{ createdAt?: string | null }>
): string | null {
  if (!urls || urls.length === 0) return null
  let latest: string | null = null
  for (const item of urls) {
    const value = item?.createdAt || null
    if (!value) continue
    if (!latest) {
      latest = value
      continue
    }
    const latestTime = new Date(latest).getTime()
    const valueTime = new Date(value).getTime()
    if (!Number.isNaN(valueTime) && (Number.isNaN(latestTime) || valueTime > latestTime)) {
      latest = value
    }
  }
  return latest
}
