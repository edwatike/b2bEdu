# Flintstones Wheel Integration Example

## Как использовать компонент в вашем фронтенде

### 1. Импорт компонента

В файле `app/parsing-runs/[runId]/page.tsx` добавьте импорт:

```tsx
import { FlinstonesWheel, FlinstonesProgressBar } from "@/components/flintstones-wheel"
```

### 2. Использование в карточке статуса парсинга

Замените текущий блок со статусом парсинга:

```tsx
// Было:
<div className="flex items-center gap-2">
  <span className="text-2xl font-bold text-purple-600">{run.resultsCount}</span>
  <span className="text-sm text-muted-foreground">результатов</span>
</div>

// Стало:
<div className="flex flex-col items-center gap-2">
  <FlinstonesWheel 
    progress={run.processingProgress || 0} 
    size={60}
    label="Обработано"
    sublabel={`${run.resultsCount} из ${run.totalDomains}`}
    isActive={run.status === 'processing'}
  />
</div>
```

### 3. Использование в прогресс-барах

Замените текущий прогресс-бар извлечения:

```tsx
// Было:
<div className="flex items-center gap-2">
  <div className="text-sm">
    <span className="text-blue-600">🏢 {processedCount}</span>
    <span className="text-amber-600">⚠️ {errorCount}</span>
    <span className="text-emerald-600">/ {totalCount} обработано</span>
  </div>
</div>

// Стало:
<FlinstonesProgressBar
  progress={(processedCount / totalCount) * 100}
  label="Извлечение ИНН / Email"
  color="blue"
  current={processedCount}
  total={totalCount}
/>
```

### 4. Использование в карточках доменов

Для каждого домена можно добавить мини-колесо статуса:

```tsx
// В таблице доменов добавить колонку со статусом:
<td className="py-1.5 px-3">
  <FlinstonesWheel 
    progress={g.processingProgress || 0}
    size={32}
    isActive={g.status === 'processing'}
  />
</td>
```

### 5. Полный пример интеграции

```tsx
// В компоненте страницы парсинга:
<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
  {/* Общий прогресс */}
  <Card>
    <CardContent className="p-4">
      <FlinstonesWheel 
        progress={overallProgress}
        size={80}
        label="Общий прогресс"
        sublabel={`${processedDomains} из ${totalDomains}`}
        isActive={isProcessing}
      />
    </CardContent>
  </Card>

  {/* Прогресс извлечения */}
  <Card>
    <CardContent className="p-4">
      <FlinstonesProgressBar
        progress={extractionProgress}
        label="Извлечение данных"
        color="emerald"
        current={extractedCount}
        total={totalCount}
      />
    </CardContent>
  </Card>

  {/* Прогресс модерации */}
  <Card>
    <CardContent className="p-4">
      <FlinstonesProgressBar
        progress={moderationProgress}
        label="Модерация"
        color="amber"
        current={moderatedCount}
        total={totalCount}
      />
    </CardContent>
  </Card>
</div>
```

## 6. Демо компонент

Для тестирования используйте `FlintstonesDemo`:

```tsx
import { FlintstonesDemo } from "@/components/flintstones-demo"

// Добавьте на любую страницу для демонстрации:
<FlintstonesDemo />
```

## 7. Кастомизация

Компоненты поддерживают кастомизацию:

```tsx
<FlinstonesWheel 
  progress={75}
  size={100}           // Размер колеса
  label="Парсинг"      // Основная надпись
  sublabel="75%"       // Дополнительная надпись
  isActive={true}      // Анимация активности
/>

<FlinstonesProgressBar
  progress={60}
  label="Процесс"
  color="emerald"      // blue | emerald | amber | red
  total={100}
  current={60}
/>
```

## 8. Где найти готовые примеры

- `components/flintstones-demo.tsx` - полный демо компонент
- `components/flintstones-wheel.tsx` - исходный код компонента

Компонент готов к использованию и полностью совместим с вашим текущим стеком (Next.js, Tailwind, Framer Motion).
