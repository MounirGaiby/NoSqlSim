import type { MemberStatus } from '../types/cluster'

export interface NodePosition {
  x: number
  y: number
  node: MemberStatus
}

// Animation state interface
export interface AnimationState {
  electionInProgress: boolean
  electionPhase: 'idle' | 'voting' | 'counting' | 'elected'
  votingNode: string | null
  votes: Map<string, string> // voter -> candidate
  term: number
  heartbeats: Map<string, number> // nodeId -> animation progress (0-1)
  replicationFlows: ReplicationFlow[]
  timestamp: number
}

export interface ReplicationFlow {
  fromNode: string
  toNode: string
  progress: number // 0-1
  color: string
}

export interface VoteAnimation {
  from: { x: number; y: number }
  to: { x: number; y: number }
  progress: number
  voter: string
  candidate: string
}

// Dark theme colors
export const CANVAS_COLORS = {
  background: '#0f1419',
  backgroundGradientStart: '#0f1419',
  backgroundGradientEnd: '#1a2332',
  gridLine: 'rgba(255, 255, 255, 0.03)',
  connectionDefault: 'rgba(75, 85, 99, 0.4)',
  connectionActive: 'rgba(16, 163, 127, 0.6)',
  connectionReplication: '#10a37f',
  connectionBlocked: 'rgba(239, 68, 68, 0.6)',
  text: '#e2e8f0',
  textMuted: '#94a3b8',
  textDark: '#1a1a2e',
} as const

export const NODE_COLORS = {
  PRIMARY: {
    fill: '#10b981',
    gradient: ['#10b981', '#059669'],
    glow: 'rgba(16, 185, 129, 0.5)',
    border: '#34d399',
  },
  SECONDARY: {
    fill: '#3b82f6',
    gradient: ['#3b82f6', '#2563eb'],
    glow: 'rgba(59, 130, 246, 0.4)',
    border: '#60a5fa',
  },
  ARBITER: {
    fill: '#8b5cf6',
    gradient: ['#8b5cf6', '#7c3aed'],
    glow: 'rgba(139, 92, 246, 0.4)',
    border: '#a78bfa',
  },
  DOWN: {
    fill: '#ef4444',
    gradient: ['#ef4444', '#dc2626'],
    glow: 'rgba(239, 68, 68, 0.4)',
    border: '#f87171',
  },
  RECOVERING: {
    fill: '#f59e0b',
    gradient: ['#f59e0b', '#d97706'],
    glow: 'rgba(245, 158, 11, 0.4)',
    border: '#fbbf24',
  },
  UNKNOWN: {
    fill: '#6b7280',
    gradient: ['#6b7280', '#4b5563'],
    glow: 'rgba(107, 114, 128, 0.3)',
    border: '#9ca3af',
  },
  VOTING: {
    fill: '#ec4899',
    gradient: ['#ec4899', '#db2777'],
    glow: 'rgba(236, 72, 153, 0.6)',
    border: '#f472b6',
  },
} as const

export const NODE_RADIUS = 40
export const NODE_LABEL_OFFSET = 55
export const CONNECTION_WIDTH = 2
export const REPLICATION_PARTICLE_SIZE = 6

/**
 * Get color config for a node based on its state
 */
export function getNodeColorConfig(state: string, isVoting: boolean = false) {
  if (isVoting) return NODE_COLORS.VOTING
  
  const stateUpper = state.toUpperCase()

  if (stateUpper === 'PRIMARY') return NODE_COLORS.PRIMARY
  if (stateUpper === 'SECONDARY') return NODE_COLORS.SECONDARY
  if (stateUpper === 'ARBITER') return NODE_COLORS.ARBITER
  if (stateUpper === 'RECOVERING') return NODE_COLORS.RECOVERING
  if (stateUpper === 'DOWN' || stateUpper === 'UNKNOWN') return NODE_COLORS.DOWN

  return NODE_COLORS.UNKNOWN
}

/**
 * Calculate positions for nodes in a circular layout
 */
export function calculateNodePositions(
  nodes: MemberStatus[],
  canvasWidth: number,
  canvasHeight: number
): NodePosition[] {
  const centerX = canvasWidth / 2
  const centerY = canvasHeight / 2
  const radius = Math.min(canvasWidth, canvasHeight) / 3

  // Single node - center it
  if (nodes.length === 1) {
    return [{ x: centerX, y: centerY, node: nodes[0] }]
  }

  // Multiple nodes - circular layout
  const angleStep = (2 * Math.PI) / nodes.length
  const startAngle = -Math.PI / 2 // Start from top

  return nodes.map((node, index) => {
    const angle = startAngle + angleStep * index
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
      node,
    }
  })
}

/**
 * Draw background with gradient and subtle grid
 */
export function drawBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number
) {
  // Create radial gradient background
  const gradient = ctx.createRadialGradient(
    width / 2, height / 2, 0,
    width / 2, height / 2, Math.max(width, height) / 1.5
  )
  gradient.addColorStop(0, CANVAS_COLORS.backgroundGradientEnd)
  gradient.addColorStop(1, CANVAS_COLORS.backgroundGradientStart)
  
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, width, height)

  // Draw subtle grid
  ctx.strokeStyle = CANVAS_COLORS.gridLine
  ctx.lineWidth = 1
  const gridSize = 40

  for (let x = 0; x < width; x += gridSize) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }

  for (let y = 0; y < height; y += gridSize) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }
}

/**
 * Draw a connection line between two nodes with optional animation
 */
export function drawConnection(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  isActive: boolean = false,
  animationProgress: number = 0,
  isBlocked: boolean = false
) {
  // Draw blocked connection (partitioned)
  if (isBlocked) {
    ctx.strokeStyle = CANVAS_COLORS.connectionBlocked
    ctx.lineWidth = 2
    ctx.setLineDash([8, 8])
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
    ctx.setLineDash([])

    // Draw X mark in the middle to indicate blocked
    const midX = (x1 + x2) / 2
    const midY = (y1 + y2) / 2
    const markSize = 8

    ctx.strokeStyle = '#ef4444'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.moveTo(midX - markSize, midY - markSize)
    ctx.lineTo(midX + markSize, midY + markSize)
    ctx.moveTo(midX + markSize, midY - markSize)
    ctx.lineTo(midX - markSize, midY + markSize)
    ctx.stroke()

    // Draw circle background for the X
    ctx.fillStyle = 'rgba(239, 68, 68, 0.2)'
    ctx.beginPath()
    ctx.arc(midX, midY, markSize + 6, 0, 2 * Math.PI)
    ctx.fill()

    return
  }

  // Draw base connection
  ctx.strokeStyle = isActive ? CANVAS_COLORS.connectionActive : CANVAS_COLORS.connectionDefault
  ctx.lineWidth = isActive ? 3 : CONNECTION_WIDTH
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()

  // Draw animated particles for active connections
  if (isActive && animationProgress > 0) {
    const particlePos = animationProgress
    const px = x1 + (x2 - x1) * particlePos
    const py = y1 + (y2 - y1) * particlePos

    // Particle glow
    ctx.shadowColor = CANVAS_COLORS.connectionReplication
    ctx.shadowBlur = 10
    
    ctx.beginPath()
    ctx.arc(px, py, REPLICATION_PARTICLE_SIZE, 0, 2 * Math.PI)
    ctx.fillStyle = CANVAS_COLORS.connectionReplication
    ctx.fill()

    ctx.shadowBlur = 0
  }
}

/**
 * Draw replication flow animation
 */
export function drawReplicationFlow(
  ctx: CanvasRenderingContext2D,
  positions: NodePosition[],
  flow: ReplicationFlow
) {
  const fromPos = positions.find(p => p.node.node_id === flow.fromNode)
  const toPos = positions.find(p => p.node.node_id === flow.toNode)
  
  if (!fromPos || !toPos) return

  const x1 = fromPos.x
  const y1 = fromPos.y
  const x2 = toPos.x
  const y2 = toPos.y

  // Calculate particle position along the line
  const px = x1 + (x2 - x1) * flow.progress
  const py = y1 + (y2 - y1) * flow.progress

  // Draw glowing particle
  ctx.shadowColor = flow.color
  ctx.shadowBlur = 15
  
  ctx.beginPath()
  ctx.arc(px, py, REPLICATION_PARTICLE_SIZE, 0, 2 * Math.PI)
  ctx.fillStyle = flow.color
  ctx.fill()

  // Draw trail
  ctx.shadowBlur = 5
  const trailLength = 0.1
  const trailStart = Math.max(0, flow.progress - trailLength)
  
  const gradient = ctx.createLinearGradient(
    x1 + (x2 - x1) * trailStart,
    y1 + (y2 - y1) * trailStart,
    px, py
  )
  gradient.addColorStop(0, 'transparent')
  gradient.addColorStop(1, flow.color)
  
  ctx.strokeStyle = gradient
  ctx.lineWidth = 3
  ctx.beginPath()
  ctx.moveTo(x1 + (x2 - x1) * trailStart, y1 + (y2 - y1) * trailStart)
  ctx.lineTo(px, py)
  ctx.stroke()

  ctx.shadowBlur = 0
}

/**
 * Draw vote animation
 */
export function drawVoteAnimation(
  ctx: CanvasRenderingContext2D,
  vote: VoteAnimation
) {
  const px = vote.from.x + (vote.to.x - vote.from.x) * vote.progress
  const py = vote.from.y + (vote.to.y - vote.from.y) * vote.progress

  // Vote badge
  ctx.shadowColor = NODE_COLORS.VOTING.glow
  ctx.shadowBlur = 20

  // Draw vote symbol (checkmark in circle)
  ctx.beginPath()
  ctx.arc(px, py, 12, 0, 2 * Math.PI)
  ctx.fillStyle = NODE_COLORS.VOTING.fill
  ctx.fill()
  
  ctx.fillStyle = '#fff'
  ctx.font = 'bold 10px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('✓', px, py)

  ctx.shadowBlur = 0
}

/**
 * Draw a node on the canvas with enhanced styling
 */
export function drawNode(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  node: MemberStatus,
  isPrimary: boolean,
  isVoting: boolean = false,
  heartbeatPulse: number = 0,
  partitionGroup?: 'A' | 'B'
) {
  const colorConfig = getNodeColorConfig(node.state_str, isVoting)
  const isHealthy = node.health === 1
  const isArbiter = node.state_str.toUpperCase() === 'ARBITER'

  // Calculate pulse effect
  const pulseScale = 1 + (heartbeatPulse * 0.1)
  const pulseAlpha = 1 - heartbeatPulse * 0.5

  // Draw outer glow
  ctx.shadowColor = colorConfig.glow
  ctx.shadowBlur = isPrimary ? 30 : 15

  // Draw pulse ring for heartbeat
  if (heartbeatPulse > 0 && isHealthy) {
    ctx.beginPath()
    ctx.arc(x, y, NODE_RADIUS * pulseScale * 1.5, 0, 2 * Math.PI)
    ctx.strokeStyle = `rgba(${hexToRgb(colorConfig.fill)}, ${pulseAlpha * 0.5})`
    ctx.lineWidth = 3
    ctx.stroke()
  }

  // Create gradient fill
  const gradient = ctx.createRadialGradient(
    x - NODE_RADIUS * 0.3, y - NODE_RADIUS * 0.3, 0,
    x, y, NODE_RADIUS
  )
  gradient.addColorStop(0, colorConfig.gradient[0])
  gradient.addColorStop(1, colorConfig.gradient[1])

  // Draw main circle
  ctx.beginPath()
  ctx.arc(x, y, NODE_RADIUS, 0, 2 * Math.PI)
  ctx.fillStyle = gradient
  ctx.fill()

  // Draw border
  ctx.strokeStyle = colorConfig.border
  ctx.lineWidth = isPrimary ? 4 : 3
  ctx.stroke()

  ctx.shadowBlur = 0

  // Draw inner ring for primary
  if (isPrimary) {
    ctx.beginPath()
    ctx.arc(x, y, NODE_RADIUS - 8, 0, 2 * Math.PI)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)'
    ctx.lineWidth = 2
    ctx.stroke()
  }

  // Draw arbiter icon (scales of justice / star)
  if (isArbiter) {
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
    ctx.font = '20px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('⚖', x, y - 2)
  } else {
    // Draw state text
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 11px Inter, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    
    // Abbreviate state
    let stateLabel = node.state_str.toUpperCase()
    if (stateLabel === 'PRIMARY') stateLabel = 'PRI'
    if (stateLabel === 'SECONDARY') stateLabel = 'SEC'
    if (stateLabel === 'RECOVERING') stateLabel = 'REC'
    
    ctx.fillText(stateLabel, x, y)
  }

  // Draw health indicator
  const healthX = x + NODE_RADIUS - 8
  const healthY = y - NODE_RADIUS + 8
  
  ctx.beginPath()
  ctx.arc(healthX, healthY, 8, 0, 2 * Math.PI)
  ctx.fillStyle = isHealthy ? '#10b981' : '#ef4444'
  ctx.fill()
  ctx.strokeStyle = CANVAS_COLORS.background
  ctx.lineWidth = 2
  ctx.stroke()

  // Health dot inner
  if (isHealthy) {
    ctx.beginPath()
    ctx.arc(healthX, healthY, 3, 0, 2 * Math.PI)
    ctx.fillStyle = '#34d399'
    ctx.fill()
  } else {
    // X mark for down
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(healthX - 3, healthY - 3)
    ctx.lineTo(healthX + 3, healthY + 3)
    ctx.moveTo(healthX + 3, healthY - 3)
    ctx.lineTo(healthX - 3, healthY + 3)
    ctx.stroke()
  }

  // Draw node label
  ctx.fillStyle = CANVAS_COLORS.text
  ctx.font = '12px Inter, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(node.node_id || node.name.split(':')[0], x, y + NODE_LABEL_OFFSET)

  // Draw partition badge
  if (partitionGroup) {
    const badgeColor = partitionGroup === 'A' ? '#10b981' : '#f59e0b'
    const badgeY = isPrimary && node.state_str.toUpperCase() === 'PRIMARY'
      ? y + NODE_LABEL_OFFSET + 28
      : y + NODE_LABEL_OFFSET + 14

    ctx.fillStyle = badgeColor
    ctx.font = 'bold 10px Inter, sans-serif'
    ctx.fillText(`Partition ${partitionGroup}`, x, badgeY)
  }

  // Draw term badge for primary
  if (isPrimary && node.state_str.toUpperCase() === 'PRIMARY') {
    ctx.fillStyle = 'rgba(16, 185, 129, 0.9)'
    ctx.font = '10px Inter, sans-serif'
    ctx.fillText('PRIMARY', x, y + NODE_LABEL_OFFSET + 14)
  }
}

/**
 * Draw election/voting indicator
 */
export function drawElectionIndicator(
  ctx: CanvasRenderingContext2D,
  centerX: number,
  centerY: number,
  phase: string,
  term: number
) {
  // Draw central election indicator
  ctx.fillStyle = 'rgba(236, 72, 153, 0.1)'
  ctx.beginPath()
  ctx.arc(centerX, centerY, 60, 0, 2 * Math.PI)
  ctx.fill()

  ctx.strokeStyle = NODE_COLORS.VOTING.fill
  ctx.lineWidth = 2
  ctx.setLineDash([5, 5])
  ctx.beginPath()
  ctx.arc(centerX, centerY, 60, 0, 2 * Math.PI)
  ctx.stroke()
  ctx.setLineDash([])

  // Phase text
  ctx.fillStyle = NODE_COLORS.VOTING.fill
  ctx.font = 'bold 14px Inter, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('ELECTION', centerX, centerY - 8)
  
  ctx.font = '11px Inter, sans-serif'
  ctx.fillText(`Term: ${term}`, centerX, centerY + 8)
  
  ctx.font = '10px Inter, sans-serif'
  ctx.fillStyle = CANVAS_COLORS.textMuted
  ctx.fillText(phase.toUpperCase(), centerX, centerY + 22)
}

/**
 * Clear the canvas
 */
export function clearCanvas(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number
) {
  ctx.clearRect(0, 0, width, height)
}

/**
 * Draw the entire cluster topology with animations
 */
export function drawClusterTopology(
  ctx: CanvasRenderingContext2D,
  nodes: MemberStatus[],
  primary: string | null,
  canvasWidth: number,
  canvasHeight: number,
  animationState?: AnimationState,
  nodePartitions?: Map<string, 'A' | 'B'>
) {
  // Draw background
  drawBackground(ctx, canvasWidth, canvasHeight)

  if (nodes.length === 0) {
    // Draw empty state
    ctx.fillStyle = CANVAS_COLORS.textMuted
    ctx.font = '16px Inter, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('Initialize a replica set to begin', canvasWidth / 2, canvasHeight / 2)
    return
  }

  const positions = calculateNodePositions(nodes, canvasWidth, canvasHeight)

  // Draw connections between all nodes (full mesh)
  for (let i = 0; i < positions.length; i++) {
    for (let j = i + 1; j < positions.length; j++) {
      // Check if nodes are in different partitions
      const node1Partition = nodePartitions?.get(positions[i].node.node_id)
      const node2Partition = nodePartitions?.get(positions[j].node.node_id)
      const inDifferentPartitions = node1Partition && node2Partition && node1Partition !== node2Partition

      const isActive = positions[i].node.health === 1 && positions[j].node.health === 1
      drawConnection(
        ctx,
        positions[i].x,
        positions[i].y,
        positions[j].x,
        positions[j].y,
        isActive && !inDifferentPartitions,
        0,
        inDifferentPartitions
      )
    }
  }

  // Draw replication flows
  if (animationState?.replicationFlows) {
    for (const flow of animationState.replicationFlows) {
      drawReplicationFlow(ctx, positions, flow)
    }
  }

  // Draw election indicator
  if (animationState?.electionInProgress) {
    drawElectionIndicator(
      ctx,
      canvasWidth / 2,
      canvasHeight / 2,
      animationState.electionPhase,
      animationState.term
    )
  }

  // Draw vote animations during election
  if (animationState?.electionInProgress && animationState?.votes && animationState.votes.size > 0) {
    animationState.votes.forEach((candidateId, voterId) => {
      const voterPos = positions.find(p => p.node.node_id === voterId)
      const candidatePos = positions.find(p => p.node.node_id === candidateId)

      if (voterPos && candidatePos) {
        const voteAnim: VoteAnimation = {
          from: { x: voterPos.x, y: voterPos.y },
          to: { x: candidatePos.x, y: candidatePos.y },
          progress: 0.5, // Middle of the animation
          voter: voterId,
          candidate: candidateId,
        }
        drawVoteAnimation(ctx, voteAnim)
      }
    })
  }

  // Draw partition boundaries if active
  if (nodePartitions && nodePartitions.size > 0) {
    const groupA: NodePosition[] = []
    const groupB: NodePosition[] = []

    positions.forEach(pos => {
      const partition = nodePartitions.get(pos.node.node_id)
      if (partition === 'A') groupA.push(pos)
      else if (partition === 'B') groupB.push(pos)
    })

    // Determine which group has majority (can accept writes)
    const totalNodes = nodes.length
    const groupAHasMajority = groupA.length > totalNodes / 2
    const groupBHasMajority = groupB.length > totalNodes / 2

    // Draw partition group boundaries
    if (groupA.length > 0) {
      drawPartitionBoundary(ctx, groupA, '#10b981', 'Group A', groupAHasMajority)
    }
    if (groupB.length > 0) {
      drawPartitionBoundary(ctx, groupB, '#f59e0b', 'Group B', groupBHasMajority)
    }

    // Draw WIP notice for partition visualization
    ctx.save()
    ctx.fillStyle = 'rgba(245, 158, 11, 0.9)'
    ctx.font = '10px Inter, sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText('[WIP] Partition visualization has known issues', 10, 10)
    ctx.restore()
  }

  // Draw nodes on top of connections
  positions.forEach(({ x, y, node }) => {
    const isPrimary = node.node_id === primary || node.name === primary
    // Mark node as voting if it's participating in an election
    const isVoting = animationState?.electionInProgress && animationState?.votes?.has(node.node_id)
    const heartbeat = animationState?.heartbeats?.get(node.node_id) || 0
    const partitionGroup = nodePartitions?.get(node.node_id)
    drawNode(ctx, x, y, node, isPrimary, isVoting || false, heartbeat, partitionGroup)
  })

  // Draw timestamp
  if (animationState?.timestamp) {
    ctx.fillStyle = CANVAS_COLORS.textMuted
    ctx.font = '10px Inter, sans-serif'
    ctx.textAlign = 'right'
    ctx.fillText(
      new Date(animationState.timestamp).toLocaleTimeString(),
      canvasWidth - 10,
      canvasHeight - 10
    )
  }
}

/**
 * Draw partition boundary around a group of nodes
 */
function drawPartitionBoundary(
  ctx: CanvasRenderingContext2D,
  nodes: NodePosition[],
  color: string,
  label: string,
  hasMajority: boolean = false
) {
  if (nodes.length === 0) return

  // Calculate bounding box
  const padding = 60
  const xs = nodes.map(n => n.x)
  const ys = nodes.map(n => n.y)
  const minX = Math.min(...xs) - padding
  const maxX = Math.max(...xs) + padding
  const minY = Math.min(...ys) - padding
  const maxY = Math.max(...ys) + padding

  // Draw dashed rectangle
  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = hasMajority ? 3 : 2
  ctx.setLineDash([10, 5])
  ctx.globalAlpha = hasMajority ? 0.9 : 0.6
  ctx.strokeRect(minX, minY, maxX - minX, maxY - minY)

  // Draw filled background
  ctx.fillStyle = color
  ctx.globalAlpha = hasMajority ? 0.1 : 0.05
  ctx.fillRect(minX, minY, maxX - minX, maxY - minY)

  // Draw label with majority indicator
  ctx.globalAlpha = 0.9
  ctx.fillStyle = color
  ctx.font = 'bold 12px Inter, sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  
  const labelText = hasMajority ? `${label} (MAJORITY - Can Write)` : `${label} (Minority - Read Only)`
  ctx.fillText(labelText, minX + 10, minY + 10)

  // Draw majority badge icon
  if (hasMajority) {
    ctx.fillStyle = '#10b981'
    ctx.font = '14px sans-serif'
    ctx.fillText('\u2713', minX + 10 + ctx.measureText(labelText).width + 8, minY + 8)
  } else {
    ctx.fillStyle = '#ef4444'
    ctx.font = '14px sans-serif'
    ctx.fillText('\u26A0', minX + 10 + ctx.measureText(labelText).width + 8, minY + 8)
  }

  ctx.restore()
}

/**
 * Helper to convert hex color to RGB values
 */
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (result) {
    return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
  }
  return '255, 255, 255'
}

// Legacy exports for backward compatibility
export function getNodeColor(state: string): string {
  return getNodeColorConfig(state).fill
}

export const CONNECTION_COLOR = CANVAS_COLORS.connectionDefault
