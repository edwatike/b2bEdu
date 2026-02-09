# Деплой B2B Platform на b2bedu.ru

## Обзор

Сайт доступен по адресу **https://b2bedu.ru** через Cloudflare Tunnel.
Tunnel проксирует трафик из интернета к локальному Next.js серверу на `localhost:3000`.

## Требования

- **B2BLauncher.exe** — запускает все сервисы (parser, backend, frontend, CDP, tunnel)
- **cloudflared.exe** — в корне проекта `D:\b2b\cloudflared.exe`
- **Cloudflare Tunnel config** — `D:\b2b\cloudflared-b2bedu.yml`
- **Cloudflare credentials** — `C:\Users\admin\.cloudflared\a172616c-c11b-4833-bdc1-3baacada6f16.json`

## Запуск

1. Запустите `B2BLauncher.exe`
2. Выберите режим:
   - **1 — Локальный** — сервер доступен только на `localhost:3000`
   - **2 — Продакшн (b2bedu.ru)** — сервер доступен на `https://b2bedu.ru`
3. В продакшн режиме лаунчер автоматически запускает Cloudflare Tunnel

## ⚠ Важно: VPN/Proxy

**Cloudflare Tunnel НЕ работает стабильно при активном VPN (Hiddify, sing-box и т.п.).**

При запуске в продакшн режиме лаунчер автоматически проверяет наличие VPN/TUN адаптера
и предупреждает пользователя. Рекомендация:

1. **Отключите VPN** перед запуском продакшн режима
2. Запустите `B2BLauncher.exe` → выберите "2 — Продакшн"
3. Дождитесь сообщения "Tunnel connected" в дашборде
4. Проверьте https://b2bedu.ru в браузере
5. После завершения работы можете включить VPN обратно

### Техническая причина

sing-box TUN адаптер (`happ-tun`) перехватывает весь сетевой трафик, включая
HTTP/2 long-lived connections cloudflared к Cloudflare edge. Это приводит к:
- Нестабильным connections (обрыв через ~30 секунд)
- DNS timeout для внутренних Cloudflare доменов
- 502 Bad Gateway ошибкам

Bypass по `process_name` в sing-box config помогает установить connections,
но не обеспечивает стабильность long-lived HTTP/2 соединений.

## Конфигурация

### cloudflared-b2bedu.yml
```yaml
tunnel: a172616c-c11b-4833-bdc1-3baacada6f16
credentials-file: C:\Users\admin\.cloudflared\a172616c-c11b-4833-bdc1-3baacada6f16.json
protocol: http2
ingress:
  - hostname: b2bedu.ru
    service: http://localhost:3000
  - hostname: www.b2bedu.ru
    service: http://localhost:3000
  - service: http_status:404
```

### Cloudflare DNS
- `b2bedu.ru` → CNAME → `a172616c-c11b-4833-bdc1-3baacada6f16.cfargotunnel.com`
- `www.b2bedu.ru` → CNAME → `a172616c-c11b-4833-bdc1-3baacada6f16.cfargotunnel.com`

### sing-box bypass (уже добавлен)
В `C:\Users\admin\AppData\Local\Happ\config.json` добавлен bypass для cloudflared:
```json
{
    "process_name": ["cloudflared.exe", "cloudflared-new.exe", "cloudflared", "cloudflared-new"],
    "outbound": "direct-wifi"
}
```

## CLI режим

```bash
B2BLauncher.exe --mode production
B2BLauncher.exe --mode local
```
