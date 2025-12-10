import { apiClient } from './client'
import { QueryRequest, QueryResult, QueryHistoryItem } from '../types/query'

export const queriesApi = {
  /**
   * Execute a MongoDB query with specified concerns
   */
  async executeQuery(request: QueryRequest): Promise<QueryResult> {
    const response = await apiClient.post<QueryResult>('/api/queries/execute', request)
    return response.data
  },

  /**
   * Get query execution history
   */
  async getHistory(): Promise<QueryHistoryItem[]> {
    const response = await apiClient.get<QueryHistoryItem[]>('/api/queries/history')
    return response.data
  },

  /**
   * Clear query history
   */
  async clearHistory(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.delete<{ success: boolean; message: string }>('/api/queries/history')
    return response.data
  },

  /**
   * Insert test data
   */
  async insertTestData(replicaSetName?: string): Promise<any> {
    const params = replicaSetName ? { replica_set_name: replicaSetName } : {}
    const response = await apiClient.post('/api/queries/test-data', null, { params })
    return response.data
  },
}
