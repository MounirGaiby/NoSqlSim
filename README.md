# NoSqlSim - Quick Start

MongoDB Replication & Consistency Simulator

**Created by:** Mounir Gaiby, Amine Banan | **Prof:** Hanin | **Class:** 3CI Big Data AI | **School:** ISGA

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (running)

## Quick Start

### 1. Start Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Backend runs on: http://localhost:8000

### 2. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: http://localhost:5173

### 3. Use the App

1. Open http://localhost:5173
2. Click "Initialize Cluster" (wait 30 seconds)
3. Explore:
   - **Add/Remove nodes**
   - **Crash/Restore nodes** (simulate failures)
   - **Step Down Primary** (trigger elections)
   - **Query Interface** (test read/write concerns)
   - **Network Partitions** (demonstrate CAP theorem)

## Features

✅ Replica set visualization
✅ Real-time WebSocket updates
✅ Node failure simulation
✅ Query execution with consistency controls
✅ Network partitions for CAP theorem demos

## Troubleshooting

**Backend won't start?**
- Make sure Docker Desktop is running
- Check Python version: `python3 --version` (need 3.11+)

**Frontend won't start?**
- Check Node version: `node --version` (need 18+)
- Delete `node_modules` and run `npm install` again

**Cluster won't initialize?**
- Make sure Docker has enough resources (4GB RAM minimum)
- Check Docker containers: `docker ps`
- Wait 30-60 seconds after clicking "Initialize"

## API Documentation

**Base URL:** http://localhost:8000

**Key Endpoints:**
- `POST /api/cluster/init` - Initialize replica set
- `GET /api/cluster/status` - Get cluster state
- `POST /api/queries/execute` - Execute MongoDB queries
- `POST /api/failures/crash` - Crash a node
- `POST /api/failures/partition` - Create network partition
- `WS /ws` - WebSocket for real-time updates

Full API docs: http://localhost:8000/docs

## Learn More

This tool demonstrates:
- MongoDB replica sets and elections
- Read/write concerns (local, majority, linearizable)
- CAP theorem through network partitions
- Failure handling and automatic failover
