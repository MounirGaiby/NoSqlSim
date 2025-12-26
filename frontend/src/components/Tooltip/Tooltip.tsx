import { useState } from 'react'
import './Tooltip.css'

interface TooltipProps {
  content: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  maxWidth?: string
}

export function Tooltip({ content, position = 'top', maxWidth = '250px' }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <span className="tooltip-wrapper">
      <span
        className="tooltip-icon"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onFocus={() => setIsVisible(true)}
        onBlur={() => setIsVisible(false)}
        tabIndex={0}
        role="button"
        aria-label="Help"
      >
        ?
      </span>
      {isVisible && (
        <span
          className={`tooltip-content tooltip-${position}`}
          style={{ maxWidth }}
          role="tooltip"
        >
          {content}
        </span>
      )}
    </span>
  )
}
