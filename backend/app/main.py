from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio

from app.config import settings
from app.api.routes import cluster, queries, failures
from app.websocket.broadcaster import broadcaster
from app.services.docker_manager import docker_manager
from app.services.cluster_manager import cluster_manager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Background task for monitoring cluster state
background_task = None
shutdown_event = asyncio.Event()


async def monitor_cluster_state():
    """Background task that monitors cluster state and broadcasts updates"""
    logger.info("Starting cluster state monitoring task")

    while not shutdown_event.is_set():
        try:
            # Get current cluster status
            status = await cluster_manager.get_cluster_status()

            # Broadcast to all connected WebSocket clients
            if status:
                await broadcaster.broadcast_cluster_state(status)

            # Wait before next check (1 second interval)
            await asyncio.sleep(settings.cluster_poll_interval_seconds)

        except Exception as e:
            logger.error(f"Error in cluster monitoring task: {e}")
            await asyncio.sleep(settings.cluster_poll_interval_seconds)

    logger.info("Cluster state monitoring task stopped")


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    global background_task

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")

    # Startup: Cleanup any leftover containers from previous runs
    try:
        await docker_manager.cleanup_all()
    except Exception as e:
        logger.warning(f"Failed to cleanup leftover resources: {e}")

    # Startup: Start background monitoring task
    background_task = asyncio.create_task(monitor_cluster_state())
    logger.info("Background cluster monitoring started")

    yield

    # Shutdown: Cleanup resources
    logger.info(f"Shutting down {settings.app_name}")
    shutdown_event.set()
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("Background task cancelled successfully")
    
    # Cleanup Docker resources
    try:
        await docker_manager.cleanup_all()
    except Exception as e:
        logger.error(f"Failed to cleanup resources on shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Educational MongoDB simulation for understanding replication and consistency models",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Educational MongoDB Simulation",
        "team": {
            "creators": ["Mounir Gaiby", "Amine Banan"],
            "professor": "Prof Hanin",
            "class": "3CI Big Data and Artificial Intelligence",
            "module": "NoSQL",
            "school": "ISGA",
            "year": "2025/2026"
        },
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time cluster state updates"""
    await broadcaster.connect(websocket)
    logger.info(f"WebSocket client connected. Total connections: {broadcaster.get_connection_count()}")

    try:
        # Keep connection alive and handle incoming messages
        while True:
            # Wait for messages from client (for potential future use)
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")

            # Could handle client subscriptions, filters, etc. here in the future

    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {broadcaster.get_connection_count()}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await broadcaster.disconnect(websocket)


# Include routers
app.include_router(cluster.router, prefix="/api/cluster", tags=["Cluster Management"])
app.include_router(queries.router, prefix="/api/queries", tags=["Query Execution"])
app.include_router(failures.router, prefix="/api/failures", tags=["Failure Simulation"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
