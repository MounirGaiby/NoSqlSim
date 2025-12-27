// Mirror backend Pydantic models

export interface NodeConfig {
  node_id: string
  host: string
  port: number
  role: 'replica' | 'arbiter'
  priority: number
  votes: number
}

export interface MemberStatus {
  node_id: string
  name: string
  state: string
  state_str: string
  health: number
  uptime: number
  optime?: string
  last_heartbeat?: string
  ping_ms?: number
}

export interface ReplicaSetStatus {
  set_name: string
  primary: string | null
  members: MemberStatus[]
  health: 'ok' | 'degraded' | 'down'
  term?: number
}

export interface PartitionInfo {
  failure_id: string
  group_a: string[]
  group_b: string[]
  description?: string
}

export interface ClusterState {
  timestamp: string
  replica_sets: Record<string, ReplicaSetStatus>
  sharded_clusters: any[]
  active_failures: string[]
  active_partitions: PartitionInfo[]
}

export interface InitClusterRequest {
  replica_set_name: string
  node_count: number
  starting_port: number
}

export interface InitClusterResponse {
  success: boolean
  message: string
  replica_set_name: string
  status: ReplicaSetStatus
}

export interface AddNodeRequest {
  replica_set_name: string
  role: 'replica' | 'arbiter'
  priority: number
}

export interface StepDownRequest {
  replica_set_name: string
  step_down_secs: number
}
