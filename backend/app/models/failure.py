from typing import Dict, List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class FailureState(BaseModel):
    """State of an active failure simulation"""
    failure_id: str = Field(..., description="Unique identifier for the failure")
    failure_type: Literal["node_crash", "network_partition", "latency_injection", "packet_loss"] = Field(
        ...,
        description="Type of failure"
    )
    affected_nodes: List[str] = Field(..., description="List of affected node IDs")
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the failure was initiated"
    )
    config: Dict = Field(default_factory=dict, description="Failure-specific configuration")
    description: str = Field(..., description="Human-readable description")


class PartitionConfig(BaseModel):
    """Configuration for network partition"""
    group_a: List[str] = Field(..., description="Node IDs in partition group A")
    group_b: List[str] = Field(..., description="Node IDs in partition group B")
    description: Optional[str] = Field(
        None,
        description="Description of the partition scenario"
    )


class LatencyConfig(BaseModel):
    """Configuration for latency injection"""
    node_id: str = Field(..., description="Target node ID")
    latency_ms: int = Field(
        ...,
        description="Latency to inject in milliseconds",
        ge=0,
        le=10000
    )
    jitter_ms: Optional[int] = Field(
        0,
        description="Random jitter in milliseconds",
        ge=0,
        le=1000
    )


class CrashNodeRequest(BaseModel):
    """Request to crash a node"""
    node_id: str = Field(..., description="Node ID to crash")
    crash_type: Literal["clean", "hard"] = Field(
        default="clean",
        description="Type of crash (clean=stop, hard=kill)"
    )


class RestoreNodeRequest(BaseModel):
    """Request to restore a crashed node"""
    node_id: str = Field(..., description="Node ID to restore")


class CreatePartitionRequest(BaseModel):
    """Request to create a network partition"""
    replica_set_name: str = Field(..., description="Target replica set name")
    partition_config: PartitionConfig = Field(..., description="Partition configuration")


class InjectLatencyRequest(BaseModel):
    """Request to inject network latency"""
    latency_config: LatencyConfig = Field(..., description="Latency configuration")


class FailureResponse(BaseModel):
    """Response from a failure operation"""
    success: bool = Field(..., description="Whether the operation succeeded")
    failure_id: Optional[str] = Field(None, description="ID of the created failure")
    message: str = Field(..., description="Status message")
    failure_state: Optional[FailureState] = Field(
        None,
        description="Current state of the failure"
    )
