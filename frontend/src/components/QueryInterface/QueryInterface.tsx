import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queriesApi } from '../../api/queries'
import {
  QueryRequest,
  QueryResult,
  ReadConcernLevel,
  WriteConcernLevel,
  ReadPreferenceMode,
} from '../../types/query'
import { Tooltip } from '../Tooltip/Tooltip'
import './QueryInterface.css'

interface QueryInterfaceProps {
  replicaSetName?: string
}

export function QueryInterface({ replicaSetName }: QueryInterfaceProps) {
  const queryClient = useQueryClient()

  // Form state
  const [database, setDatabase] = useState('testdb')
  const [collection, setCollection] = useState('testcol')
  const [operation, setOperation] = useState('find')
  const [queryFilter, setQueryFilter] = useState('{}')
  const [document, setDocument] = useState('{}')
  const [limit, setLimit] = useState('')
  const [readConcern, setReadConcern] = useState<ReadConcernLevel>(ReadConcernLevel.LOCAL)
  const [writeConcern, setWriteConcern] = useState<WriteConcernLevel>(WriteConcernLevel.W1)
  const [readPreference, setReadPreference] = useState<ReadPreferenceMode>(
    ReadPreferenceMode.PRIMARY
  )

  // Result state
  const [lastResult, setLastResult] = useState<QueryResult | null>(null)

  // Execute query mutation
  const executeMutation = useMutation({
    mutationFn: (request: QueryRequest) => queriesApi.executeQuery(request),
    onSuccess: (result) => {
      setLastResult(result)
      queryClient.invalidateQueries({ queryKey: ['query-history'] })
    },
    onError: (error: any) => {
      console.error('Query execution failed:', error)
      setLastResult({
        success: false,
        data: [],
        metrics: {
          execution_time_ms: 0,
          nodes_accessed: [],
          documents_returned: 0,
          timestamp: new Date().toISOString(),
        },
        message: 'Query execution failed',
        error: error.message || 'Unknown error',
      })
    },
  })

  // Insert test data mutation
  const insertTestDataMutation = useMutation({
    mutationFn: () => queriesApi.insertTestData(replicaSetName),
    onSuccess: () => {
      alert('Test data inserted successfully!')
    },
    onError: (error: any) => {
      alert(`Failed to insert test data: ${error.message}`)
    },
  })

  // Query history
  const { data: history = [] } = useQuery({
    queryKey: ['query-history'],
    queryFn: queriesApi.getHistory,
    refetchInterval: 5000,
  })

  const handleExecute = () => {
    try {
      // Parse JSON inputs
      let parsedFilter = {}
      let parsedDocument = {}

      if (queryFilter.trim()) {
        parsedFilter = JSON.parse(queryFilter)
      }

      if (document.trim()) {
        parsedDocument = JSON.parse(document)
      }

      // Build request
      const request: QueryRequest = {
        replica_set_name: replicaSetName,
        database,
        collection,
        operation,
        read_concern: readConcern,
        write_concern: writeConcern,
        read_preference: readPreference,
      }

      // Add operation-specific fields
      if (['find', 'findOne', 'count', 'deleteOne', 'deleteMany', 'updateOne', 'updateMany'].includes(operation)) {
        request.filter = parsedFilter
      }

      if (operation === 'find' && limit) {
        request.limit = parseInt(limit)
      }

      if (['insertOne'].includes(operation)) {
        request.document = parsedDocument
      }

      if (['updateOne', 'updateMany'].includes(operation)) {
        request.update = parsedDocument
      }

      executeMutation.mutate(request)
    } catch (error: any) {
      alert(`Invalid JSON: ${error.message}`)
    }
  }

  const isReadOperation = ['find', 'findOne', 'count', 'aggregate'].includes(operation)
  const isWriteOperation = ['insertOne', 'insertMany', 'updateOne', 'updateMany', 'deleteOne', 'deleteMany'].includes(
    operation
  )

  return (
    <div className="query-interface">
      <div className="interface-header">
        <h2>Query Interface</h2>
        <p>Execute MongoDB queries with configurable consistency guarantees</p>
      </div>

      <div className="query-form">
        {/* Target */}
        <div className="form-section">
          <h3>Target</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Database</label>
              <input
                type="text"
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                placeholder="testdb"
              />
            </div>
            <div className="form-group">
              <label>Collection</label>
              <input
                type="text"
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
                placeholder="testcol"
              />
            </div>
          </div>
        </div>

        {/* Operation */}
        <div className="form-section">
          <h3>Operation</h3>
          <div className="form-group">
            <label>Operation Type</label>
            <select value={operation} onChange={(e) => setOperation(e.target.value)}>
              <optgroup label="Read Operations">
                <option value="find">find</option>
                <option value="findOne">findOne</option>
                <option value="count">count</option>
              </optgroup>
              <optgroup label="Write Operations">
                <option value="insertOne">insertOne</option>
                <option value="updateOne">updateOne</option>
                <option value="updateMany">updateMany</option>
                <option value="deleteOne">deleteOne</option>
                <option value="deleteMany">deleteMany</option>
              </optgroup>
            </select>
          </div>

          {(isReadOperation || operation.includes('delete') || operation.includes('update')) && (
            <div className="form-group">
              <label>Filter (JSON)</label>
              <textarea
                value={queryFilter}
                onChange={(e) => setQueryFilter(e.target.value)}
                placeholder='{"name": "Alice"}'
                rows={3}
              />
            </div>
          )}

          {operation === 'find' && (
            <div className="form-group">
              <label>Limit</label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="10"
              />
            </div>
          )}

          {(operation === 'insertOne' || operation.includes('update')) && (
            <div className="form-group">
              <label>{operation.includes('update') ? 'Update Document (JSON)' : 'Document (JSON)'}</label>
              <textarea
                value={document}
                onChange={(e) => setDocument(e.target.value)}
                placeholder={operation.includes('update') ? '{"$set": {"age": 31}}' : '{"name": "Alice", "age": 30}'}
                rows={4}
              />
            </div>
          )}
        </div>

        {/* Consistency Settings */}
        <div className="form-section">
          <h3>Consistency Settings</h3>

          {isReadOperation && (
            <>
              <div className="form-group">
                <label>
                  Read Concern
                  <Tooltip
                    content="Controls data freshness: 'local' is fastest but may return stale data, 'majority' ensures data won't be rolled back, 'linearizable' is slowest but guarantees the absolute latest data."
                    position="right"
                    maxWidth="300px"
                  />
                </label>
                <select
                  value={readConcern}
                  onChange={(e) => setReadConcern(e.target.value as ReadConcernLevel)}
                >
                  <option value={ReadConcernLevel.LOCAL}>local (default)</option>
                  <option value={ReadConcernLevel.AVAILABLE}>available</option>
                  <option value={ReadConcernLevel.MAJORITY}>majority (linearizable reads)</option>
                  <option value={ReadConcernLevel.LINEARIZABLE}>linearizable (strongest)</option>
                </select>
              </div>

              <div className="form-group">
                <label>
                  Read Preference
                  <Tooltip
                    content="Choose which nodes to read from: 'primary' always reads from leader (most consistent), 'secondary' offloads reads to followers (may be stale), 'nearest' picks lowest latency node."
                    position="right"
                    maxWidth="300px"
                  />
                </label>
                <select
                  value={readPreference}
                  onChange={(e) => setReadPreference(e.target.value as ReadPreferenceMode)}
                >
                  <option value={ReadPreferenceMode.PRIMARY}>primary (default)</option>
                  <option value={ReadPreferenceMode.PRIMARY_PREFERRED}>primaryPreferred</option>
                  <option value={ReadPreferenceMode.SECONDARY}>secondary</option>
                  <option value={ReadPreferenceMode.SECONDARY_PREFERRED}>secondaryPreferred</option>
                  <option value={ReadPreferenceMode.NEAREST}>nearest</option>
                </select>
              </div>
            </>
          )}

          {isWriteOperation && (
            <div className="form-group">
              <label>
                Write Concern
                <Tooltip
                  content="Controls write durability: 'w:0' is fastest but unsafe (no ack), 'w:1' waits for primary ack, 'w:majority' waits for majority ack (safest, prevents data loss during failover)."
                  position="right"
                  maxWidth="300px"
                />
              </label>
              <select
                value={writeConcern}
                onChange={(e) => setWriteConcern(e.target.value as WriteConcernLevel)}
              >
                <option value={WriteConcernLevel.W0}>w:0 (no acknowledgment)</option>
                <option value={WriteConcernLevel.W1}>w:1 (primary only - default)</option>
                <option value={WriteConcernLevel.W2}>w:2 (primary + 1 secondary)</option>
                <option value={WriteConcernLevel.W3}>w:3 (primary + 2 secondaries)</option>
                <option value={WriteConcernLevel.MAJORITY}>majority (majority acknowledgment)</option>
              </select>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="form-actions">
          <button
            onClick={handleExecute}
            disabled={executeMutation.isPending}
            className="btn-primary"
          >
            {executeMutation.isPending ? 'Executing...' : 'Execute Query'}
          </button>

          <button
            onClick={() => insertTestDataMutation.mutate()}
            disabled={insertTestDataMutation.isPending}
            className="btn-secondary"
          >
            Insert Test Data
          </button>
        </div>
      </div>

      {/* Results */}
      {lastResult && (
        <div className="query-results">
          <h3>Results</h3>

          <div className={`result-status ${lastResult.success ? 'success' : 'error'}`}>
            <strong>{lastResult.success ? 'Success' : 'Error'}</strong>
            <p>{lastResult.message}</p>
            {lastResult.error && <p className="error-detail">{lastResult.error}</p>}
          </div>

          {lastResult.success && (
            <>
              <div className="metrics">
                <h4>Metrics</h4>
                <div className="metrics-grid">
                  <div className="metric-item">
                    <span className="metric-label">Execution Time</span>
                    <span className="metric-value">
                      {lastResult.metrics.execution_time_ms.toFixed(2)} ms
                    </span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Documents</span>
                    <span className="metric-value">{lastResult.metrics.documents_returned}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Nodes Accessed</span>
                    <span className="metric-value">
                      {lastResult.metrics.nodes_accessed.join(', ') || 'N/A'}
                    </span>
                  </div>
                  {lastResult.metrics.read_concern_used && (
                    <div className="metric-item">
                      <span className="metric-label">Read Concern</span>
                      <span className="metric-value">{lastResult.metrics.read_concern_used}</span>
                    </div>
                  )}
                  {lastResult.metrics.write_concern_used && (
                    <div className="metric-item">
                      <span className="metric-label">Write Concern</span>
                      <span className="metric-value">{lastResult.metrics.write_concern_used}</span>
                    </div>
                  )}
                </div>
              </div>

              {lastResult.data.length > 0 && (
                <div className="result-data">
                  <h4>Data ({lastResult.data.length} documents)</h4>
                  <pre>{JSON.stringify(lastResult.data, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="query-history">
          <div className="history-header">
            <h3>Query History ({history.length})</h3>
            <button
              onClick={() => queriesApi.clearHistory()}
              className="btn-clear"
            >
              Clear History
            </button>
          </div>
          <div className="history-list">
            {history.slice(-5).reverse().map((item, index) => (
              <div key={index} className="history-item">
                <div className="history-operation">
                  <strong>{item.request.operation}</strong> on {item.request.database}.
                  {item.request.collection}
                </div>
                <div className="history-time">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </div>
                <div className={`history-status ${item.result.success ? 'success' : 'error'}`}>
                  {item.result.success ? '✓' : '✗'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
