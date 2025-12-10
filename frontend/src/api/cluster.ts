import { apiClient } from './client'
import type {
  ClusterState,
  InitClusterRequest,
  InitClusterResponse,
  ReplicaSetStatus,
  AddNodeRequest,
  StepDownRequest,
} from '../types/cluster'

export const clusterApi = {
  /**
   * Initialize a new replica set
   */
  initCluster: async (request: InitClusterRequest): Promise<InitClusterResponse> => {
    const response = await apiClient.post<InitClusterResponse>('/api/cluster/init', request)
    return response.data
  },

  /**
   * Get status of all clusters
   */
  getClusterStatus: async (): Promise<ClusterState> => {
    const response = await apiClient.get<ClusterState>('/api/cluster/status')
    return response.data
  },

  /**
   * Get status of a specific replica set
   */
  getReplicaSetStatus: async (replicaSetName: string): Promise<ReplicaSetStatus> => {
    const response = await apiClient.get<ReplicaSetStatus>(`/api/cluster/status/${replicaSetName}`)
    return response.data
  },

  /**
   * Add a new node to a replica set
   */
  addNode: async (request: AddNodeRequest) => {
    const response = await apiClient.post('/api/cluster/nodes', request)
    return response.data
  },

  /**
   * Remove a node from a replica set
   */
  removeNode: async (nodeId: string, replicaSetName: string) => {
    const response = await apiClient.delete(`/api/cluster/nodes/${nodeId}`, {
      params: { replica_set_name: replicaSetName },
    })
    return response.data
  },

  /**
   * Step down the primary node
   */
  stepDownPrimary: async (request: StepDownRequest) => {
    const response = await apiClient.post('/api/cluster/stepdown', request)
    return response.data
  },

  /**
   * Get logs for a specific node
   */
  getNodeLogs: async (nodeId: string): Promise<{ node_id: string; logs: string }> => {
    const response = await apiClient.get<{ node_id: string; logs: string }>(`/api/cluster/nodes/${nodeId}/logs`)
    return response.data
  },
}
