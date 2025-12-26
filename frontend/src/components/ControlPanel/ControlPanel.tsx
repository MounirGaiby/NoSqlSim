import { useState, useEffect, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clusterApi } from '../../api/cluster'
import { failuresApi } from '../../api/failures'
import { useWebSocket } from '../../hooks/useWebSocket'
import type { InitClusterRequest, MemberStatus } from '../../types/cluster'
import './ControlPanel.css'

interface ControlPanelProps {
  hasCluster: boolean
  replicaSetName: string | null
  nodes?: MemberStatus[]
}

export function ControlPanel({ hasCluster, replicaSetName, nodes = [] }: ControlPanelProps) {
  const queryClient = useQueryClient()
  const { subscribeToNodeLogs, unsubscribeFromNodeLogs, isConnected } = useWebSocket()
  const [showInitForm, setShowInitForm] = useState(!hasCluster)
  const [selectedNode, setSelectedNode] = useState<string>('')

  // Logs state
  const [logsNodeId, setLogsNodeId] = useState<string>('')
  const [logs, setLogs] = useState<string>('')
  const [autoScroll, setAutoScroll] = useState(true)
  const logsContainerRef = useRef<HTMLDivElement>(null)

  // Node type for adding
  const [nodeType, setNodeType] = useState<'replica' | 'arbiter'>('replica')

  // Partition state
  const [partitionGroupA, setPartitionGroupA] = useState<string[]>([])
  const [partitionGroupB, setPartitionGroupB] = useState<string[]>([])

  // Form state
  const [formData, setFormData] = useState<InitClusterRequest>({
    replica_set_name: 'rs0',
    node_count: 3,
    starting_port: 27017,
  })

  // Initialize cluster mutation
  const initMutation = useMutation({
    mutationFn: (data: InitClusterRequest) => clusterApi.initCluster(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
      setShowInitForm(false)
    },
  })

  // Add node mutation
  const addNodeMutation = useMutation({
    mutationFn: () =>
      clusterApi.addNode({
        replica_set_name: replicaSetName!,
        role: nodeType,
        priority: nodeType === 'replica' ? 1 : 0,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
      // Reset to replica for next addition
      setNodeType('replica')
    },
  })

  // Remove node mutation
  const removeNodeMutation = useMutation({
    mutationFn: (nodeId: string) =>
      clusterApi.removeNode(nodeId, replicaSetName!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
      setSelectedNode('')
    },
  })

  // Step down primary mutation
  const stepDownMutation = useMutation({
    mutationFn: () =>
      clusterApi.stepDownPrimary({
        replica_set_name: replicaSetName!,
        step_down_secs: 60,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
    },
  })

  // Crash node mutation
  const crashNodeMutation = useMutation({
    mutationFn: (nodeId: string) =>
      failuresApi.crashNode({
        node_id: nodeId,
        crash_type: 'clean',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
    },
  })

  // Restore node mutation
  const restoreNodeMutation = useMutation({
    mutationFn: (nodeId: string) =>
      failuresApi.restoreNode({ node_id: nodeId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
    },
  })

  // Create partition mutation
  const createPartitionMutation = useMutation({
    mutationFn: () =>
      failuresApi.createPartition({
        replica_set_name: replicaSetName!,
        group_a: partitionGroupA,
        group_b: partitionGroupB,
        description: `Partition: [${partitionGroupA.join(', ')}] vs [${partitionGroupB.join(', ')}]`,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
      alert('Network partition created successfully!')
      setPartitionGroupA([])
      setPartitionGroupB([])
    },
    onError: (error: any) => {
      alert(`Failed to create partition: ${error.message}`)
    },
  })

  // Heal partitions mutation
  const healPartitionsMutation = useMutation({
    mutationFn: () => failuresApi.healPartitions(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-status'] })
      alert('Network partitions healed successfully!')
    },
    onError: (error: any) => {
      alert(`Failed to heal partitions: ${error.message}`)
    },
  })

  // Subscribe to logs when modal is open
  useEffect(() => {
    if (logs && logsNodeId) {
      // Modal is open, subscribe to logs
      subscribeToNodeLogs(logsNodeId, (newLogs: string) => {
        setLogs(newLogs)
      })

      return () => {
        // Cleanup: unsubscribe when modal closes
        unsubscribeFromNodeLogs(logsNodeId)
      }
    }
  }, [logs && logsNodeId]) // Re-subscribe if node changes

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  // Handle user scrolling (disable auto-scroll if user scrolls up)
  const handleLogsScroll = () => {
    if (logsContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 10
      if (!isAtBottom && autoScroll) {
        setAutoScroll(false)
      } else if (isAtBottom && !autoScroll) {
        setAutoScroll(true)
      }
    }
  }

  const handleInitSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    initMutation.mutate(formData)
  }

  const toggleNodeInPartition = (nodeId: string, partition: 'A' | 'B') => {
    if (partition === 'A') {
      if (partitionGroupA.includes(nodeId)) {
        setPartitionGroupA(partitionGroupA.filter((id) => id !== nodeId))
      } else {
        setPartitionGroupA([...partitionGroupA, nodeId])
        // Remove from group B if present
        setPartitionGroupB(partitionGroupB.filter((id) => id !== nodeId))
      }
    } else {
      if (partitionGroupB.includes(nodeId)) {
        setPartitionGroupB(partitionGroupB.filter((id) => id !== nodeId))
      } else {
        setPartitionGroupB([...partitionGroupB, nodeId])
        // Remove from group A if present
        setPartitionGroupA(partitionGroupA.filter((id) => id !== nodeId))
      }
    }
  }

  const canCreatePartition = partitionGroupA.length > 0 && partitionGroupB.length > 0

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'replica_set_name' ? value : parseInt(value, 10),
    }))
  }

  return (
    <div className="control-panel">
      <h2>Control Panel</h2>

      {!hasCluster && showInitForm && (
        <div className="init-form-container">
          <h3>Initialize Replica Set</h3>
          <form onSubmit={handleInitSubmit} className="init-form">
            <div className="form-group">
              <label htmlFor="replica_set_name">Replica Set Name:</label>
              <input
                type="text"
                id="replica_set_name"
                name="replica_set_name"
                value={formData.replica_set_name}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="node_count">Number of Nodes:</label>
              <input
                type="number"
                id="node_count"
                name="node_count"
                value={formData.node_count}
                onChange={handleInputChange}
                min="1"
                max="7"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="starting_port">Starting Port:</label>
              <input
                type="number"
                id="starting_port"
                name="starting_port"
                value={formData.starting_port}
                onChange={handleInputChange}
                min="27017"
                max="27100"
                required
              />
            </div>

            <button
              type="submit"
              disabled={initMutation.isPending}
              className="btn-primary"
            >
              {initMutation.isPending ? 'Initializing...' : 'Initialize Cluster'}
            </button>

            {initMutation.isError && (
              <div className="error-message">
                Error: {(initMutation.error as Error).message}
              </div>
            )}

            {initMutation.isSuccess && (
              <div className="success-message">
                Cluster initialized successfully! Wait a few seconds for nodes to start.
              </div>
            )}
          </form>
        </div>
      )}

      {hasCluster && (
        <div className="cluster-controls">
          <h3>Cluster Operations</h3>

          <div className="control-section">
            <h4>Node Management</h4>
            <div className="form-group">
              <label>Node Type</label>
              <select
                value={nodeType}
                onChange={(e) => setNodeType(e.target.value as 'replica' | 'arbiter')}
                disabled={addNodeMutation.isPending}
              >
                <option value="replica">Secondary (Data-bearing)</option>
                <option value="arbiter">Arbiter (Vote-only)</option>
              </select>
            </div>
            <button
              onClick={() => addNodeMutation.mutate()}
              disabled={addNodeMutation.isPending || !replicaSetName}
              className="btn-secondary"
            >
              {addNodeMutation.isPending ? 'Adding...' : `Add ${nodeType === 'arbiter' ? 'Arbiter' : 'Secondary'} Node`}
            </button>

            {addNodeMutation.isError && (
              <div className="error-message">
                Error: {(addNodeMutation.error as Error).message}
              </div>
            )}
          </div>

          <div className="control-section">
            <h4>Election Control</h4>
            <button
              onClick={() => stepDownMutation.mutate()}
              disabled={stepDownMutation.isPending || !replicaSetName}
              className="btn-warning"
            >
              {stepDownMutation.isPending ? 'Stepping Down...' : 'Step Down Primary'}
            </button>
            <p className="control-hint">
              Forces the primary to step down and triggers a new election
            </p>

            {stepDownMutation.isError && (
              <div className="error-message">
                Error: {(stepDownMutation.error as Error).message}
              </div>
            )}
          </div>

          <div className="control-section">
            <h4>Failure Simulation</h4>
            <div className="form-group">
              <label htmlFor="node-selector">Select Node:</label>
              <select
                id="node-selector"
                value={selectedNode}
                onChange={(e) => setSelectedNode(e.target.value)}
                disabled={nodes.length === 0}
              >
                <option value="">-- Select a node --</option>
                {nodes.map((node) => (
                  <option key={node.node_id} value={node.node_id}>
                    {node.node_id} ({node.state_str})
                  </option>
                ))}
              </select>
            </div>

            <div className="button-group">
              <button
                onClick={() => selectedNode && crashNodeMutation.mutate(selectedNode)}
                disabled={!selectedNode || crashNodeMutation.isPending}
                className="btn-danger"
              >
                {crashNodeMutation.isPending ? 'Crashing...' : 'Crash Node'}
              </button>

              <button
                onClick={() => selectedNode && restoreNodeMutation.mutate(selectedNode)}
                disabled={!selectedNode || restoreNodeMutation.isPending}
                className="btn-success"
              >
                {restoreNodeMutation.isPending ? 'Restoring...' : 'Restore Node'}
              </button>

              <button
                onClick={() => selectedNode && removeNodeMutation.mutate(selectedNode)}
                disabled={!selectedNode || removeNodeMutation.isPending || nodes.length <= 1}
                className="btn-danger"
              >
                {removeNodeMutation.isPending ? 'Removing...' : 'Remove Node'}
              </button>
            </div>

            <p className="control-hint">
              Crash: Stops the container. Restore: Starts it again. Remove: Permanently removes from cluster.
            </p>

            {crashNodeMutation.isError && (
              <div className="error-message">
                Error: {(crashNodeMutation.error as Error).message}
              </div>
            )}
            {restoreNodeMutation.isError && (
              <div className="error-message">
                Error: {(restoreNodeMutation.error as Error).message}
              </div>
            )}
            {removeNodeMutation.isError && (
              <div className="error-message">
                Error: {(removeNodeMutation.error as Error).message}
              </div>
            )}
          </div>

          {/* Network Partitions (CAP) - Hidden for now
          <div className="control-section">
            <h4>Network Partitions (CAP Theorem)</h4>
            <p className="control-hint">
              Create a network partition to demonstrate CAP theorem. Select nodes for each isolated group.
            </p>

            <div className="partition-groups">
              <div className="partition-group">
                <h5>Group A (Majority)</h5>
                <div className="node-checkboxes">
                  {nodes.map((node) => (
                    <label key={`a-${node.node_id}`} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={partitionGroupA.includes(node.node_id)}
                        onChange={() => toggleNodeInPartition(node.node_id, 'A')}
                      />
                      <span>{node.node_id}</span>
                    </label>
                  ))}
                </div>
                <p className="group-count">
                  Selected: {partitionGroupA.length} node{partitionGroupA.length !== 1 ? 's' : ''}
                </p>
              </div>

              <div className="partition-divider">vs</div>

              <div className="partition-group">
                <h5>Group B (Minority)</h5>
                <div className="node-checkboxes">
                  {nodes.map((node) => (
                    <label key={`b-${node.node_id}`} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={partitionGroupB.includes(node.node_id)}
                        onChange={() => toggleNodeInPartition(node.node_id, 'B')}
                      />
                      <span>{node.node_id}</span>
                    </label>
                  ))}
                </div>
                <p className="group-count">
                  Selected: {partitionGroupB.length} node{partitionGroupB.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>

            <div className="button-group">
              <button
                onClick={() => createPartitionMutation.mutate()}
                disabled={!canCreatePartition || createPartitionMutation.isPending || nodes.length < 3}
                className="btn-warning"
              >
                {createPartitionMutation.isPending ? 'Creating...' : 'Create Partition'}
              </button>

              <button
                onClick={() => healPartitionsMutation.mutate()}
                disabled={healPartitionsMutation.isPending}
                className="btn-success"
              >
                {healPartitionsMutation.isPending ? 'Healing...' : 'Heal Partition'}
              </button>
            </div>

            <p className="control-hint">
              Tip: Create a 3-2 split (majority vs minority) to observe CAP theorem: writes to minority will fail!
            </p>
          </div>
          */}

          <div className="control-section">
            <h4>Node Logs</h4>
            <div className="form-group">
                <label htmlFor="logs-node-selector">Select Node:</label>
                <select
                    id="logs-node-selector"
                    value={logsNodeId}
                    onChange={(e) => setLogsNodeId(e.target.value)}
                >
                    <option value="">-- Select a node --</option>
                    {nodes.map((node) => (
                        <option key={node.node_id} value={node.node_id}>
                            {node.node_id}
                        </option>
                    ))}
                </select>
            </div>
            <button
                onClick={async () => {
                  if (logsNodeId) {
                    // Fetch initial logs then open modal
                    try {
                      const data = await clusterApi.getNodeLogs(logsNodeId)
                      setLogs(data.logs)
                    } catch (error: any) {
                      alert(`Failed to fetch logs: ${error.message}`)
                    }
                  }
                }}
                disabled={!logsNodeId || !isConnected}
                className="btn-secondary"
            >
                View Logs
            </button>
          </div>

          {/* Logs Modal */}
          {logs && (
            <div className="modal-overlay" onClick={() => setLogs('')}>
              <div className="modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Logs: {logsNodeId}</h3>
                  <button className="modal-close" onClick={() => setLogs('')}>×</button>
                </div>
                <div className="modal-body">
                  <div className="logs-container">
                    <div className="logs-header">
                      <h4>Container Output</h4>
                      <div className="logs-controls">
                        {isConnected && (
                          <span className="streaming-indicator">
                            <span className="streaming-dot"></span>
                            Live
                          </span>
                        )}
                        <label className="auto-scroll-toggle">
                          <input
                            type="checkbox"
                            checked={autoScroll}
                            onChange={(e) => setAutoScroll(e.target.checked)}
                          />
                          Auto-scroll
                        </label>
                      </div>
                    </div>
                    <div
                      ref={logsContainerRef}
                      className="logs-content"
                      onScroll={handleLogsScroll}
                    >
                      {logs}
                    </div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn-ghost" onClick={() => setLogs('')}>Close</button>
                </div>
              </div>
            </div>
          )}

          <div className="control-section">
            <h4>Information</h4>
            <p className="info-text">
              Active Replica Set: <strong>{replicaSetName}</strong>
            </p>
            <p className="info-text">
              Total Nodes: <strong>{nodes.length}</strong>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
