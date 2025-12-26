# NoSqlSim Educational Guide
**Understanding MongoDB Replication & Consistency Models**

---

## 1. Introduction

### What is MongoDB Replication?

MongoDB replication is the process of synchronizing data across multiple servers to provide redundancy, increase data availability, and enable disaster recovery. Instead of storing data on a single server, MongoDB uses **replica sets** - groups of MongoDB instances that maintain the same data set.

### Why Consistency Matters

In distributed systems, **consistency** refers to whether all nodes see the same data at the same time. Different consistency levels offer different trade-offs:
- **Strong consistency**: Slower but guarantees latest data
- **Eventual consistency**: Faster but may show stale data temporarily
- **Configurable consistency**: MongoDB allows you to choose per-operation

### NoSqlSim Overview

NoSqlSim is an interactive educational tool that lets you:
- ✅ Visualize MongoDB replica sets in real-time
- ✅ Simulate node failures and network partitions
- ✅ Test different read/write concerns to understand consistency trade-offs
- ✅ Observe elections and automatic failover
- ✅ Demonstrate CAP theorem principles

---

## 2. Replica Sets Explained

### Architecture: Primary-Secondary-Arbiter

A MongoDB replica set consists of:

```
┌─────────────┐
│   PRIMARY   │  ← Accepts all writes
│  (Leader)   │  ← Replicates to secondaries
└──────┬──────┘
       │
  ┌────┴────┐
  │         │
┌─▼────────▼─┐       ┌──────────────┐
│ SECONDARY  │       │   ARBITER    │
│ (Follower) │       │ (Vote Only)  │
└────────────┘       └──────────────┘
```

**Roles:**
- **Primary**: Receives all write operations, single source of truth
- **Secondary**: Maintains copy of data through replication, can serve reads
- **Arbiter** (optional): Participates in elections but holds no data (saves storage)

### Heartbeat Mechanism

Nodes send **heartbeat** messages every 2 seconds to:
- Detect failures
- Monitor node health
- Trigger elections when primary goes down

**In NoSqlSim:** Toggle "Heartbeats" visualization to see the heartbeat animation between nodes.

### Oplog Replication

MongoDB uses an **operations log (oplog)** to replicate data:

1. Primary records all writes to its oplog
2. Secondaries copy and apply oplog entries asynchronously
3. Secondaries can lag behind (replication lag)

**Replication Flow:**
```
Write → Primary → Oplog → Secondaries → Apply Changes
```

**In NoSqlSim:** Toggle "Replication" to see data flowing from Primary to Secondaries.

### Interactive Demo: Initialize 3-Node Cluster

**Steps:**
1. Click "Initialize Cluster" in the Control Panel
2. Set node count to **3** (recommended for quorum)
3. Wait 30 seconds for cluster to stabilize
4. Observe the topology: 1 Primary (green) + 2 Secondaries (blue)

**What's happening behind the scenes:**
- Docker containers launch MongoDB instances
- `replSetInitiate` command creates the replica set
- Nodes elect a Primary via Raft-based algorithm
- Heartbeats begin between all nodes

---

## 3. Elections and Failover

### When Elections Occur

Elections are triggered when:
- Primary node crashes or becomes unavailable
- Primary steps down manually
- Network partition isolates the primary from majority

### Election Algorithm

MongoDB uses a **Raft-based consensus algorithm**:

1. **Detect failure**: Secondaries notice missing heartbeats
2. **Call election**: Eligible secondary requests votes
3. **Vote**: Each node votes for one candidate
4. **Majority wins**: Candidate with >50% votes becomes Primary
5. **New term**: Election term number increments

**Requirements for winning:**
- Must have highest priority (if priorities differ)
- Must have most up-to-date data (latest oplog entry)
- Must receive votes from majority of nodes

### Quorum Requirements

**Quorum = Majority of nodes**

| Total Nodes | Quorum | Max Failures |
|-------------|--------|--------------|
| 3           | 2      | 1            |
| 5           | 3      | 2            |
| 7           | 4      | 3            |

**Why odd numbers?** Prevents split-brain scenarios where two nodes could both think they're primary.

### Automatic Failover

When primary fails:
```
Time    Event
0s      Primary crashes
2-10s   Secondaries detect failure (missed heartbeats)
10s     Election begins
15s     New primary elected (if quorum available)
15s+    New primary accepts writes
```

### Interactive Demo: Crash Primary & Observe Election

**Steps:**
1. Initialize a 3-node cluster (if not already running)
2. Note which node is Primary (green node)
3. In Control Panel, select the Primary node
4. Click "Crash Node"
5. **Watch the topology:**
   - Primary turns red (DOWN)
   - After ~10 seconds, one Secondary becomes Primary (blue → green)
   - The topology shows the new leader

**What to observe:**
- Election duration (~10-15 seconds)
- New primary is elected from healthy secondaries
- Crashed node remains down until you click "Restore Node"

---

## 4. Consistency Models

MongoDB provides fine-grained control over consistency through **Read Concerns**, **Write Concerns**, and **Read Preferences**.

### Read Concerns

Controls what data version a read operation returns:

#### `local` (Default)
- **What it does**: Returns most recent data from the node you query
- **Consistency**: May return data not yet replicated to majority
- **Use when**: Low latency is critical, stale reads acceptable
- **Trade-off**: Fastest, but might read data that gets rolled back

#### `available`
- **What it does**: Like `local` but for sharded clusters
- **Consistency**: No consistency guarantee
- **Use when**: Maximum read throughput needed

#### `majority`
- **What it does**: Returns data acknowledged by majority of replica set
- **Consistency**: Strong - data won't be rolled back
- **Use when**: Consistency is critical (e.g., financial data)
- **Trade-off**: Slightly higher latency

#### `linearizable` (Strongest)
- **What it does**: Guarantees read reflects all writes completed before the read began
- **Consistency**: Strongest possible, ensures real-time consistency
- **Use when**: Absolute latest data required
- **Trade-off**: Highest latency, must read from primary

#### `snapshot`
- **What it does**: Returns data from a specific point-in-time
- **Use when**: You need consistent view across multiple operations

**Comparison:**
```
local         ─────▶ Fast but may read stale data
available     ─────▶ Fastest, no guarantees
majority      ─────▶ Balanced, safe from rollbacks
linearizable  ─────▶ Slowest, always latest
```

### Write Concerns

Controls write acknowledgment level:

#### `w:0` (Fire and Forget)
- **What it does**: No acknowledgment, write and move on
- **Durability**: None - write could be lost
- **Use when**: Logging, analytics (data loss acceptable)
- **Risk**: HIGH - data may never be persisted

#### `w:1` (Default)
- **What it does**: Primary acknowledges write
- **Durability**: Write persisted on primary
- **Use when**: Standard operations
- **Risk**: Medium - data lost if primary crashes before replication

#### `w:2` or `w:3`
- **What it does**: Primary + N-1 secondaries acknowledge
- **Durability**: Data on multiple nodes
- **Use when**: Important data, moderate risk tolerance

#### `w:majority`
- **What it does**: Majority of nodes acknowledge write
- **Durability**: Write survives most failure scenarios
- **Use when**: Critical data (payments, user auth)
- **Trade-off**: Higher latency (~10-50ms more)

**Durability vs Performance:**
```
w:0       ────▶ Fastest, no durability
w:1       ────▶ Fast, moderate durability
w:majority ───▶ Slower, high durability
```

### Read Preferences

Controls which replica set members to read from:

#### `primary`
- **Reads from**: Primary only
- **Consistency**: Always latest data
- **Use when**: Consistency critical

#### `primaryPreferred`
- **Reads from**: Primary, fallback to secondary
- **Use when**: Want consistency but need availability during failover

#### `secondary`
- **Reads from**: Secondaries only
- **Consistency**: May be stale (replication lag)
- **Use when**: Offload read traffic from primary

#### `secondaryPreferred`
- **Reads from**: Secondaries, fallback to primary
- **Use when**: Distribute reads, high read volume

#### `nearest`
- **Reads from**: Node with lowest network latency
- **Use when**: Geo-distributed deployments, latency matters most

### Trade-offs: Performance vs Consistency

**The Spectrum:**
```
┌────────────────────────────────────────────────┐
│  Eventual Consistency ◄────────► Strong       │
│  (Faster, Stale OK)          (Slower, Latest) │
└────────────────────────────────────────────────┘
    local +              majority +      linearizable
    secondary            w:majority      + primary
```

**Choosing the Right Combination:**

| Use Case               | Read Concern | Write Concern | Read Preference |
|------------------------|--------------|---------------|-----------------|
| Social media feed      | local        | w:1           | secondary       |
| E-commerce product list| available    | w:1           | secondaryPref   |
| Shopping cart          | majority     | w:majority    | primaryPref     |
| Payment processing     | linearizable | w:majority    | primary         |
| Analytics dashboard    | local        | w:0           | nearest         |

### Interactive Demo: Compare Read Concern Behaviors

**Steps:**
1. Go to "Query Interface"
2. Insert test data:
   - Operation: `insertOne`
   - Database: `test`
   - Collection: `demo`
   - Document: `{"name": "Alice", "balance": 1000}`
   - Write Concern: `w:majority`
   - Click "Execute Query"

3. **Immediately** read with `local`:
   - Operation: `findOne`
   - Filter: `{"name": "Alice"}`
   - Read Concern: `local`
   - Note execution time

4. Read with `majority`:
   - Same query
   - Read Concern: `majority`
   - Compare execution time (should be slightly higher)

5. **Crash a secondary** and repeat reads:
   - Observe how `majority` still works (has quorum)
   - If you crash primary + 1 secondary, `majority` reads fail

**What to observe:**
- `local` is faster but could return data not yet replicated
- `majority` takes a bit longer but guarantees durability
- `linearizable` is slowest but always reflects latest committed writes

---

## 5. CAP Theorem in Practice

### Understanding CAP

CAP Theorem states distributed systems can only guarantee **2 out of 3**:

```
        C (Consistency)
       /  \
      /    \
     /  CP  \
    /   ▲    \
   / MongoDB  \
  /__________\___
  A         P
(Availability) (Partition Tolerance)
```

- **Consistency**: All nodes see same data
- **Availability**: Every request gets a response
- **Partition Tolerance**: System works despite network failures

**MongoDB's Choice: CP (Consistency + Partition Tolerance)**
- Prioritizes data consistency
- During partition, minority partition becomes unavailable for writes
- Majority partition continues operating

### Network Partitions

A **network partition** occurs when nodes can't communicate:
```
Before Partition:          After Partition:
┌───┬───┬───┐             ┌───┬───┐ | ┌───┐
│ P │ S │ S │      →      │ P │ S │ | │ S │
└───┴───┴───┘             └───┴───┘ | └───┘
   Cluster                 Majority  |  Minority
                          (Works)    | (Read-only)
```

**What happens:**
- **Majority side**: Can elect primary, accept writes
- **Minority side**: Cannot form quorum, becomes read-only (stale reads)

### MongoDB's Response to Partitions

1. **Majority partition** (e.g., 2 out of 3 nodes):
   - Elects or retains primary
   - Accepts writes with `w:majority`
   - Continues normal operations

2. **Minority partition** (e.g., 1 out of 3 nodes):
   - Cannot elect primary
   - Rejects writes
   - Can serve reads (potentially stale) with `local` concern
   - Returns errors for `majority` reads

### Interactive Demo: Create Partition & Test Behaviors

**Steps:**
1. Initialize a 3-node cluster
2. Insert some test documents (write concern: `w:majority`)
3. In Control Panel, find "Network Partitions" section
4. **Create 2-1 split**:
   - Add Primary + 1 Secondary to Group A
   - Add 1 Secondary to Group B
   - Click "Create Partition"

5. **Test majority partition (Group A)**:
   - Try inserting data → **Should succeed**
   - Try reading with `majority` → **Should succeed**

6. **Test minority partition (Group B)**:
   - Select the isolated node in dropdown
   - Try writing → **Should fail** (no quorum)
   - Try reading with `local` → **Might succeed** (stale)
   - Try reading with `majority` → **Should fail**

7. Click "Heal Partition" to restore network
   - Isolated node catches up via replication
   - All nodes return to normal

**What to observe:**
- Writes require majority (CAP consistency)
- Minority partition cannot accept writes (sacrifices availability)
- This proves MongoDB's CP nature

---

## 6. Real-world Scenarios

### Scenario 1: High-Traffic Web Application

**Requirements:**
- Millions of reads per day
- Moderate writes
- Tolerates slightly stale data

**Configuration:**
```javascript
readConcern: "local"
writeConcern: { w: 1 }
readPreference: "secondaryPreferred"
```

**Why:**
- Offload reads to secondaries (better scalability)
- Fast writes (w:1)
- Stale data acceptable for product listings, news feeds

### Scenario 2: Financial Transaction System

**Requirements:**
- Strong consistency
- Data durability critical
- Cannot tolerate data loss

**Configuration:**
```javascript
readConcern: "majority"
writeConcern: { w: "majority" }
readPreference: "primary"
```

**Why:**
- Majority read/write ensures no rollbacks
- Primary reads guarantee latest balance
- Survives single node failure

### Scenario 3: Analytics Dashboard

**Requirements:**
- Complex aggregation queries
- Can tolerate 5-minute old data
- High query volume

**Configuration:**
```javascript
readConcern: "available"
readPreference: "nearest"
```

**Why:**
- Fastest reads possible
- Distribute load across all nodes
- Stale data acceptable for dashboards

### Scenario 4: Session Store

**Requirements:**
- Low latency critical
- Session loss acceptable
- Very high write volume

**Configuration:**
```javascript
writeConcern: { w: 1 }
readConcern: "local"
readPreference: "primary"
```

**Why:**
- Fast writes (w:1)
- Primary reads ensure session consistency
- If session lost, user just re-logs in

### Production Best Practices

1. **Always use odd number of nodes** (3, 5, or 7)
   - Ensures clear majority for elections
   - 3 nodes tolerate 1 failure
   - 5 nodes tolerate 2 failures

2. **Use `w:majority` for critical writes**
   - Payments, user registration, account updates
   - Prevents data loss during failover

3. **Use `majority` read concern when reading your own writes**
   - Ensures you see data you just wrote
   - Example: Create account → redirect to profile page

4. **Consider read preferences based on query type**
   - Real-time user data: `primary`
   - Reports/analytics: `secondary` or `nearest`
   - Search: `secondaryPreferred`

5. **Monitor replication lag**
   - Large lag means secondaries are falling behind
   - Can cause stale reads with `local` concern
   - In NoSqlSim: Check "Uptime" in node details

6. **Plan for network partitions**
   - Deploy across availability zones
   - Majority of nodes in different zones
   - Test partition scenarios (like in NoSqlSim!)

### Common Pitfalls

❌ **Using `w:0` for user-facing writes**
- Write could be lost if primary crashes
- Use `w:1` minimum for user data

❌ **Reading from secondaries without handling staleness**
- User updates profile, refreshes page, sees old data
- Solution: Use `majority` or `primaryPreferred`

❌ **Even number of nodes (e.g., 2 or 4)**
- Can cause split-brain during partition
- Always use odd numbers

❌ **Not testing failover scenarios**
- Disaster strikes, you discover writes fail during election
- Solution: Use NoSqlSim to practice failure scenarios!

❌ **Ignoring replication lag**
- Secondaries lag behind by minutes
- `local` reads return very stale data
- Solution: Monitor lag, alert if >10 seconds

---

## 7. Appendix

### Glossary

- **Arbiter**: Voting-only member that holds no data
- **Election**: Process of choosing a new primary
- **Heartbeat**: Periodic message between nodes to detect failures
- **Majority**: More than 50% of replica set members
- **Oplog**: Operations log used for replication
- **Primary**: Leader node that accepts writes
- **Quorum**: Minimum number of nodes needed for decisions
- **Read Concern**: Consistency level for read operations
- **Read Preference**: Which nodes to read from
- **Replica Set**: Group of MongoDB instances with same data
- **Replication Lag**: Time delay between primary and secondary
- **Secondary**: Follower node that replicates data
- **Write Concern**: Acknowledgment level for writes

### Further Reading

**Official MongoDB Documentation:**
- [Replication](https://docs.mongodb.com/manual/replication/)
- [Read Concern](https://docs.mongodb.com/manual/reference/read-concern/)
- [Write Concern](https://docs.mongodb.com/manual/reference/write-concern/)
- [Read Preference](https://docs.mongodb.com/manual/core/read-preference/)
- [Replica Set Elections](https://docs.mongodb.com/manual/core/replica-set-elections/)

**Academic Papers:**
- "In Search of an Understandable Consensus Algorithm" (Raft)
- "Consistency Tradeoffs in Modern Distributed Database System Design" (Daniel Abadi)

**NoSqlSim Resources:**
- GitHub Repository: [github.com/youruser/nosqlsim](https://github.com)
- Report Issues: Use GitHub issues for bugs/feature requests
- README.md: Quick start guide

### Quick Reference Card

```
╔══════════════════════════════════════════════════════════╗
║  CONSISTENCY LEVELS CHEAT SHEET                          ║
╠══════════════════════════════════════════════════════════╣
║  Read Concerns:                                          ║
║  • local          → Fastest, may be stale                ║
║  • majority       → Safe, won't rollback                 ║
║  • linearizable   → Slowest, always latest               ║
║                                                          ║
║  Write Concerns:                                         ║
║  • w:0            → No ack, UNSAFE                       ║
║  • w:1            → Primary ack                          ║
║  • w:majority     → Majority ack, SAFE                   ║
║                                                          ║
║  Read Preferences:                                       ║
║  • primary        → Always from leader                   ║
║  • secondary      → Offload to followers                 ║
║  • nearest        → Lowest latency                       ║
╚══════════════════════════════════════════════════════════╝
```

---

**🎓 Congratulations!** You now understand MongoDB replication and consistency models. Use NoSqlSim to experiment with these concepts hands-on. Try different scenarios, crash nodes, create partitions, and observe how MongoDB handles failures while maintaining data consistency.

**💡 Pro Tip:** The best way to learn is by breaking things! Don't be afraid to crash nodes, create network partitions, and test edge cases in NoSqlSim. That's what it's here for!

---

*NoSqlSim - Educational Tool for MongoDB Replication & Consistency*
*Created by: Mounir Gaiby & Amine Banan | Prof: Hanin | ISGA 2025*
