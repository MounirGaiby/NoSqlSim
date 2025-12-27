export enum ReadConcernLevel {
  LOCAL = 'local',
  AVAILABLE = 'available',
  MAJORITY = 'majority',
  LINEARIZABLE = 'linearizable',
  SNAPSHOT = 'snapshot',
}

export enum WriteConcernLevel {
  W0 = 'w0',
  W1 = 'w1',
  W2 = 'w2',
  W3 = 'w3',
  MAJORITY = 'majority',
  CUSTOM = 'custom',
}

export enum ReadPreferenceMode {
  PRIMARY = 'primary',
  PRIMARY_PREFERRED = 'primaryPreferred',
  SECONDARY = 'secondary',
  SECONDARY_PREFERRED = 'secondaryPreferred',
  NEAREST = 'nearest',
}

export interface QueryRequest {
  replica_set_name?: string
  target_node_id?: string
  database: string
  collection: string
  operation: string
  filter?: Record<string, any>
  limit?: number
  pipeline?: any[]
  document?: Record<string, any>
  documents?: Record<string, any>[]
  update?: Record<string, any>
  read_concern: ReadConcernLevel
  write_concern: WriteConcernLevel
  write_concern_w?: number
  read_preference: ReadPreferenceMode
}

export interface QueryMetrics {
  execution_time_ms: number
  nodes_accessed: string[]
  documents_returned: number
  read_concern_used?: string
  write_concern_used?: string
  read_preference_used?: string
  timestamp: string
}

export interface QueryResult {
  success: boolean
  data: any[]
  metrics: QueryMetrics
  message: string
  error?: string
}

export interface QueryHistoryItem {
  timestamp: string
  request: QueryRequest
  result: QueryResult
}
