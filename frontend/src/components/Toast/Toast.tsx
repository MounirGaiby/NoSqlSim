import { useEffect, useState, useCallback } from 'react'
import './Toast.css'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastMessage {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
}

interface ToastProps {
  toast: ToastMessage
  onDismiss: (id: string) => void
}

function Toast({ toast, onDismiss }: ToastProps) {
  const [isExiting, setIsExiting] = useState(false)

  const handleDismiss = useCallback(() => {
    setIsExiting(true)
    setTimeout(() => onDismiss(toast.id), 300)
  }, [onDismiss, toast.id])

  useEffect(() => {
    const duration = toast.duration ?? 4000
    if (duration > 0) {
      const timer = setTimeout(handleDismiss, duration)
      return () => clearTimeout(timer)
    }
  }, [toast.duration, handleDismiss])

  const icons: Record<ToastType, string> = {
    success: '\u2713',
    error: '\u2717',
    warning: '\u26A0',
    info: '\u2139',
  }

  return (
    <div className={`toast toast-${toast.type} ${isExiting ? 'toast-exit' : ''}`}>
      <div className="toast-icon">{icons[toast.type]}</div>
      <div className="toast-content">
        <div className="toast-title">{toast.title}</div>
        {toast.message && <div className="toast-message">{toast.message}</div>}
      </div>
      <button className="toast-close" onClick={handleDismiss} aria-label="Dismiss">
        \u2715
      </button>
    </div>
  )
}

interface ToastContainerProps {
  toasts: ToastMessage[]
  onDismiss: (id: string) => void
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

let toastIdCounter = 0

interface ToastStore {
  toasts: ToastMessage[]
  listeners: Set<() => void>
  addToast: (toast: Omit<ToastMessage, 'id'>) => string
  removeToast: (id: string) => void
  subscribe: (listener: () => void) => () => void
  getToasts: () => ToastMessage[]
}

const toastStore: ToastStore = {
  toasts: [],
  listeners: new Set(),

  addToast(toast) {
    const id = `toast-${++toastIdCounter}`
    this.toasts = [...this.toasts, { ...toast, id }]
    this.listeners.forEach((listener) => listener())
    return id
  },

  removeToast(id) {
    this.toasts = this.toasts.filter((t) => t.id !== id)
    this.listeners.forEach((listener) => listener())
  },

  subscribe(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  },

  getToasts() {
    return this.toasts
  },
}

export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>(toastStore.getToasts())

  useEffect(() => {
    return toastStore.subscribe(() => {
      setToasts(toastStore.getToasts())
    })
  }, [])

  const showToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    return toastStore.addToast(toast)
  }, [])

  const dismissToast = useCallback((id: string) => {
    toastStore.removeToast(id)
  }, [])

  const success = useCallback((title: string, message?: string) => {
    return showToast({ type: 'success', title, message })
  }, [showToast])

  const error = useCallback((title: string, message?: string) => {
    return showToast({ type: 'error', title, message })
  }, [showToast])

  const warning = useCallback((title: string, message?: string) => {
    return showToast({ type: 'warning', title, message })
  }, [showToast])

  const info = useCallback((title: string, message?: string) => {
    return showToast({ type: 'info', title, message })
  }, [showToast])

  return {
    toasts,
    showToast,
    dismissToast,
    success,
    error,
    warning,
    info,
  }
}
