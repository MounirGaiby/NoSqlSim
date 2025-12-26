import { useEffect, useRef, useState, useCallback } from 'react'
import type { ReplicaSetStatus, MemberStatus } from '../../types/cluster'
import { 
  drawClusterTopology, 
  calculateNodePositions, 
  NODE_RADIUS,
  type AnimationState,
  type ReplicationFlow 
} from '../../utils/canvas'
import './ClusterTopology.css'

interface ClusterTopologyProps {
  replicaSet: ReplicaSetStatus | null
  width?: number
  height?: number
}

export function ClusterTopology({ replicaSet, width = 700, height = 450 }: ClusterTopologyProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number | null>(null)
  const [hoveredNode, setHoveredNode] = useState<MemberStatus | null>(null)
  const [selectedNode, setSelectedNode] = useState<MemberStatus | null>(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  // Animation controls
  const [showHeartbeats, setShowHeartbeats] = useState(true)
  const [showReplication, setShowReplication] = useState(true)
  
  // Animation state (simplified - no election stuff)
  const [animationState, setAnimationState] = useState<AnimationState>({
    electionInProgress: false,
    electionPhase: 'idle',
    votingNode: null,
    votes: new Map(),
    term: 1,
    heartbeats: new Map(),
    replicationFlows: [],
    timestamp: Date.now(),
  })

  // Previous state tracking
  const prevPrimaryRef = useRef<string | null>(null)
  const prevMemberIdsRef = useRef<string[]>([])

  // Generate replication flows from primary to all healthy secondaries
  const generateReplicationFlows = useCallback((members: MemberStatus[], primary: string | null): ReplicationFlow[] => {
    if (!primary) return []
    
    const flows: ReplicationFlow[] = []
    const primaryNode = members.find(m => m.node_id === primary || m.name === primary)
    
    if (!primaryNode || primaryNode.health !== 1) return []
    
    members.forEach(member => {
      const isPrimary = member.node_id === primary || member.name === primary
      const isArbiter = member.state_str.toUpperCase() === 'ARBITER'
      const isHealthy = member.health === 1
      const isSecondary = member.state_str.toUpperCase() === 'SECONDARY'
      
      if (!isPrimary && isHealthy && !isArbiter && isSecondary) {
        flows.push({
          fromNode: primaryNode.node_id,
          toNode: member.node_id,
          progress: Math.random(),
          color: '#10b981',
        })
      }
    })
    
    return flows
  }, [])

  // Regenerate flows when members change or primary changes
  useEffect(() => {
    if (!replicaSet || !showReplication) return
    
    const memberIds = replicaSet.members.map(m => m.node_id).sort()
    const memberIdsStr = memberIds.join(',')
    const prevIdsStr = prevMemberIdsRef.current.join(',')
    
    const membersChanged = memberIdsStr !== prevIdsStr
    const primaryChanged = prevPrimaryRef.current !== null && prevPrimaryRef.current !== replicaSet.primary
    
    if (membersChanged || primaryChanged) {
      const newFlows = generateReplicationFlows(replicaSet.members, replicaSet.primary)
      setAnimationState(prev => ({
        ...prev,
        replicationFlows: newFlows,
      }))
    }
    
    prevMemberIdsRef.current = memberIds
    prevPrimaryRef.current = replicaSet.primary
  }, [replicaSet?.members, replicaSet?.primary, showReplication, generateReplicationFlows])

  // Animation loop
  useEffect(() => {
    if (!replicaSet) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
        animationRef.current = null
      }
      return
    }

    let lastTime = performance.now()

    const animate = (currentTime: number) => {
      const deltaTime = currentTime - lastTime
      lastTime = currentTime

      setAnimationState(prev => {
        const newHeartbeats = new Map(prev.heartbeats)
        let newFlows = [...prev.replicationFlows]
        
        if (showHeartbeats) {
          replicaSet.members.forEach(member => {
            if (member.health === 1) {
              const current = newHeartbeats.get(member.node_id) || 0
              const newValue = (current + deltaTime * 0.0005) % 1
              newHeartbeats.set(member.node_id, newValue)
            } else {
              newHeartbeats.delete(member.node_id)
            }
          })
        }
        
        if (showReplication) {
          if (newFlows.length === 0 && replicaSet.primary) {
            newFlows = generateReplicationFlows(replicaSet.members, replicaSet.primary)
          } else {
            newFlows = newFlows.map(flow => ({
              ...flow,
              progress: (flow.progress + deltaTime * 0.00035) % 1
            }))
          }
        } else {
          newFlows = []
        }
        
        return {
          ...prev,
          heartbeats: newHeartbeats,
          replicationFlows: newFlows,
          timestamp: Date.now(),
        }
      })

      animationRef.current = requestAnimationFrame(animate)
    }

    animationRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [replicaSet, showHeartbeats, showReplication, generateReplicationFlows])

  // Draw canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = width
    canvas.height = height

    if (!replicaSet) {
      const gradient = ctx.createRadialGradient(
        width / 2, height / 2, 0,
        width / 2, height / 2, Math.max(width, height) / 1.5
      )
      gradient.addColorStop(0, '#1a2332')
      gradient.addColorStop(1, '#0f1419')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, width, height)
      
      ctx.fillStyle = '#94a3b8'
      ctx.font = '18px Inter, sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('Initialize a replica set to begin', width / 2, height / 2)
      return
    }

    drawClusterTopology(
      ctx,
      replicaSet.members,
      replicaSet.primary,
      width,
      height,
      animationState
    )
  }, [replicaSet, width, height, animationState])

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !replicaSet) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    setMousePos({ x: e.clientX, y: e.clientY })

    const positions = calculateNodePositions(replicaSet.members, width, height)

    let foundNode: MemberStatus | null = null
    for (const pos of positions) {
      const dx = x - pos.x
      const dy = y - pos.y
      const distance = Math.sqrt(dx * dx + dy * dy)

      if (distance <= NODE_RADIUS) {
        foundNode = pos.node
        break
      }
    }

    setHoveredNode(foundNode)
    canvas.style.cursor = foundNode ? 'pointer' : 'default'
  }

  const handleClick = () => {
    if (hoveredNode) {
      setSelectedNode(selectedNode?.node_id === hoveredNode.node_id ? null : hoveredNode)
    }
  }

  return (
    <div className="cluster-topology">
      <div className="topology-header">
        <div className="header-left">
          <h2>Cluster Topology</h2>
          {replicaSet && (
            <div className="topology-badges">
              <span className="replica-set-name">{replicaSet.set_name}</span>
              <span className={`health-badge health-${replicaSet.health}`}>
                {replicaSet.health.toUpperCase()}
              </span>
            </div>
          )}
        </div>
        
      </div>

      <div className="canvas-container">
        <canvas
          ref={canvasRef}
          className="topology-canvas"
          onMouseMove={handleMouseMove}
          onClick={handleClick}
          onMouseLeave={() => setHoveredNode(null)}
        />

        {replicaSet && (
          <div className="animation-controls">
            <div className="control-group">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={showHeartbeats}
                  onChange={(e) => setShowHeartbeats(e.target.checked)}
                />
                <span className="toggle-text">Heartbeats</span>
              </label>
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={showReplication}
                  onChange={(e) => setShowReplication(e.target.checked)}
                />
                <span className="toggle-text">Replication</span>
              </label>
            </div>
          </div>
        )}

        {replicaSet?.primary && (
          <div className="primary-badge">
            <span className="primary-dot"></span>
            Primary: {replicaSet.primary}
          </div>
        )}

        {hoveredNode && !selectedNode && (
          <div
            className="node-tooltip"
            style={{
              left: mousePos.x + 15,
              top: mousePos.y + 15,
            }}
          >
            <strong>{hoveredNode.node_id}</strong>
            <div>State: {hoveredNode.state_str}</div>
            <div>Health: {hoveredNode.health === 1 ? 'Healthy' : 'Down'}</div>
            <div className="tooltip-hint">Click for details</div>
          </div>
        )}

        {selectedNode && (
          <div className="node-details-panel">
            <div className="panel-header">
              <h4>{selectedNode.node_id}</h4>
              <button
                className="close-btn"
                onClick={() => setSelectedNode(null)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="panel-content">
              <div className="detail-row">
                <span className="detail-label">Name:</span>
                <span className="detail-value">{selectedNode.name}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">State:</span>
                <span className={`detail-value state-${selectedNode.state_str.toLowerCase()}`}>
                  {selectedNode.state_str}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Health:</span>
                <span className={`detail-value ${selectedNode.health === 1 ? 'healthy' : 'unhealthy'}`}>
                  {selectedNode.health === 1 ? 'Healthy' : 'Down'}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Uptime:</span>
                <span className="detail-value">{Math.floor(selectedNode.uptime / 60)} minutes</span>
              </div>
              {selectedNode.ping_ms !== undefined && selectedNode.ping_ms !== null && (
                <div className="detail-row">
                  <span className="detail-label">Ping:</span>
                  <span className="detail-value">{selectedNode.ping_ms}ms</span>
                </div>
              )}
              {selectedNode.last_heartbeat && (
                <div className="detail-row">
                  <span className="detail-label">Last Heartbeat:</span>
                  <span className="detail-value">
                    {new Date(selectedNode.last_heartbeat).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="topology-legend">
        <div className="legend-item">
          <span className="legend-color primary"></span>
          <span>Primary</span>
        </div>
        <div className="legend-item">
          <span className="legend-color secondary"></span>
          <span>Secondary</span>
        </div>
        <div className="legend-item">
          <span className="legend-color arbiter"></span>
          <span>Arbiter</span>
        </div>
        <div className="legend-item">
          <span className="legend-color down"></span>
          <span>Down</span>
        </div>
      </div>
    </div>
  )
}
