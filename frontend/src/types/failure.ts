// Mirror backend failure models

export interface FailureState {
  failure_id: string
  failure_type: 'node_crash' | 'network_partition' | 'latency_injection' | 'packet_loss'
  affected_nodes: string[]
  started_at: string
  config: Record<string, any>
  description: string
}

export interface PartitionConfig {
  group_a: string[]
  group_b: string[]
  description?: string
}

export interface LatencyConfig {
  node_id: string
  latency_ms: number
  jitter_ms?: number
}

export interface CrashNodeRequest {
  node_id: string
  crash_type: 'clean' | 'hard'
}

export interface RestoreNodeRequest {
  node_id: string
}

export interface CreatePartitionRequest {
  replica_set_name: string
  partition_config: PartitionConfig
}

export interface InjectLatencyRequest {
  latency_config: LatencyConfig
}

export interface FailureResponse {
  success: boolean
  failure_id?: string
  message: string
  failure_state?: FailureState
}
