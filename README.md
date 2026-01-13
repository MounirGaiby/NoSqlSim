# NoSqlSim

MongoDB Replication & Consistency Simulator

An interactive, visual learning platform for understanding distributed database concepts through hands-on simulation of MongoDB replica sets.

**Created by:** Mounir Gaiby, Amine Banan

## Overview

NoSqlSim is an open-source educational platform that simulates MongoDB replica sets, providing educators, students, and learners with an interactive, visual way to explore distributed database concepts. Whether you're teaching a database course, learning NoSQL systems, or exploring distributed architectures, NoSqlSim offers real-time visualization of cluster topology, node failures, network partitions, and consistency behaviors.

## Key Features

### Cluster Management
- **Initialize Replica Sets**: Create MongoDB clusters with configurable node counts
- **Dynamic Scaling**: Add or remove nodes from running clusters
- **Node Role Management**: Configure primaries, secondaries, and arbiters

### Failure Simulation
- **Node Crashes**: Simulate clean and hard node failures
- **Network Partitions**: Create split-brain scenarios to demonstrate CAP theorem
- **Primary Step Down**: Trigger election processes manually
- **Automatic Failover**: Observe MongoDB's self-healing capabilities

### Query Execution
- **Write Concerns**: Test local, majority, and linearizable write concerns
- **Read Concerns**: Experiment with different consistency levels
- **Consistency Testing**: Observe how MongoDB handles concurrent operations during failures

### Real-Time Visualization
- **Live Cluster Topology**: Visual representation of node states and roles
- **Heartbeat Animation**: See replication heartbeats in action
- **Replication Flows**: Watch data flow from primary to secondaries
- **WebSocket Updates**: Real-time state synchronization across the UI

### Educational Components
- **CAP Theorem Panel**: Interactive explanation of MongoDB's CP characteristics
- **Partition Behavior**: Demonstrable split-brain scenarios
- **Consistency Models**: Visual feedback on read/write concern behaviors

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  React + TypeScript + Vite + Canvas API + WebSocket Client  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                        Backend                               │
│           FastAPI + Python + Docker SDK + PyMongo           │
└────────────────────────┬────────────────────────────────────┘
                         │ Docker API
┌────────────────────────▼────────────────────────────────────┐
│                    Docker Containers                         │
│             MongoDB 7.0 Replica Set Instances               │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: 18 or higher
- **Docker Desktop**: Running with at least 4GB RAM allocated
- **Operating System**: macOS, Linux, or Windows with WSL2

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd NoSqlSim
```

### 2. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

## Running the Application

### Start Backend Server

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python -m app.main
```

Backend runs on: **http://localhost:8000**
API Documentation: **http://localhost:8000/docs**

### Start Frontend Server

```bash
cd frontend
npm run dev
```

Frontend runs on: **http://localhost:5173**

## Usage Guide

### Initial Setup

1. Open **http://localhost:5173** in your browser
2. Click **"Initialize Cluster"** in the Control Panel
3. Wait 30-60 seconds for the replica set to stabilize
4. Observe the cluster topology visualization

### Exploring Features

#### Add/Remove Nodes
- Use the Control Panel to dynamically scale your cluster
- Observe how MongoDB reconfigures the replica set
- Watch election processes when nodes are added or removed

#### Simulate Node Failures
- **Crash Node**: Stops a running node to simulate hardware failure
- **Restore Node**: Brings a crashed node back online
- **Step Down Primary**: Forces primary to step down and trigger election

#### Create Network Partitions
- Split the cluster into two groups (e.g., 2 nodes vs 1 node)
- Observe that only the majority partition can accept writes
- Demonstrates MongoDB's CP (Consistency + Partition tolerance) behavior

#### Execute Queries
- Use the Query Interface to test read and write operations
- Experiment with different write concerns:
  - `w: 1` - Acknowledge after writing to primary
  - `w: "majority"` - Acknowledge after majority replication
- Test during network partitions to see consistency guarantees

## API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### Cluster Management
```http
POST   /api/cluster/init           # Initialize replica set
GET    /api/cluster/status         # Get cluster state
POST   /api/cluster/add-member     # Add node to replica set
DELETE /api/cluster/remove-member  # Remove node from replica set
POST   /api/cluster/step-down      # Step down primary
DELETE /api/cluster/cleanup        # Cleanup all resources
```

#### Failure Simulation
```http
POST   /api/failures/crash         # Crash a node
POST   /api/failures/restore       # Restore crashed node
POST   /api/failures/partition     # Create network partition
POST   /api/failures/heal          # Heal network partition
GET    /api/failures/active        # List active failures
```

#### Query Execution
```http
POST   /api/queries/execute        # Execute MongoDB query
GET    /api/queries/history        # Query execution history
```

#### WebSocket
```
WS     /ws                         # Real-time cluster updates
```

Full interactive documentation available at: **http://localhost:8000/docs**

## Understanding CAP Theorem with NoSqlSim

### What is CAP Theorem?

The CAP theorem states that distributed systems can guarantee only two of three properties:
- **Consistency**: All nodes see the same data simultaneously
- **Availability**: Every request receives a response
- **Partition Tolerance**: System operates despite network partitions

### MongoDB's CP Choice

MongoDB chooses **Consistency + Partition Tolerance (CP)**, sacrificing availability during network partitions.

**How it works:**
1. During a partition, MongoDB uses majority voting
2. The partition with majority nodes elects a primary and accepts writes
3. The minority partition rejects writes to prevent data conflicts
4. This guarantees consistency across the cluster

**Try it yourself:**
1. Initialize a 3-node cluster
2. Create a 2-1 network partition
3. Attempt writes on both partitions
4. Observe: Only the majority (2-node) partition accepts writes
5. The minority (1-node) partition returns errors

This behavior prevents split-brain scenarios and ensures data integrity.

## Technology Stack

### Backend
- **FastAPI**: Modern async web framework
- **PyMongo**: MongoDB driver for Python
- **Docker SDK**: Container orchestration
- **Pydantic**: Data validation
- **Uvicorn**: ASGI server

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type-safe JavaScript
- **Vite**: Build tool and dev server
- **TanStack Query**: Data synchronization
- **Canvas API**: Cluster visualization

### Infrastructure
- **Docker**: Container runtime
- **MongoDB 7.0**: Database engine
- **WebSockets**: Real-time communication

## Project Structure

```
NoSqlSim/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # API endpoints
│   │   ├── models/              # Data models
│   │   ├── services/            # Business logic
│   │   │   ├── cluster_manager.py
│   │   │   ├── docker_manager.py
│   │   │   ├── failure_simulator.py
│   │   │   └── query_executor.py
│   │   ├── websocket/           # WebSocket handlers
│   │   ├── config.py            # Configuration
│   │   └── main.py              # Application entry
│   ├── tests/                   # Test suite
│   └── requirements.txt         # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── api/                 # API client
│   │   ├── components/          # React components
│   │   │   ├── ClusterTopology/
│   │   │   ├── ControlPanel/
│   │   │   ├── QueryInterface/
│   │   │   └── CAPTheorem/
│   │   ├── hooks/               # Custom React hooks
│   │   ├── types/               # TypeScript types
│   │   ├── utils/               # Utility functions
│   │   └── App.tsx              # Root component
│   ├── package.json             # Node dependencies
│   └── vite.config.ts           # Vite configuration
│
├── docs/                        # Additional documentation
└── README.md                    # This file
```

## Troubleshooting

### Backend Issues

**Backend won't start**
- Ensure Docker Desktop is running
- Check Python version: `python3 --version` (requires 3.11+)
- Verify virtual environment is activated

**Port already in use**
- Check if port 8000 is available: `lsof -i :8000`
- Modify port in `backend/app/config.py` if needed

### Frontend Issues

**Frontend won't start**
- Check Node version: `node --version` (requires 18+)
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Clear npm cache: `npm cache clean --force`

### Cluster Issues

**Cluster won't initialize**
- Ensure Docker has sufficient resources (4GB RAM minimum)
- Check running containers: `docker ps`
- View Docker logs: `docker logs <container-name>`
- Wait 30-60 seconds for initialization to complete

**Nodes won't respond**
- Check container health: `docker ps`
- Restart Docker Desktop
- Clear old containers: `docker rm -f $(docker ps -aq)`

### Network Partition Issues

**Partition won't create**
- Ensure all nodes are healthy before partitioning
- Check Docker network: `docker network ls`
- Remove old partition networks manually if needed

## Development

### Running Tests

```bash
cd backend
pytest tests/
```

### Code Formatting

```bash
# Backend
black app/
isort app/

# Frontend
npm run lint
npm run format
```

### Building for Production

```bash
# Frontend
cd frontend
npm run build

# Backend
cd backend
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Learning Outcomes

By using NoSqlSim, you will understand:
- MongoDB replica set architecture and configuration
- Distributed consensus and leader election (Raft protocol concepts)
- Write concerns and read concerns in distributed databases
- CAP theorem implications in real-world systems
- Network partition handling and split-brain prevention
- Automatic failover and disaster recovery mechanisms
- Trade-offs between consistency, availability, and partition tolerance

## Contributing

Contributions, suggestions, and improvements are welcome! This project aims to be a valuable educational resource for the global developer and educator community.

## License

MIT License - Free to use for educational purposes, personal learning, and teaching.
