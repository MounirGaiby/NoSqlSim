import { useEffect, useCallback } from 'react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { ClusterTopology } from './components/ClusterTopology/ClusterTopology'
import { ControlPanel } from './components/ControlPanel/ControlPanel'
import { QueryInterface } from './components/QueryInterface/QueryInterface'
import { CAPTheorem } from './components/CAPTheorem/CAPTheorem'
import { ToastContainer, useToast } from './components/Toast/Toast'
import { clusterApi } from './api/cluster'
import { failuresApi } from './api/failures'
import { useClusterStore } from './hooks/useClusterState'
import { useWebSocket } from './hooks/useWebSocket'
import './styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function AppContent() {
  const { clusterState, setClusterState, setLoading, setError } = useClusterStore()
  const { toasts, dismissToast, success: showSuccess, error: showError } = useToast()

  // Node action handlers
  const handleCrashNode = useCallback(async (nodeId: string) => {
    try {
      await failuresApi.crashNode({ node_id: nodeId, crash_type: 'hard' })
      showSuccess('Node Crashed', `Node ${nodeId} has been crashed`)
    } catch (err) {
      showError('Crash Failed', err instanceof Error ? err.message : 'Unknown error')
    }
  }, [showSuccess, showError])

  const handleRestoreNode = useCallback(async (nodeId: string) => {
    try {
      await failuresApi.restoreNode({ node_id: nodeId })
      showSuccess('Node Restored', `Node ${nodeId} has been restored`)
    } catch (err) {
      showError('Restore Failed', err instanceof Error ? err.message : 'Unknown error')
    }
  }, [showSuccess, showError])

  const handleDeleteNode = useCallback(async (nodeId: string) => {
    const replicaSetName = Object.values(clusterState?.replica_sets || {})[0]?.set_name
    if (!replicaSetName) return
    try {
      await clusterApi.removeNode(nodeId, replicaSetName)
      showSuccess('Node Removed', `Node ${nodeId} removed from replica set`)
    } catch (err) {
      showError('Remove Failed', err instanceof Error ? err.message : 'Unknown error')
    }
  }, [clusterState, showSuccess, showError])

  // WebSocket for real-time updates
  const { isConnected, reconnect } = useWebSocket((state) => {
    // Update store when WebSocket receives cluster state
    // state is already the full ClusterState object
    setClusterState(state)
  })

  // Fallback: Poll cluster status only when WebSocket is disconnected
  const { data, isLoading, error, isError } = useQuery({
    queryKey: ['cluster-status'],
    queryFn: clusterApi.getClusterStatus,
    refetchInterval: isConnected ? false : 2000, // Only poll if WebSocket disconnected
    enabled: !isConnected, // Only enable when WebSocket is disconnected
  })

  // Update store when polling data changes (fallback mode)
  useEffect(() => {
    if (!isConnected && data) {
      setClusterState(data)
      setLoading(false)
    }
  }, [data, isConnected, setClusterState, setLoading])

  useEffect(() => {
    setLoading(isLoading)
  }, [isLoading, setLoading])

  useEffect(() => {
    if (isError) {
      setError(error?.message || 'Failed to fetch cluster status')
    }
  }, [isError, error, setError])

  // Get first replica set (for now, we only support one)
  const replicaSets = Object.values(clusterState?.replica_sets || {})
  const firstReplicaSet = replicaSets[0] || null
  const hasCluster = replicaSets.length > 0

  // Check for active network partitions
  const hasActivePartition = (clusterState?.active_failures || []).some(
    failureId => failureId.startsWith('partition-')
  )

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-left">
            <h1>NoSqlSim</h1>
            <p className="subtitle">MongoDB Replication & Consistency Simulator</p>
          </div>
        </div>
      </header>

      <main className="app-main">
        {!hasCluster && (
          <div className="welcome-banner">
            <h2>Welcome to NoSqlSim</h2>
            <p>
              An educational simulation tool for understanding MongoDB replication and
              consistency models.
            </p>
            <p className="instruction">
              Use the control panel to initialize your first replica set and begin exploring!
            </p>
          </div>
        )}

        {hasActivePartition && clusterState?.active_partitions && clusterState.active_partitions.length > 0 && (
          <div className="partition-warning">
            <strong>Network Partition Active</strong>
            <p>
              Group A: {clusterState.active_partitions[0].group_a.join(', ')} |
              Group B: {clusterState.active_partitions[0].group_b.join(', ')}
            </p>
            <p className="partition-hint">
              Only the majority group can accept writes (CP behavior).
            </p>
          </div>
        )}

        <div className="app-layout">
          <div className="main-content">
            <ClusterTopology
              replicaSet={firstReplicaSet}
              width={700}
              height={380}
              activePartitions={clusterState?.active_partitions || []}
              isLoading={isLoading}
              onCrashNode={handleCrashNode}
              onRestoreNode={handleRestoreNode}
              onDeleteNode={handleDeleteNode}
            />

            {hasCluster && firstReplicaSet && (
              <div className="cluster-info">
                <h3>Cluster Information</h3>
                <div className="info-grid">
                  <div className="info-card">
                    <span className="info-label">Replica Set:</span>
                    <span className="info-value">{firstReplicaSet.set_name}</span>
                  </div>
                  <div className="info-card">
                    <span className="info-label">Health:</span>
                    <span className={`info-value health-${firstReplicaSet.health}`}>
                      {firstReplicaSet.health ? firstReplicaSet.health.toUpperCase() : 'UNKNOWN'}
                    </span>
                  </div>
                  <div className="info-card">
                    <span className="info-label">Total Nodes:</span>
                    <span className="info-value">{firstReplicaSet.members.length}</span>
                  </div>
                  <div className="info-card">
                    <span className="info-label">Primary:</span>
                    <span className="info-value">
                      {firstReplicaSet.primary || 'None (Election in progress)'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {hasCluster && <CAPTheorem />}

            {hasCluster && firstReplicaSet && (
              <QueryInterface replicaSetName={firstReplicaSet.set_name} />
            )}
          </div>

          <aside className="sidebar">
            <ControlPanel
              hasCluster={hasCluster}
              replicaSetName={firstReplicaSet?.set_name || null}
              nodes={firstReplicaSet?.members || []}
            />

            <div className={`connection-status ${isError ? 'error' : isConnected ? 'success' : 'warning'}`}>
              <strong>
                <span className="status-icon"></span>
                {isError ? 'Connection Error' : isConnected ? 'Connected' : 'Reconnecting...'}
              </strong>
              {isError ? (
                <span>Backend unavailable</span>
              ) : (
                <span>{isConnected ? 'WebSocket' : 'Polling'}</span>
              )}
              {!isConnected && !isError && (
                <button onClick={reconnect} className="btn-sm btn-ghost">
                  Retry
                </button>
              )}
            </div>
          </aside>
        </div>
      </main>

      <footer className="app-footer">
        <p>NoSqlSim v1.0.0 - Educational Tool for MongoDB Concepts</p>
      </footer>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}

export default App
