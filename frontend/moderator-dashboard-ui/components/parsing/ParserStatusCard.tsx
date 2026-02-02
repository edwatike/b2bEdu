"use client"

import { motion } from "framer-motion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { FileSearch } from "lucide-react"

export interface ParserResult {
  domain: string
  inn: string | null
  emails: string[]
  sourceUrls: string[]
  error: string | null
}

export interface ParserStatusData {
  runId: string
  parserRunId: string
  status: "running" | "completed" | "failed"
  processed: number
  total: number
  results: ParserResult[]
}

interface ParserStatusCardProps {
  parserStatus: ParserStatusData | null
  parserLoading: boolean
}

export function ParserStatusCard({ parserStatus, parserLoading }: ParserStatusCardProps) {
  if (!parserStatus) return null

  return (
    <Card className="mt-6 border-2 border-blue-500">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileSearch className="h-5 w-5 text-blue-600" />
          Статус получения данных
          {parserLoading && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="ml-2"
            >
              <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full" />
            </motion.div>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 mb-4">
          <Badge
            variant={
              parserStatus.status === "completed"
                ? "default"
                : parserStatus.status === "running"
                  ? "secondary"
                  : "destructive"
            }
            className={
              parserStatus.status === "completed"
                ? "bg-green-600"
                : parserStatus.status === "running"
                  ? "bg-blue-600"
                  : ""
            }
          >
            {parserStatus.status === "completed"
              ? "✅ Завершено"
              : parserStatus.status === "running"
                ? "⏳ Выполняется..."
                : "❌ Ошибка"}
          </Badge>
          <span className="text-sm text-muted-foreground">
            Обработано: {parserStatus.processed} / {parserStatus.total}
          </span>
        </div>

        {parserStatus.status === "running" && (
          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <motion.div
              className="bg-gradient-to-r from-blue-600 to-cyan-600 h-2 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${(parserStatus.processed / parserStatus.total) * 100}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        )}

        {parserStatus.results && parserStatus.results.length > 0 && (
          <Accordion type="multiple" className="w-full">
            {parserStatus.results.map((result, idx) => {
              const hasData = result.inn || (result.emails && result.emails.length > 0)
              const hasError = !!result.error

              return (
                <AccordionItem key={`parser-${idx}`} value={`parser-${idx}`} className="border-b">
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex items-center gap-2 flex-1">
                      <span
                        className={`w-3 h-3 rounded-full ${hasError ? "bg-red-500" : hasData ? "bg-green-500" : "bg-gray-400"}`}
                      />
                      <span className="font-mono font-semibold">{result.domain}</span>
                      {result.inn && <Badge className="bg-blue-600 text-white">ИНН: {result.inn}</Badge>}
                      {result.emails && result.emails.length > 0 && (
                        <Badge className="bg-green-600 text-white">Email: {result.emails[0]}</Badge>
                      )}
                      {hasError && <Badge variant="destructive">Ошибка</Badge>}
                      {!hasData && !hasError && <Badge variant="outline">Не найдено</Badge>}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="pt-2 space-y-3">
                      {result.inn && (
                        <div className="text-sm">
                          <p className="font-semibold text-blue-700 mb-1">ИНН найден:</p>
                          <div className="p-2 bg-blue-50 rounded border border-blue-200">
                            <span className="font-mono text-lg">{result.inn}</span>
                          </div>
                        </div>
                      )}

                      {result.emails && result.emails.length > 0 && (
                        <div className="text-sm">
                          <p className="font-semibold text-green-700 mb-1">Email найден:</p>
                          <div className="space-y-1">
                            {result.emails.map((email, emailIdx) => (
                              <div key={emailIdx} className="p-2 bg-green-50 rounded border border-green-200">
                                <a href={`mailto:${email}`} className="text-green-700 hover:underline">
                                  {email}
                                </a>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {result.sourceUrls && result.sourceUrls.length > 0 && (
                        <div className="text-sm">
                          <p className="font-semibold text-muted-foreground mb-1">
                            Источники ({result.sourceUrls.length}):
                          </p>
                          <div className="space-y-1">
                            {result.sourceUrls.map((url, urlIdx) => (
                              <div key={urlIdx} className="text-xs">
                                <a
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:underline break-all"
                                >
                                  {url}
                                </a>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {result.error && (
                        <div className="text-sm">
                          <p className="font-semibold text-red-700 mb-1">Ошибка:</p>
                          <div className="p-2 bg-red-50 rounded border border-red-200 text-red-700">
                            {result.error}
                          </div>
                        </div>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )
            })}
          </Accordion>
        )}
      </CardContent>
    </Card>
  )
}
