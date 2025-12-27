from fastapi import APIRouter, HTTPException
from typing import Dict
from datetime import datetime

from app.models.cluster import (
    InitClusterRequest,
    AddNodeRequest,
    StepDownRequest,
    ClusterState,
    ReplicaSetStatus
)
from app.services.docker_manager import docker_manager
from app.services.cluster_manager import get_cluster_manager
from app.websocket.broadcaster import broadcaster

router = APIRouter()

# Get cluster manager instance
cluster_mgr = get_cluster_manager(docker_manager)


@router.post("/init")
async def initialize_cluster(request: InitClusterRequest):
    """Initialize a new replica set"""
    try:
        status = await cluster_mgr.initialize_replica_set(
            replica_set_name=request.replica_set_name,
            node_count=request.node_count,
            starting_port=request.starting_port
        )

        # Immediately broadcast updated cluster state
        cluster_state = await cluster_mgr.get_cluster_status()
        await broadcaster.broadcast_cluster_state(cluster_state)

        return {
            "success": True,
            "message": f"Initialized replica set '{request.replica_set_name}' with {request.node_count} nodes",
            "replica_set_name": request.replica_set_name,
            "status": status.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_cluster_status() -> ClusterState:
    """Get current status of all clusters"""
    return await cluster_mgr.get_cluster_status()


@router.get("/status/{replica_set_name}")
async def get_replica_set_status(replica_set_name: str) -> ReplicaSetStatus:
    """Get status of a specific replica set"""
    try:
        status = await cluster_mgr.get_replica_set_status(replica_set_name)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodes")
async def add_node(request: AddNodeRequest):
    """Add a new node to a replica set"""
    try:
        node_config = await cluster_mgr.add_member(
            replica_set_name=request.replica_set_name,
            role=request.role,
            priority=request.priority
        )

        # Immediately broadcast updated cluster state
        cluster_state = await cluster_mgr.get_cluster_status()
        await broadcaster.broadcast_cluster_state(cluster_state)

        return {
            "success": True,
            "message": f"Added {request.role} node to replica set '{request.replica_set_name}'",
            "node": node_config.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/nodes/{node_id}")
async def remove_node(node_id: str, replica_set_name: str):
    """Remove a node from a replica set"""
    try:
        success = await cluster_mgr.remove_member(replica_set_name, node_id)

        # Immediately broadcast updated cluster state
        cluster_state = await cluster_mgr.get_cluster_status()
        await broadcaster.broadcast_cluster_state(cluster_state)

        return {
            "success": success,
            "message": f"Removed node '{node_id}' from replica set '{replica_set_name}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stepdown")
async def step_down_primary(request: StepDownRequest):
    """Step down the current primary node"""
    try:
        success = await cluster_mgr.step_down_primary(
            replica_set_name=request.replica_set_name,
            step_down_secs=request.step_down_secs
        )

        # Immediately broadcast updated cluster state
        cluster_state = await cluster_mgr.get_cluster_status()
        await broadcaster.broadcast_cluster_state(cluster_state)

        return {
            "success": success,
            "message": f"Stepped down primary in replica set '{request.replica_set_name}'"
        }
    except ValueError as e:
        # No primary found - likely election in progress
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}/logs")
async def get_node_logs(node_id: str, tail: int = 100):
    """Get logs for a specific node"""
    try:
        logs = await docker_manager.get_container_logs(node_id, tail=tail)
        return {"node_id": node_id, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
