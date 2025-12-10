import { create } from 'zustand'
import type { ClusterState, ReplicaSetStatus } from '../types/cluster'

interface ClusterStore {
  clusterState: ClusterState | null
  selectedReplicaSet: string | null
  isLoading: boolean
  error: string | null

  setClusterState: (state: ClusterState) => void
  setSelectedReplicaSet: (name: string | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void

  getReplicaSet: (name: string) => ReplicaSetStatus | null
}

export const useClusterStore = create<ClusterStore>((set, get) => ({
  clusterState: null,
  selectedReplicaSet: null,
  isLoading: false,
  error: null,

  setClusterState: (state) => set({ clusterState: state, error: null }),

  setSelectedReplicaSet: (name) => set({ selectedReplicaSet: name }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  getReplicaSet: (name) => {
    const state = get().clusterState
    return state?.replica_sets[name] || null
  },
}))
