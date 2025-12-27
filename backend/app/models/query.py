from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class ReadConcernLevel(str, Enum):
    """Read concern levels"""
    LOCAL = "local"
    AVAILABLE = "available"
    MAJORITY = "majority"
    LINEARIZABLE = "linearizable"
    SNAPSHOT = "snapshot"


class WriteConcernLevel(str, Enum):
    """Write concern levels"""
    W0 = "w0"  # No acknowledgment
    W1 = "w1"  # Acknowledge from primary
    W2 = "w2"  # Acknowledge from primary + 1 secondary
    W3 = "w3"  # Acknowledge from primary + 2 secondaries
    MAJORITY = "majority"  # Acknowledge from majority
    CUSTOM = "custom"  # Custom w value


class ReadPreferenceMode(str, Enum):
    """Read preference modes"""
    PRIMARY = "primary"
    PRIMARY_PREFERRED = "primaryPreferred"
    SECONDARY = "secondary"
    SECONDARY_PREFERRED = "secondaryPreferred"
    NEAREST = "nearest"


class QueryRequest(BaseModel):
    """Request to execute a query"""
    # Target settings
    replica_set_name: Optional[str] = Field(None, description="Target replica set name (optional if only one exists)")
    target_node_id: Optional[str] = Field(None, description="Specific node ID to target (optional, overrides read preference)")
    database: str = Field(default="testdb", description="Database name")
    collection: str = Field(default="testcol", description="Collection name")

    # Operation type
    operation: str = Field(..., description="MongoDB operation type (find, findOne, insertOne, etc.)")

    # Read operations
    filter: Optional[Dict[str, Any]] = Field(None, description="Query filter for read/update/delete operations")
    limit: Optional[int] = Field(None, description="Limit for find operations")
    pipeline: Optional[List[Dict[str, Any]]] = Field(None, description="Aggregation pipeline")

    # Write operations
    document: Optional[Dict[str, Any]] = Field(None, description="Document for insertOne")
    documents: Optional[List[Dict[str, Any]]] = Field(None, description="Documents for insertMany")
    update: Optional[Dict[str, Any]] = Field(None, description="Update document for update operations")

    # Consistency settings
    read_concern: ReadConcernLevel = Field(
        default=ReadConcernLevel.LOCAL,
        description="Read concern level"
    )
    write_concern: WriteConcernLevel = Field(
        default=WriteConcernLevel.W1,
        description="Write concern level"
    )
    write_concern_w: Optional[int] = Field(
        None,
        description="Custom w value for write concern (used with CUSTOM level)"
    )
    read_preference: ReadPreferenceMode = Field(
        default=ReadPreferenceMode.PRIMARY,
        description="Read preference mode"
    )


class QueryMetrics(BaseModel):
    """Metrics collected during query execution"""
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
    nodes_accessed: List[str] = Field(default_factory=list, description="Nodes that served the query")
    documents_returned: int = Field(default=0, description="Number of documents returned or affected")

    # Consistency settings used
    read_concern_used: Optional[str] = Field(None, description="Read concern level used")
    write_concern_used: Optional[str] = Field(None, description="Write concern level used")
    read_preference_used: Optional[str] = Field(None, description="Read preference used")

    # Timestamps
    timestamp: datetime = Field(..., description="Query execution timestamp")


class QueryResult(BaseModel):
    """Result of a query execution"""
    success: bool = Field(..., description="Whether the query succeeded")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Query result data")
    metrics: QueryMetrics = Field(..., description="Query execution metrics")
    message: str = Field(..., description="Result message")
    error: Optional[str] = Field(None, description="Error message if failed")


class QueryHistoryItem(BaseModel):
    """A single query in the history"""
    timestamp: datetime = Field(..., description="Query execution timestamp")
    request: QueryRequest = Field(..., description="Original query request")
    result: QueryResult = Field(..., description="Query result")
