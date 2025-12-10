import { apiClient } from './client'
import type {
  CrashNodeRequest,
  RestoreNodeRequest,
  CreatePartitionRequest,
  InjectLatencyRequest,
  FailureResponse,
  FailureState,
} from '../types/failure'

export const failuresApi = {
  /**
   * Crash a MongoDB node
   */
  crashNode: async (request: CrashNodeRequest): Promise<FailureResponse> => {
    const response = await apiClient.post<FailureResponse>('/api/failures/crash', request)
    return response.data
  },

  /**
   * Restore a crashed node
   */
  restoreNode: async (request: RestoreNodeRequest): Promise<FailureResponse> => {
    const response = await apiClient.post<FailureResponse>('/api/failures/restore', request)
    return response.data
  },

  /**
   * Create a network partition
   */
  createPartition: async (request: CreatePartitionRequest): Promise<FailureResponse> => {
    const response = await apiClient.post<FailureResponse>('/api/failures/partition', request)
    return response.data
  },

  /**
   * Heal all network partitions
   */
  healPartitions: async (): Promise<FailureResponse> => {
    const response = await apiClient.post<FailureResponse>('/api/failures/heal')
    return response.data
  },

  /**
   * Inject network latency
   */
  injectLatency: async (request: InjectLatencyRequest): Promise<FailureResponse> => {
    const response = await apiClient.post<FailureResponse>('/api/failures/latency', request)
    return response.data
  },

  /**
   * Get all active failures
   */
  getActiveFailures: async (): Promise<FailureState[]> => {
    const response = await apiClient.get<FailureState[]>('/api/failures/active')
    return response.data
  },

  /**
   * Clear a specific failure
   */
  clearFailure: async (failureId: string): Promise<FailureResponse> => {
    const response = await apiClient.delete<FailureResponse>(`/api/failures/${failureId}`)
    return response.data
  },
}
