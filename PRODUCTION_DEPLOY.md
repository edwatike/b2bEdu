# 🚀 Развертывание в продакшене

## Готовность система к продакшену

✅ **Система готова к боевому развертыванию**

Это полное руководство по переводу приложения из разработки в продакшен.

---

## 📋 Чек-лист перед развертыванием

### 1. Frontend конфигурация

- [ ] Удалить `NEXT_PUBLIC_DEBUG=true` из `.env.local`
- [ ] Установить правильный `NEXT_PUBLIC_APP_VERSION`
- [ ] Обновить `NEXT_PUBLIC_ENVIRONMENT=production`
- [ ] Проверить все переменные окружения

### 2. Backend конфигурация

- [ ] Переключить на HTTPS (SSL сертификат)
- [ ] Обновить Content-Security-Policy
- [ ] Включить CORS для продакшен домена
- [ ] Настроить логирование для продакшена
- [ ] Проверить все API endpoints

### 3. Yandex OAuth

- [ ] Добавить новый Redirect URI в приложение на oauth.yandex.ru
- [ ] Обновить `YANDEX_REDIRECT_URI` в `.env` для продакшена
- [ ] Проверить scope прав
- [ ] Убедиться, что приложение опубликовано (не в draft)

### 4. Безопасность

- [ ] Включить HTTPS везде
- [ ] Установить флаг `secure` для cookies
- [ ] Проверить CORS headers
- [ ] Настроить rate limiting
- [ ] Включить логирование всех ошибок

### 5. Мониторинг и алерты

- [ ] Настроить мониторинг backend
- [ ] Настроить мониторинг frontend
- [ ] Настроить алерты при ошибках OAuth
- [ ] Настроить логирование в продакшене

---

## 🔧 Пошаговое развертывание

### Шаг 1: Подготовка кода

```bash
# Обновить зависимости
cd frontend/moderator-dashboard-ui
npm install
npm run build  # Проверить, что build успешен

cd ../../backend
pip install -r requirements.txt
```

### Шаг 2: Переменные окружения для продакшена

#### Frontend (`.env.production`)

```env
# Production Frontend
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_APP_NAME=B2B Platform
NEXT_PUBLIC_APP_VERSION=1.0.0
NEXT_PUBLIC_ENVIRONMENT=production
NEXT_PUBLIC_DEBUG=false

# Yandex OAuth для продакшена
YANDEX_CLIENT_ID=YOUR_PRODUCTION_CLIENT_ID
YANDEX_CLIENT_SECRET=YOUR_PRODUCTION_CLIENT_SECRET
YANDEX_REDIRECT_URI=https://your-domain.com/api/yandex/callback
YANDEX_SCOPE=login:email login:info mail:imap_full mail:smtp

# Администратор
MODERATOR_MASTER_EMAIL=admin@your-domain.com
```

#### Backend (`.env.production`)

```env
# Database (your production DB)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Security
SECRET_KEY=your-very-secret-key-at-least-32-chars
DEBUG=false
ALLOWED_HOSTS=your-domain.com,api.your-domain.com

# CORS
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Mail (if needed)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Logging
LOG_LEVEL=INFO
```

### Шаг 3: Обновить конфигурацию Яндекса

#### На https://oauth.yandex.ru:

1. Откройте приложение B2B Platform
2. Перейдите на вкладку "Redirect URLs"
3. Добавьте production URL:
   ```
   https://your-domain.com/api/yandex/callback
   ```
4. Сохраните изменения
5. Скопируйте новые Client ID и Client Secret
6. Убедитесь, что приложение опубликовано (не в draft)

### Шаг 4: Обновить Content-Security-Policy

#### В `next.config.mjs`:

```javascript
const nextConfig = {
  // ...
  headers: async () => {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https:; font-src 'self' data: https://fonts.gstatic.com https:; connect-src 'self' https://your-domain.com https://api.your-domain.com https://oauth.yandex.ru https://login.yandex.ru; frame-ancestors 'none'",
          },
        ],
      },
      {
        source: "/moderator/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https:; font-src 'self' data: https://fonts.gstatic.com https:; connect-src 'self' https://your-domain.com https://api.your-domain.com https://oauth.yandex.ru https://login.yandex.ru; frame-ancestors 'self'",
          },
        ],
      },
    ]
  },
}
```

### Шаг 5: Настроить CORS на backend

#### В FastAPI (FastAPI код):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-domain.com",
        "https://www.your-domain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

### Шаг 6: Включить HTTPS везде

#### Frontend:
```bash
# Next.js автоматически требует HTTPS в production
# Убедитесь, что ваш хостер использует HTTPS
```

#### Backend:
```python
# В settings.py добавьте:
SECURE_SSL_REDIRECT = not DEBUG  # True в production
SESSION_COOKIE_SECURE = not DEBUG  # True в production
CSRF_COOKIE_SECURE = not DEBUG  # True в production
```

### Шаг 7: Настроить логирование

#### Frontend:
```javascript
// В app/layout.tsx добавьте:
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
});
```

#### Backend:
```python
# В main.py добавьте:
import logging
from logging.handlers import RotatingFileHandler

# Setup logging
log_handler = RotatingFileHandler('logs/app.log', maxBytes=10000000, backupCount=5)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO if not DEBUG else logging.DEBUG)
```

### Шаг 8: Развернуть на сервере

#### Option 1: Vercel (для Frontend)

```bash
# Коннектить GitHub репозиторий к Vercel
# Vercel автоматически разворачивает при push

# Или вручную:
vercel --prod
```

#### Option 2: Docker (для обоих компонентов)

**Frontend Dockerfile:**
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY frontend/moderator-dashboard-ui/package*.json ./
RUN npm ci
COPY frontend/moderator-dashboard-ui/ ./
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

**Backend Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
EXPOSE 8010
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  frontend:
    build: ./frontend/moderator-dashboard-ui
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: https://api.your-domain.com
      YANDEX_CLIENT_ID: YOUR_CLIENT_ID
      YANDEX_CLIENT_SECRET: YOUR_CLIENT_SECRET
      YANDEX_REDIRECT_URI: https://your-domain.com/api/yandex/callback

  backend:
    build: ./backend
    ports:
      - "8010:8010"
    environment:
      DATABASE_URL: postgresql://...
      DEBUG: "false"
```

### Шаг 9: Настроить обратный прокси (Nginx)

#### `/etc/nginx/sites-available/your-domain.com`:

```nginx
upstream frontend {
  server localhost:3000;
}

upstream backend {
  server localhost:8010;
}

server {
    listen 443 ssl;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}

# Перенаправить HTTP на HTTPS
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Шаг 10: Тестирование в продакшене

```bash
# 1. Проверить frontend
curl https://your-domain.com/login

# 2. Проверить backend
curl https://api.your-domain.com/health

# 3. Проверить OAuth конфиг
curl https://your-domain.com/api/yandex/config

# 4. Полный flow тестирования
# Откройте https://your-domain.com/login в браузере
# Авторизуйтесь через Яндекс
# Проверьте, что попали в кабинет
```

---

## 🔍 Мониторинг в продакшене

### Показатели для отслеживания

1. **Frontend**
   - Page load time
   - JavaScript errors
   - 404 errors
   - Slow network requests

2. **Backend**
   - Response time
   - Error rate
   - Database performance
   - OAuth callback failures

3. **OAuth**
   - Login success rate
   - Token refresh rate
   - Error rate
   - Average time to login

### Инструменты мониторинга

- **Sentry** - для отслеживания ошибок
- **Datadog** - для мониторинга производительности
- **LogRocket** - для отслеживания пользовательских сессий
- **New Relic** - для полного мониторинга

---

## 🆘 Отладка проблем в продакшене

### Проблема: "Invalid redirect_uri"

**Решение:**
1. Проверьте `YANDEX_REDIRECT_URI` в `.env.production`
2. Проверьте, что URL добавлен в приложение на oauth.yandex.ru
3. Убедитесь, что домен использует HTTPS

### Проблема: "Certificate verification failed"

**Решение:**
1. Убедитесь, что SSL сертификат правильно установлен
2. Проверьте, что сертификат не истек
3. Используйте `certbot` для автоматического обновления

### Проблема: CORS errors

**Решение:**
1. Проверьте `CORS_ORIGINS` в backend конфигурации
2. Проверьте `Content-Security-Policy` headers
3. Убедитесь, что домены правильно указаны

### Проблема: Cookies не работают

**Решение:**
1. Убедитесь, что используется HTTPS
2. Проверьте `secure` флаг в cookie settings
3. Проверьте `sameSite` значение

---

## 📈 Масштабирование

### Если трафик растет

1. **Frontend:**
   - Используйте CDN (Cloudflare, Akamai)
   - Включите caching
   - Оптимизируйте assets

2. **Backend:**
   - Используйте load balancer
   - Масштабируйте horizontally (добавляйте серверы)
   - Используйте кэширование (Redis)
   - Оптимизируйте БД queries

3. **Database:**
   - Используйте read replicas
   - Включите connection pooling
   - Оптимизируйте indexes

---

## 🔒 Безопасность в продакшене

### Обязательные меры

1. **HTTPS везде** ✅
2. **Secure cookies** ✅
3. **CORS правильно** ✅
4. **Rate limiting** ✅
5. **Input validation** ✅
6. **SQL injection protection** ✅
7. **XSS protection** ✅
8. **CSRF protection** ✅
9. **DDoS protection** (Cloudflare) ✅
10. **WAF** (Web Application Firewall) ✅

---

## ✅ Финальная проверка

Перед go-live:

- [ ] Все переменные окружения установлены
- [ ] Сертификаты SSL действительны
- [ ] Яндекс OAuth конфигурирован
- [ ] CORS правильно настроен
- [ ] Логирование работает
- [ ] Мониторинг включен
- [ ] Backup система настроена
- [ ] Recovery процедуры задокументированы
- [ ] Команда обучена
- [ ] Есть план на случай emergency

---

## 📞 Поддержка в продакшене

### Emergency контакты

- **Разработчик:** admin@your-domain.com
- **Администратор Яндекса:** edwatik@yandex.ru
- **Хостер поддержка:** support@hosting.com

### Процедура при отключении

1. Проверить логи
2. Перезагрузить сервис
3. Проверить конфигурацию
4. Переключиться на backup
5. Обратиться к хостеру
6. Создать incident report

---

**Версия:** 1.0  
**Дата:** 2026-02-07  
**Статус:** Готово к продакшену ✅
