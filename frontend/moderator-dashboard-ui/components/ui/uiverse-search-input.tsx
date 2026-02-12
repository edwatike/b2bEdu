import * as React from "react"

import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import styles from "./uiverse-search-input.module.css"

export interface UiverseSearchInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  containerClassName?: string
  filterOpen?: boolean
  onFilterOpenChange?: (open: boolean) => void
  filterContent?: React.ReactNode
}

const UiverseSearchInput = React.forwardRef<HTMLInputElement, UiverseSearchInputProps>(
  ({
    className,
    containerClassName,
    placeholder,
    filterOpen,
    onFilterOpenChange,
    filterContent,
    ...props
  }, ref) => {
    return (
      <div className={cn(styles.root, containerClassName)}>
        <div className={styles.frame}>
          <div className={styles.glow} aria-hidden="true" />
          <div className={styles.content}>
            <div className={styles.searchIcon} aria-hidden="true">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
                height="24"
                fill="none"
              >
                <circle r="8" cy="11" cx="11" />
                <line y2="16.65" y1="22" x2="16.65" x1="22" />
              </svg>
            </div>
            <input
              ref={ref}
              type="text"
              placeholder={placeholder}
              className={cn(styles.searchInput, className)}
              {...props}
            />

            {filterContent ? (
              <Popover open={Boolean(filterOpen)} onOpenChange={onFilterOpenChange}>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    aria-label="Фильтры"
                    disabled={!onFilterOpenChange}
                    className={styles.filterButton}
                  >
                    <svg
                      preserveAspectRatio="none"
                      height="18"
                      width="18"
                      viewBox="4.8 4.56 14.832 15.408"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M8.16 6.65002H15.83C16.47 6.65002 16.99 7.17002 16.99 7.81002V9.09002C16.99 9.56002 16.7 10.14 16.41 10.43L13.91 12.64C13.56 12.93 13.33 13.51 13.33 13.98V16.48C13.33 16.83 13.1 17.29 12.81 17.47L12 17.98C11.24 18.45 10.2 17.92 10.2 16.99V13.91C10.2 13.5 9.97 12.98 9.73 12.69L7.52 10.36C7.23 10.08 7 9.55002 7 9.20002V7.87002C7 7.17002 7.52 6.65002 8.16 6.65002Z"
                        stroke="currentColor"
                        strokeWidth="1"
                        strokeMiterlimit="10"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-56 p-1">
                  {filterContent}
                </PopoverContent>
              </Popover>
            ) : null}
          </div>
        </div>
      </div>
    )
  },
)
UiverseSearchInput.displayName = "UiverseSearchInput"

export { UiverseSearchInput }
