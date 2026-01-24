import { useCallback, useEffect, useRef } from 'react'
import './ConfirmDialog.css'

export interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'info'
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel()
    }
  }, [onCancel])

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      confirmButtonRef.current?.focus()
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  if (!isOpen) return null

  const icons = {
    danger: '\u26A0',
    warning: '\u26A0',
    info: '\u2139',
  }

  return (
    <div className="confirm-overlay" onClick={onCancel}>
      <div 
        ref={dialogRef}
        className={`confirm-dialog confirm-${variant}`}
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-message"
      >
        <div className="confirm-header">
          <span className={`confirm-icon confirm-icon-${variant}`}>{icons[variant]}</span>
          <h3 id="confirm-title">{title}</h3>
        </div>
        <p id="confirm-message" className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button 
            className="btn-ghost" 
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button 
            ref={confirmButtonRef}
            className={`btn-${variant === 'danger' ? 'danger' : variant === 'warning' ? 'warning' : 'primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

interface UseConfirmDialogOptions {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'info'
}

export function useConfirmDialog() {
  const resolveRef = useRef<((value: boolean) => void) | null>(null)

  const confirm = useCallback((_options: UseConfirmDialogOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      resolveRef.current = resolve
    })
  }, [])

  return { confirm }
}
