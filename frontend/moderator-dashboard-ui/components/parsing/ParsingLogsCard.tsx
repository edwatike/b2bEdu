"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { ScrollText } from "lucide-react"

interface ParsingLog {
  total_links?: number
  pages_processed?: number
  last_links?: string[]
  links_by_page?: Record<string, number>
}

interface ParsingLogsData {
  google?: ParsingLog
  yandex?: ParsingLog
}

interface ParsingLogsCardProps {
  parsingLogs: ParsingLogsData | null
  isLoading: boolean
  accordionValue: string[]
  onAccordionChange: (value: string[]) => void
}

export function ParsingLogsCard({
  parsingLogs,
  isLoading,
  accordionValue,
  onAccordionChange,
}: ParsingLogsCardProps) {
  if (!parsingLogs && !isLoading) return null

  return (
    <Card className="mt-6 border-2 border-purple-300">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScrollText className="h-5 w-5 text-purple-600" />
          Логи парсинга поисковых систем
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground animate-pulse">Загрузка логов парсинга...</p>
        ) : parsingLogs ? (
          <Accordion
            type="multiple"
            value={accordionValue}
            onValueChange={onAccordionChange}
            className="w-full"
          >
            {/* Google Logs */}
            {parsingLogs.google && (
              <AccordionItem value="google-logs" className="border-b">
                <AccordionTrigger className="hover:no-underline">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-blue-500" />
                    <span className="font-semibold">Google</span>
                    <Badge variant="outline" className="ml-2">
                      {parsingLogs.google.total_links || 0} ссылок
                    </Badge>
                    <Badge variant="outline">
                      {parsingLogs.google.pages_processed || 0} страниц
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="pt-2 space-y-3">
                    {parsingLogs.google.links_by_page && (
                      <div className="text-sm">
                        <p className="font-semibold text-blue-700 mb-1">Ссылок по страницам:</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(parsingLogs.google.links_by_page).map(([page, count]) => (
                            <Badge key={page} variant="secondary">
                              Стр. {page}: {count}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {parsingLogs.google.last_links && parsingLogs.google.last_links.length > 0 && (
                      <div className="text-sm">
                        <p className="font-semibold text-muted-foreground mb-1">
                          Последние найденные ссылки ({parsingLogs.google.last_links.length}):
                        </p>
                        <div className="max-h-40 overflow-y-auto space-y-1 bg-gray-50 p-2 rounded">
                          {parsingLogs.google.last_links.slice(0, 10).map((link, idx) => (
                            <div key={idx} className="text-xs truncate">
                              <a
                                href={link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline"
                              >
                                {link}
                              </a>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            )}

            {/* Yandex Logs */}
            {parsingLogs.yandex && (
              <AccordionItem value="yandex-logs" className="border-b">
                <AccordionTrigger className="hover:no-underline">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-500" />
                    <span className="font-semibold">Yandex</span>
                    <Badge variant="outline" className="ml-2">
                      {parsingLogs.yandex.total_links || 0} ссылок
                    </Badge>
                    <Badge variant="outline">
                      {parsingLogs.yandex.pages_processed || 0} страниц
                    </Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="pt-2 space-y-3">
                    {parsingLogs.yandex.links_by_page && (
                      <div className="text-sm">
                        <p className="font-semibold text-red-700 mb-1">Ссылок по страницам:</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(parsingLogs.yandex.links_by_page).map(([page, count]) => (
                            <Badge key={page} variant="secondary">
                              Стр. {page}: {count}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {parsingLogs.yandex.last_links && parsingLogs.yandex.last_links.length > 0 && (
                      <div className="text-sm">
                        <p className="font-semibold text-muted-foreground mb-1">
                          Последние найденные ссылки ({parsingLogs.yandex.last_links.length}):
                        </p>
                        <div className="max-h-40 overflow-y-auto space-y-1 bg-gray-50 p-2 rounded">
                          {parsingLogs.yandex.last_links.slice(0, 10).map((link, idx) => (
                            <div key={idx} className="text-xs truncate">
                              <a
                                href={link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline"
                              >
                                {link}
                              </a>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            )}
          </Accordion>
        ) : (
          <p className="text-sm text-muted-foreground">Логи парсинга пока недоступны...</p>
        )}
      </CardContent>
    </Card>
  )
}
