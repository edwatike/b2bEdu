"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export interface ManualLearnDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  domain: string
  /** Pre-filled INN value */
  inn?: string
  /** Pre-filled email value */
  email?: string
  /** Pre-filled INN source URL */
  innSourceUrl?: string
  /** Pre-filled email source URL */
  emailSourceUrl?: string
  /** Pre-filled supplier type */
  supplierType?: "supplier" | "reseller"
  /** Whether INN field should be disabled (e.g. when INN is already known) */
  innDisabled?: boolean
  /** Whether to show email source URL field (parsing-run page needs it, domains page doesn't) */
  showEmailSourceUrl?: boolean
  /** Whether to show supplier type selector */
  showSupplierType?: boolean
  /** Whether submission is in progress */
  submitting?: boolean
  /** Called when user submits the form */
  onSubmit: (data: ManualLearnFormData) => void
}

export interface ManualLearnFormData {
  domain: string
  inn: string
  email: string
  sourceUrl: string
  sourceUrls: string[]
  emailSourceUrl: string
  supplierType: "supplier" | "reseller"
}

export function ManualLearnDialog({
  open,
  onOpenChange,
  domain,
  inn = "",
  email = "",
  innSourceUrl = "",
  emailSourceUrl = "",
  supplierType = "supplier",
  innDisabled = false,
  showEmailSourceUrl = false,
  showSupplierType = false,
  submitting = false,
  onSubmit,
}: ManualLearnDialogProps) {
  const [formInn, setFormInn] = useState(inn)
  const [formEmail, setFormEmail] = useState(email)
  const [formSourceUrl, setFormSourceUrl] = useState(innSourceUrl)
  const [formSourceUrlsText, setFormSourceUrlsText] = useState("")
  const [formEmailSourceUrl, setFormEmailSourceUrl] = useState(emailSourceUrl)
  const [formSupplierType, setFormSupplierType] = useState<"supplier" | "reseller">(supplierType)

  useEffect(() => {
    if (open) {
      setFormInn(inn)
      setFormEmail(email)
      setFormSourceUrl(innSourceUrl)
      setFormSourceUrlsText("")
      setFormEmailSourceUrl(emailSourceUrl)
      setFormSupplierType(supplierType)
    }
  }, [open, inn, email, innSourceUrl, emailSourceUrl, supplierType])

  const handleSubmit = () => {
    const sourceUrls = formSourceUrlsText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
    onSubmit({
      domain,
      inn: formInn,
      email: formEmail,
      sourceUrl: formSourceUrl,
      sourceUrls,
      emailSourceUrl: formEmailSourceUrl || formSourceUrl,
      supplierType: formSupplierType,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Обучить парсер по ИНН</DialogTitle>
          <DialogDescription>
            Укажите правильные данные для обучения парсера на домене {domain}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label htmlFor="manual-learn-domain">Домен</Label>
            <Input id="manual-learn-domain" value={domain} disabled />
          </div>
          <div>
            <Label htmlFor="manual-learn-inn">ИНН</Label>
            <Input
              id="manual-learn-inn"
              value={formInn}
              onChange={(e) => setFormInn(e.target.value.replace(/\D/g, ""))}
              disabled={innDisabled}
              placeholder="ИНН компании"
            />
          </div>
          <div>
            <Label htmlFor="manual-learn-email">Email</Label>
            <Input
              id="manual-learn-email"
              type="email"
              value={formEmail}
              onChange={(e) => setFormEmail(e.target.value)}
              placeholder="info@example.com"
            />
          </div>
          <div>
            <Label htmlFor="manual-learn-url">Ссылка на страницу с ИНН (Обязательно)</Label>
            <Input
              id="manual-learn-url"
              value={formSourceUrl}
              onChange={(e) => setFormSourceUrl(e.target.value)}
              placeholder="https://example.com/contacts"
            />
          </div>
          <div>
            <Label htmlFor="manual-learn-urls">Доп. ссылки (по 1 в строке)</Label>
            <Textarea
              id="manual-learn-urls"
              value={formSourceUrlsText}
              onChange={(e) => setFormSourceUrlsText(e.target.value)}
              placeholder={"https://site.ru/company/rekvizity\nhttps://site.ru/contacts"}
              rows={3}
            />
            <div className="text-[10px] text-muted-foreground mt-1">
              Вставь 1–3 ссылки на страницы, где реально виден ИНН (реквизиты/о компании/контакты). Это улучшает обучение URL-паттернам.
            </div>
          </div>
          {showEmailSourceUrl && (
            <div>
              <Label htmlFor="manual-learn-email-url">Ссылка на страницу с Email</Label>
              <Input
                id="manual-learn-email-url"
                value={formEmailSourceUrl}
                onChange={(e) => setFormEmailSourceUrl(e.target.value)}
                placeholder="https://example.com/contacts"
              />
            </div>
          )}
          {showSupplierType && (
            <div>
              <Label>Тип компании</Label>
              <Select value={formSupplierType} onValueChange={(v) => setFormSupplierType(v as "supplier" | "reseller")}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите тип" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="supplier">Поставщик</SelectItem>
                  <SelectItem value="reseller">Реселлер</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Отмена
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Обучение..." : "Сохранить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
