import './Skeleton.css'

interface SkeletonProps {
  width?: string | number
  height?: string | number
  variant?: 'text' | 'circular' | 'rectangular'
  className?: string
}

export function Skeleton({ 
  width = '100%', 
  height = '1rem', 
  variant = 'rectangular',
  className = ''
}: SkeletonProps) {
  const style = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  }

  return (
    <div 
      className={`skeleton skeleton-${variant} ${className}`}
      style={style}
      aria-hidden="true"
    />
  )
}

interface SkeletonCanvasProps {
  width?: number
  height?: number
}

export function SkeletonCanvas({ width = 700, height = 380 }: SkeletonCanvasProps) {
  return (
    <div className="skeleton-canvas" style={{ width, height }}>
      <div className="skeleton-canvas-content">
        <div className="skeleton-spinner"></div>
        <div className="skeleton-text">Loading cluster topology...</div>
      </div>
    </div>
  )
}

interface LoadingOverlayProps {
  message?: string
  visible: boolean
}

export function LoadingOverlay({ message = 'Processing...', visible }: LoadingOverlayProps) {
  if (!visible) return null

  return (
    <div className="loading-overlay">
      <div className="loading-content">
        <div className="loading-spinner"></div>
        <div className="loading-message">{message}</div>
      </div>
    </div>
  )
}
