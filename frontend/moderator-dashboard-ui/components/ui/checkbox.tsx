import * as React from "react"

import { cn } from "@/lib/utils"

type CheckboxProps = {
  checked?: boolean
  disabled?: boolean
  onCheckedChange?: (checked: boolean) => void
  className?: string
} & Omit<React.HTMLAttributes<HTMLLabelElement>, "onChange"> & {
    onClick?: React.MouseEventHandler<HTMLLabelElement>
  }

const Checkbox = React.forwardRef<HTMLLabelElement, CheckboxProps>(
  ({ className, checked, disabled, onCheckedChange, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn("uv-cb", disabled && "opacity-50 cursor-not-allowed", className)}
        {...props}
      >
        <input
          type="checkbox"
          checked={Boolean(checked)}
          disabled={disabled}
          onChange={(e) => onCheckedChange?.(e.target.checked)}
        />
        <div className="uv-cb-checkmark" />
      </label>
    )
  },
)

Checkbox.displayName = "Checkbox"

export { Checkbox }
