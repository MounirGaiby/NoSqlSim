# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NoSqlSim is a MongoDB Replication & Consistency Simulator built for educational purposes. It demonstrates MongoDB replica sets, elections, read/write concerns, CAP theorem through network partitions, and failure handling. The project consists of a FastAPI backend that manages Docker-based MongoDB instances and a React/TypeScript frontend with real-time WebSocket updates.

## Development Commands

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Backend runs on http://localhost:8000

**Run tests:**
```bash
cd backend
pytest
```

**Run single test:**
```bash
cd backend
pytest tests/test_file.py::test_function_name
```

### Frontend (React + Vite)

```bash
cd frontend
npm install      # or pnpm install
npm run dev
npm run build
npm run lint
```

Frontend runs on http://localhost:5173

## Architecture

### Backend Service Layer

The backend uses a layered architecture with singleton managers coordinated via dependency injection:

**Core Services:**
- `DockerManager` (backend/app/services/docker_manager.py): Manages Docker containers for MongoDB nodes. Creates/removes containers, simulates crashes (stop/start/kill), handles network isolation for partition simulation. All containers use the `nosqlsim_default` bridge network.

- `ClusterManager` (backend/app/services/cluster_manager.py): Orchestrates MongoDB replica sets. Initializes replica sets via `replSetInitiate`, adds/removes members via `replSetReconfig`, manages elections via `replSetStepDown`. Maintains PyMongo client connections and tracks node configurations.

- `QueryExecutor` (backend/app/services/query_executor.py): Executes MongoDB queries with configurable read/write concerns and read preferences. Automatically finds working nodes or primary based on query type. Serializes BSON types (ObjectId, datetime) to JSON.

- `FailureSimulator` (backend/app/services/failure_simulator.py): Simulates various failure scenarios including node crashes, network partitions, and recovery.

**Key Interactions:**
- ClusterManager depends on DockerManager to create containers before initializing replica sets
- QueryExecutor references ClusterManager (lazy import to avoid circular dependency) to find nodes and get cluster status
- All services are global singletons instantiated in their respective modules

### MongoDB Connection Strategy

The architecture uses **direct connections** to MongoDB nodes because:
1. Replica sets are configured with internal Docker hostnames (e.g., `mongo-rs0-node1:27017`)
2. These hostnames are not resolvable from the host machine
3. External access uses port mapping (localhost:27017, localhost:27018, etc.)
4. All connections use `?directConnection=true` to bypass replica set discovery

This is handled in `DockerManager.get_node_connection_string()` for internal network communication and `_find_working_node()/_find_primary_node()` in QueryExecutor for external queries.

### WebSocket Real-time Updates

The backend broadcasts cluster state updates via WebSocket:
- `monitor_cluster_state()` in main.py polls cluster status every 1 second (configurable via `cluster_poll_interval_seconds`)
- Updates are broadcasted through `broadcaster.broadcast_cluster_state()`
- Frontend connects via `useWebSocket` hook which auto-reconnects with exponential backoff

### Frontend State Management

- **Zustand**: Not currently used extensively, but imported for potential global state
- **React Query (@tanstack/react-query)**: Manages API calls and server state
- **WebSocket Hook** (frontend/src/hooks/useWebSocket.ts): Handles real-time cluster state updates with automatic reconnection logic
- **Custom Hook** (frontend/src/hooks/useClusterState.ts): Manages cluster-specific state

### Configuration

Backend settings are centralized in `backend/app/config.py` using Pydantic Settings:
- MongoDB version, ports, Docker network/container prefixes
- CORS origins for frontend communication
- Cluster defaults (election timeout, heartbeat interval)
- Monitoring intervals

Load settings from `.env` file (see `backend/.env.example` for template).

## Important Implementation Details

### Adding/Removing Replica Set Members

When adding a member:
1. Create Docker container via DockerManager
2. Wait for container startup (3 seconds)
3. Get current replica set config via `replSetGetConfig`
4. Increment config version and append new member
5. Apply via `replSetReconfig`

When removing:
1. Get current config and increment version
2. Filter out member by hostname
3. Apply reconfiguration
4. Stop and remove Docker container

### Stepping Down Primary

The `step_down_primary()` method has special error handling:
- PyMongo raises an exception when stepdown succeeds (connection closed by server)
- Check error message for "connection closed", "socket", "not primary" to detect success
- Clear cached MongoDB client after successful stepdown
- Raise ValueError if no electable secondaries available

### Failure Simulation

Network partitions are simulated by detaching containers from Docker networks, not by firewall rules. This is handled in DockerManager via `attach_to_network()`/`detach_from_network()`.

### BSON Serialization

MongoDB returns BSON types (ObjectId, datetime) that aren't JSON-serializable. The `_serialize_mongo_doc()` function in query_executor.py recursively converts these:
- ObjectId → string
- datetime → ISO format string
- Recursively handles nested dicts and lists

## Common Workflows

### Testing Read/Write Concerns

1. Initialize a replica set via `POST /api/cluster/init`
2. Use QueryExecutor with different `ReadConcernLevel` (local, majority, linearizable) or `WriteConcernLevel` (w0, w1, majority)
3. Observe consistency behavior in the frontend's Query Interface

### Simulating Failures

1. Crash a node: `POST /api/failures/crash` with `node_id`
2. Create partition: `POST /api/failures/partition` with list of `node_ids` to isolate
3. Observe election behavior and cluster state updates via WebSocket

### Election Demonstration

1. Initialize 3-node replica set
2. Call `POST /api/cluster/step-down` to force primary stepdown
3. Watch WebSocket updates to see election complete (typically 10 seconds)
4. New primary will be elected from healthy secondaries
