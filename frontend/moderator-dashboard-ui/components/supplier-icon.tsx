import React from "react";
import { Factory } from "lucide-react";

export function SupplierIcon({ title = "Поставщик" }: { title?: string }) {
  return (
    <span
      title={title}
      aria-label="Поставщик"
      className="inline-flex h-7 w-7 items-center justify-center rounded-full
                 border border-emerald-200 bg-emerald-50 text-emerald-800
                 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200"
    >
      <Factory className="h-4 w-4" />
    </span>
  );
}
