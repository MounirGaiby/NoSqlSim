import { useEffect } from 'react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { ClusterTopology } from './components/ClusterTopology/ClusterTopology'
import { ControlPanel } from './components/ControlPanel/ControlPanel'
import { QueryInterface } from './components/QueryInterface/QueryInterface'
import { clusterApi } from './api/cluster'
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

  // WebSocket for real-time updates
  const { isConnected, clusterState: wsClusterState, reconnect } = useWebSocket((state) => {
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

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-left">
            <h1>NoSqlSim</h1>
            <p className="subtitle">MongoDB Replication & Consistency Simulator</p>
          </div>
          <div className="header-right">
            <div className="credits">
              <p>Created by: Mounir Gaiby, Amine Banan | Prof Hanin</p>
              <p>3CI Big Data & AI | NoSQL Module | ISGA 2025/2026</p>
            </div>
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

        <div className="app-layout">
          <div className="main-content">
            <ClusterTopology replicaSet={firstReplicaSet} width={700} height={380} />

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
