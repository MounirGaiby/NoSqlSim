from fastapi import APIRouter, HTTPException
from typing import List

from app.models.failure import (
    CrashNodeRequest,
    RestoreNodeRequest,
    CreatePartitionRequest,
    InjectLatencyRequest,
    FailureResponse,
    FailureState
)
from app.services.docker_manager import docker_manager
from app.services.failure_simulator import get_failure_simulator

router = APIRouter()

# Get failure simulator instance
failure_sim = get_failure_simulator(docker_manager)


@router.post("/crash", response_model=FailureResponse)
async def crash_node(request: CrashNodeRequest):
    """Crash a MongoDB node"""
    try:
        failure_state = await failure_sim.crash_node(
            node_id=request.node_id,
            crash_type=request.crash_type
        )

        return FailureResponse(
            success=True,
            failure_id=failure_state.failure_id,
            message=f"Crashed node '{request.node_id}' ({request.crash_type} crash)",
            failure_state=failure_state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore", response_model=FailureResponse)
async def restore_node(request: RestoreNodeRequest):
    """Restore a crashed node"""
    try:
        success = await failure_sim.restore_node(request.node_id)

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restore node '{request.node_id}'"
            )

        return FailureResponse(
            success=True,
            message=f"Restored node '{request.node_id}'"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/partition", response_model=FailureResponse)
async def create_partition(request: CreatePartitionRequest):
    """Create a network partition"""
    try:
        failure_state = await failure_sim.create_network_partition(
            replica_set_name=request.replica_set_name,
            partition_config=request.partition_config
        )

        return FailureResponse(
            success=True,
            failure_id=failure_state.failure_id,
            message=f"Created network partition in '{request.replica_set_name}'",
            failure_state=failure_state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heal", response_model=FailureResponse)
async def heal_partition():
    """Heal all network partitions"""
    try:
        success = await failure_sim.heal_network_partition()

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to heal network partitions"
            )

        return FailureResponse(
            success=True,
            message="Healed all network partitions"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/latency", response_model=FailureResponse)
async def inject_latency(request: InjectLatencyRequest):
    """Inject network latency to a node"""
    try:
        failure_state = await failure_sim.inject_latency(
            node_id=request.latency_config.node_id,
            latency_ms=request.latency_config.latency_ms,
            jitter_ms=request.latency_config.jitter_ms or 0
        )

        return FailureResponse(
            success=True,
            failure_id=failure_state.failure_id,
            message=f"Injecting {request.latency_config.latency_ms}ms latency to node '{request.latency_config.node_id}'",
            failure_state=failure_state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=List[FailureState])
async def get_active_failures():
    """Get all active failure simulations"""
    try:
        failures = failure_sim.get_active_failures()
        return list(failures.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{failure_id}", response_model=FailureResponse)
async def clear_failure(failure_id: str):
    """Clear a specific failure simulation"""
    try:
        success = await failure_sim.clear_failure(failure_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Failure '{failure_id}' not found"
            )

        return FailureResponse(
            success=True,
            message=f"Cleared failure '{failure_id}'"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
