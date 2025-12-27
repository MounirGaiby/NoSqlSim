from typing import Dict, List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    """Configuration for a MongoDB node"""
    node_id: str = Field(..., description="Unique identifier for the node")
    host: str = Field(default="localhost", description="Host address")
    port: int = Field(..., description="Port number", ge=1024, le=65535)
    role: Literal["replica", "arbiter"] = Field(
        default="replica",
        description="Node role in replica set"
    )
    priority: int = Field(default=1, description="Election priority", ge=0, le=1000)
    votes: int = Field(default=1, description="Number of votes in elections", ge=0, le=1)


class TopologyConfig(BaseModel):
    """Configuration for cluster topology"""
    topology_type: Literal["replica_set", "sharded"] = Field(
        ...,
        description="Type of cluster topology"
    )
    replica_set_name: str = Field(..., description="Name of the replica set")
    nodes: List[NodeConfig] = Field(..., description="List of nodes in the cluster")


class MemberStatus(BaseModel):
    """Status of a single replica set member"""
    node_id: str = Field(..., description="Node identifier")
    name: str = Field(..., description="Node name (host:port)")
    state: str = Field(..., description="Node state (PRIMARY, SECONDARY, ARBITER, etc.)")
    state_str: str = Field(..., description="Human-readable state string")
    health: int = Field(..., description="Health status (0=down, 1=up)")
    uptime: int = Field(..., description="Uptime in seconds")
    optime: Optional[datetime] = Field(None, description="Last operation time")
    last_heartbeat: Optional[datetime] = Field(None, description="Last heartbeat time")
    ping_ms: Optional[int] = Field(None, description="Ping time in milliseconds")


class ReplicaSetStatus(BaseModel):
    """Status of a replica set"""
    set_name: str = Field(..., description="Replica set name")
    primary: Optional[str] = Field(None, description="Current primary node")
    members: List[MemberStatus] = Field(..., description="List of member statuses")
    health: Literal["ok", "degraded", "down"] = Field(
        ...,
        description="Overall health status"
    )
    term: Optional[int] = Field(None, description="Current election term")


class ShardInfo(BaseModel):
    """Information about a shard in a sharded cluster"""
    shard_id: str = Field(..., description="Shard identifier")
    host: str = Field(..., description="Shard host connection string")
    state: int = Field(..., description="Shard state (1=active)")


class ShardedClusterStatus(BaseModel):
    """Status of a sharded cluster"""
    cluster_name: str = Field(..., description="Cluster name")
    config_servers: List[str] = Field(..., description="Config server addresses")
    mongos_routers: List[str] = Field(..., description="Mongos router addresses")
    shards: List[ShardInfo] = Field(..., description="List of shards")
    databases: Dict[str, bool] = Field(
        default_factory=dict,
        description="Databases with sharding enabled"
    )


class ClusterState(BaseModel):
    """Complete state of all clusters"""
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="State timestamp"
    )
    replica_sets: Dict[str, ReplicaSetStatus] = Field(
        default_factory=dict,
        description="Map of replica set name to status"
    )
    sharded_clusters: List[ShardedClusterStatus] = Field(
        default_factory=list,
        description="List of sharded clusters"
    )
    active_failures: List[str] = Field(
        default_factory=list,
        description="List of active failure IDs"
    )


class InitClusterRequest(BaseModel):
    """Request to initialize a cluster"""
    replica_set_name: str = Field(default="rs0", description="Name of the replica set")
    node_count: int = Field(default=3, description="Number of nodes", ge=1, le=7)
    starting_port: int = Field(
        default=27017,
        description="Starting port for nodes",
        ge=1024,
        le=65535
    )


class AddNodeRequest(BaseModel):
    """Request to add a node to replica set"""
    replica_set_name: str = Field(..., description="Target replica set name")
    role: Literal["replica", "arbiter"] = Field(
        default="replica",
        description="Node role"
    )
    priority: int = Field(default=1, description="Election priority", ge=0, le=1000)


class StepDownRequest(BaseModel):
    """Request to step down primary node"""
    replica_set_name: str = Field(..., description="Target replica set name")
    step_down_secs: int = Field(
        default=10,
        description="Seconds to remain stepped down",
        ge=0,
        le=3600
    )
