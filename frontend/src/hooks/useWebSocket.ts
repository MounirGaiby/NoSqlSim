import { useEffect, useRef, useState, useCallback } from 'react'
import { ClusterState } from '../types/cluster'

interface WebSocketMessage {
  type: string
  timestamp: string
  payload: any
}

interface UseWebSocketReturn {
  isConnected: boolean
  lastMessage: WebSocketMessage | null
  clusterState: ClusterState | null
  sendMessage: (message: string) => void
  reconnect: () => void
  subscribeToNodeLogs: (nodeId: string, callback: (logs: string) => void) => void
  unsubscribeFromNodeLogs: (nodeId: string) => void
}

const WS_URL = import.meta.env.DEV
  ? 'ws://localhost:8000/ws'
  : `ws://${window.location.host}/ws`

const RECONNECT_DELAY = 1000 // 1 second - faster reconnect
const MAX_RECONNECT_ATTEMPTS = 15

export function useWebSocket(onStateUpdate?: (state: ClusterState) => void): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [clusterState, setClusterState] = useState<ClusterState | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const shouldReconnectRef = useRef(true)
  const isConnectingRef = useRef(false)

  // Track log callbacks for each node
  const logCallbacksRef = useRef<Map<string, (logs: string) => void>>(new Map())

  // Store callback in ref to avoid dependency changes causing reconnections
  const onStateUpdateRef = useRef(onStateUpdate)
  useEffect(() => {
    onStateUpdateRef.current = onStateUpdate
  }, [onStateUpdate])

  const connect = useCallback(() => {
    // Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) {
      console.log('[WebSocket] Already connecting, skipping...')
      return
    }
    
    // Clean up existing connection
    if (wsRef.current) {
      const currentState = wsRef.current.readyState
      // If already connected or connecting, don't reconnect
      if (currentState === WebSocket.OPEN || currentState === WebSocket.CONNECTING) {
        console.log('[WebSocket] Already connected or connecting, skipping...')
        return
      }
      wsRef.current.close()
      wsRef.current = null
    }

    isConnectingRef.current = true
    console.log('[WebSocket] Connecting to', WS_URL)
    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      console.log('[WebSocket] Connected')
      isConnectingRef.current = false
      setIsConnected(true)
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        console.log('[WebSocket] Message received:', message.type)

        setLastMessage(message)

        // Handle different message types
        if (message.type === 'cluster_state' && message.payload) {
          const state = message.payload as ClusterState
          setClusterState(state)

          // Call optional callback using ref to get latest value
          if (onStateUpdateRef.current) {
            onStateUpdateRef.current(state)
          }
        } else if (message.type === 'node_logs' && message.payload) {
          const { node_id, logs } = message.payload
          const callback = logCallbacksRef.current.get(node_id)
          if (callback) {
            callback(logs)
          }
        }
      } catch (error) {
        console.error('[WebSocket] Error parsing message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
      isConnectingRef.current = false
    }

    ws.onclose = () => {
      console.log('[WebSocket] Disconnected')
      isConnectingRef.current = false
      setIsConnected(false)
      wsRef.current = null

      // Attempt to reconnect if we should
      if (shouldReconnectRef.current && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current++
        console.log(
          `[WebSocket] Reconnecting in ${RECONNECT_DELAY / 1000}s (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
        )

        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, RECONNECT_DELAY)
      } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        console.error('[WebSocket] Max reconnection attempts reached')
      }
    }

    wsRef.current = ws
  }, []) // No dependencies - connect function is stable

  const sendMessage = useCallback((message: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(message)
    } else {
      console.warn('[WebSocket] Cannot send message: not connected')
    }
  }, [])

  const reconnect = useCallback(() => {
    console.log('[WebSocket] Manual reconnect triggered')
    reconnectAttemptsRef.current = 0
    isConnectingRef.current = false // Reset connecting state for manual reconnect

    // Close existing connection first
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    connect()
  }, [connect])

  const subscribeToNodeLogs = useCallback((nodeId: string, callback: (logs: string) => void) => {
    console.log(`[WebSocket] Subscribing to logs for ${nodeId}`)

    // Store callback
    logCallbacksRef.current.set(nodeId, callback)

    // Send subscription message
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ action: 'subscribe_logs', node_id: nodeId })
      wsRef.current.send(message)
    } else {
      console.warn('[WebSocket] Cannot subscribe: not connected')
    }
  }, [])

  const unsubscribeFromNodeLogs = useCallback((nodeId: string) => {
    console.log(`[WebSocket] Unsubscribing from logs for ${nodeId}`)

    // Remove callback
    logCallbacksRef.current.delete(nodeId)

    // Send unsubscription message
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ action: 'unsubscribe_logs', node_id: nodeId })
      wsRef.current.send(message)
    }
  }, [])

  // Connect on mount - only once
  useEffect(() => {
    // Use a small delay to handle React Strict Mode's double-invocation
    // This prevents the "WebSocket closed before connection established" error
    const mountTimeoutRef = setTimeout(() => {
      shouldReconnectRef.current = true
      connect()
    }, 0)

    // Cleanup on unmount
    return () => {
      clearTimeout(mountTimeoutRef)
      
      // Only log and cleanup if we actually had a connection attempt
      if (wsRef.current || isConnectingRef.current) {
        console.log('[WebSocket] Cleaning up')
      }
      
      shouldReconnectRef.current = false
      isConnectingRef.current = false

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }

      if (wsRef.current) {
        // Silently close - don't trigger reconnect logic
        const ws = wsRef.current
        wsRef.current = null
        ws.onclose = null // Remove handler to prevent reconnect
        ws.onerror = null
        ws.close()
      }
    }
  }, []) // Empty dependency array - only run on mount/unmount

  return {
    isConnected,
    lastMessage,
    clusterState,
    sendMessage,
    reconnect,
    subscribeToNodeLogs,
    unsubscribeFromNodeLogs,
  }
}
