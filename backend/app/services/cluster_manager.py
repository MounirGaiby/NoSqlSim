from pymongo import MongoClient
from pymongo.errors import PyMongoError
from typing import Dict, List, Optional
import logging
import time
import asyncio

from datetime import datetime
from app.config import settings
from app.models.cluster import (
    NodeConfig,
    ReplicaSetStatus,
    MemberStatus,
    ClusterState
)
from app.services.docker_manager import DockerManager

logger = logging.getLogger(__name__)


class ClusterManager:
    """Manages MongoDB replica sets"""

    def __init__(self, docker_manager: DockerManager):
        """Initialize cluster manager"""
        self.docker_manager = docker_manager
        self.mongo_clients: Dict[str, MongoClient] = {}
        self.replica_sets: Dict[str, List[NodeConfig]] = {}
        self.next_port = settings.mongodb_start_port

    async def get_cluster_status(self) -> ClusterState:
        """
        Get current status of all clusters
        
        Returns:
            ClusterState: Complete state of all clusters
        """
        replica_sets_status = {}

        for replica_set_name in self.replica_sets.keys():
            try:
                status = await self.get_replica_set_status(replica_set_name)
                replica_sets_status[replica_set_name] = status
            except Exception as e:
                logger.error(f"Error getting status for {replica_set_name}: {e}")
                # Skip failed replica sets or include with error state
                continue

        return ClusterState(
            timestamp=datetime.utcnow(),
            replica_sets=replica_sets_status,
            sharded_clusters=[],
            active_failures=[]
        )

    def _get_next_port(self) -> int:
        """Get next available port"""
        port = self.next_port
        self.next_port += 1
        return port

    def _get_mongo_client(self, host: str, port: int) -> MongoClient:
        """Get or create MongoDB client for a node"""
        connection_string = f"mongodb://{host}:{port}/?directConnection=true"

        if connection_string not in self.mongo_clients:
            try:
                client = MongoClient(
                    connection_string,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000
                )
                # Test connection
                client.admin.command('ping')
                self.mongo_clients[connection_string] = client
                logger.info(f"Created MongoDB client for {host}:{port}")
            except Exception as e:
                logger.error(f"Failed to create MongoDB client for {host}:{port}: {e}")
                raise

        return self.mongo_clients[connection_string]

    async def initialize_replica_set(
        self,
        replica_set_name: str,
        node_count: int = 3,
        starting_port: int = None
    ) -> ReplicaSetStatus:
        """
        Initialize a new replica set

        Args:
            replica_set_name: Name of the replica set
            node_count: Number of nodes to create
            starting_port: Starting port number (optional)

        Returns:
            ReplicaSetStatus: Status of the initialized replica set
        """
        if replica_set_name in self.replica_sets:
            raise ValueError(f"Replica set '{replica_set_name}' already exists")

        if starting_port:
            self.next_port = starting_port

        logger.info(f"Initializing replica set '{replica_set_name}' with {node_count} nodes")

        nodes = []
        try:
            # Create Docker containers
            for i in range(node_count):
                node_id = f"{replica_set_name}-node{i+1}"
                port = self._get_next_port()

                container = await self.docker_manager.create_replica_set_node(
                    node_id=node_id,
                    port=port,
                    replica_set_name=replica_set_name
                )

                node_config = NodeConfig(
                    node_id=node_id,
                    host="localhost",
                    port=port,
                    role="replica",
                    priority=1 if i < node_count else 0,  # Last node can be arbiter
                    votes=1
                )
                nodes.append(node_config)

                logger.info(f"Created node {node_id} on port {port}")

            # Wait for containers to be ready
            logger.info("Waiting for MongoDB instances to start...")
            await asyncio.sleep(5)

            # Initialize replica set on the first node
            primary_node = nodes[0]
            primary_client = self._get_mongo_client(primary_node.host, primary_node.port)

            # Build replica set configuration
            rs_config = {
                "_id": replica_set_name,
                "members": []
            }

            for idx, node in enumerate(nodes):
                hostname = self.docker_manager.get_node_connection_string(node.node_id)
                member = {
                    "_id": idx,
                    "host": hostname,
                    "priority": node.priority,
                    "votes": node.votes
                }
                rs_config["members"].append(member)

            # Initialize replica set
            logger.info(f"Initiating replica set with config: {rs_config}")
            result = primary_client.admin.command("replSetInitiate", rs_config)
            logger.info(f"Replica set initiation result: {result}")

            # Wait for replica set to stabilize
            logger.info("Waiting for replica set to elect primary...")
            await asyncio.sleep(10)

            # Store node configurations
            self.replica_sets[replica_set_name] = nodes

            # Get and return status
            status = await self.get_replica_set_status(replica_set_name)
            return status

        except Exception as e:
            logger.error(f"Failed to initialize replica set '{replica_set_name}': {e}")
            # Cleanup on failure
            for node in nodes:
                try:
                    await self.docker_manager.remove_node(node.node_id, force=True)
                except:
                    pass
            raise

    async def get_replica_set_status(self, replica_set_name: str) -> ReplicaSetStatus:
        """
        Get current status of a replica set

        Args:
            replica_set_name: Name of the replica set

        Returns:
            ReplicaSetStatus: Current status
        """
        if replica_set_name not in self.replica_sets:
            raise ValueError(f"Replica set '{replica_set_name}' not found")

        nodes = self.replica_sets[replica_set_name]

        try:
            # Try to connect to any node to get status
            status_data = None
            for node in nodes:
                try:
                    client = self._get_mongo_client(node.host, node.port)
                    status_data = client.admin.command("replSetGetStatus")
                    break
                except Exception as e:
                    logger.debug(f"Failed to get status from {node.node_id}: {e}")
                    continue

            if not status_data:
                # All nodes unreachable
                return ReplicaSetStatus(
                    set_name=replica_set_name,
                    primary=None,
                    members=[],
                    health="down"
                )

            # Parse status
            members = []
            primary = None

            for member_data in status_data.get("members", []):
                state = member_data.get("stateStr", "UNKNOWN")
                member_name = member_data.get("name", "")

                # Find corresponding node_id
                node_id = None
                for node in nodes:
                    conn_str = self.docker_manager.get_node_connection_string(node.node_id)
                    if conn_str == member_name:
                        node_id = node.node_id
                        break

                member_status = MemberStatus(
                    node_id=node_id or member_name,
                    name=member_name,
                    state=str(member_data.get("state", -1)),
                    state_str=state,
                    health=member_data.get("health", 0),
                    uptime=member_data.get("uptime", 0),
                    last_heartbeat=member_data.get("lastHeartbeat"),
                    ping_ms=member_data.get("pingMs")
                )
                members.append(member_status)

                if state == "PRIMARY":
                    primary = node_id or member_name

            # Determine overall health
            healthy_count = sum(1 for m in members if m.health == 1)
            if healthy_count == len(members):
                health = "ok"
            elif healthy_count > len(members) // 2:
                health = "degraded"
            else:
                health = "down"

            return ReplicaSetStatus(
                set_name=replica_set_name,
                primary=primary,
                members=members,
                health=health,
                term=status_data.get("term")
            )

        except Exception as e:
            logger.error(f"Failed to get status for '{replica_set_name}': {e}")
            raise

    async def add_member(
        self,
        replica_set_name: str,
        role: str = "replica",
        priority: int = 1
    ) -> NodeConfig:
        """
        Add a new member to a replica set

        Args:
            replica_set_name: Name of the replica set
            role: Node role (replica or arbiter)
            priority: Election priority

        Returns:
            NodeConfig: Configuration of the added node
        """
        if replica_set_name not in self.replica_sets:
            raise ValueError(f"Replica set '{replica_set_name}' not found")

        nodes = self.replica_sets[replica_set_name]

        # Create new node
        node_count = len(nodes)
        node_id = f"{replica_set_name}-node{node_count+1}"
        port = self._get_next_port()

        logger.info(f"Adding node {node_id} to replica set '{replica_set_name}'")

        # Create Docker container
        await self.docker_manager.create_replica_set_node(
            node_id=node_id,
            port=port,
            replica_set_name=replica_set_name,
            role=role
        )

        # Wait for container to start
        await asyncio.sleep(3)

        # Get current replica set config
        primary_node = nodes[0]
        client = self._get_mongo_client(primary_node.host, primary_node.port)

        config = client.admin.command("replSetGetConfig")["config"]
        version = config["version"]

        # Add new member to config
        hostname = self.docker_manager.get_node_connection_string(node_id)
        new_member_id = max([m["_id"] for m in config["members"]]) + 1

        config["members"].append({
            "_id": new_member_id,
            "host": hostname,
            "priority": priority if role == "replica" else 0,
            "votes": 1 if role == "replica" else 1
        })
        config["version"] = version + 1

        # Reconfigure replica set
        client.admin.command("replSetReconfig", config)
        logger.info(f"Added node {node_id} to replica set")

        # Update stored configuration
        node_config = NodeConfig(
            node_id=node_id,
            host="localhost",
            port=port,
            role=role,
            priority=priority,
            votes=1
        )
        self.replica_sets[replica_set_name].append(node_config)

        return node_config

    async def remove_member(self, replica_set_name: str, node_id: str) -> bool:
        """
        Remove a member from a replica set

        Args:
            replica_set_name: Name of the replica set
            node_id: ID of the node to remove

        Returns:
            bool: True if successful
        """
        if replica_set_name not in self.replica_sets:
            raise ValueError(f"Replica set '{replica_set_name}' not found")

        nodes = self.replica_sets[replica_set_name]

        # Find node
        node_to_remove = None
        for node in nodes:
            if node.node_id == node_id:
                node_to_remove = node
                break

        if not node_to_remove:
            raise ValueError(f"Node '{node_id}' not found in replica set")

        logger.info(f"Removing node {node_id} from replica set '{replica_set_name}'")

        # Get primary connection
        primary_node = nodes[0]
        client = self._get_mongo_client(primary_node.host, primary_node.port)

        # Get current config
        config = client.admin.command("replSetGetConfig")["config"]
        version = config["version"]

        # Remove member from config
        hostname = self.docker_manager.get_node_connection_string(node_id)
        config["members"] = [m for m in config["members"] if m["host"] != hostname]
        config["version"] = version + 1

        # Reconfigure replica set
        client.admin.command("replSetReconfig", config)
        logger.info(f"Removed {node_id} from replica set config")

        # Stop and remove Docker container
        await self.docker_manager.remove_node(node_id, force=True)

        # Update stored configuration
        self.replica_sets[replica_set_name] = [n for n in nodes if n.node_id != node_id]

        return True

    async def step_down_primary(
        self,
        replica_set_name: str,
        step_down_secs: int = 10
    ) -> bool:
        """
        Step down the current primary node

        Args:
            replica_set_name: Name of the replica set
            step_down_secs: Seconds to remain stepped down

        Returns:
            bool: True if successful
        """
        status = await self.get_replica_set_status(replica_set_name)

        if not status.primary:
            # Check if there are any healthy secondaries that could become primary
            healthy_secondaries = [m for m in status.members if m.state_str == 'SECONDARY' and m.health == 1]
            if not healthy_secondaries:
                raise ValueError("No primary node found and no healthy secondaries available. "
                               "Start or recover some secondary nodes before an election can occur.")
            
            # Wait for election to complete (up to 15 seconds)
            logger.info("No primary found, waiting for election to complete...")
            for i in range(15):
                await asyncio.sleep(1)
                status = await self.get_replica_set_status(replica_set_name)
                if status.primary:
                    logger.info(f"Election completed, new primary: {status.primary}")
                    break
            else:
                raise ValueError("No primary node found - election is taking longer than expected. Please wait and try again.")

        # Find primary node
        primary_node = None
        for node in self.replica_sets[replica_set_name]:
            if node.node_id == status.primary:
                primary_node = node
                break

        if not primary_node:
            raise ValueError("Primary node not found in configuration")

        logger.info(f"Stepping down primary {primary_node.node_id}")

        try:
            client = self._get_mongo_client(primary_node.host, primary_node.port)
            # Try normal stepdown first
            try:
                client.admin.command("replSetStepDown", step_down_secs)
            except PyMongoError as stepdown_error:
                error_msg = str(stepdown_error).lower()
                # If no electable secondaries, DON'T force - that would leave the cluster without a primary
                if 'no electable secondaries' in error_msg or 'exceededtimelimit' in error_msg:
                    logger.warning(f"No electable secondaries available: {stepdown_error}")
                    raise ValueError(
                        "Cannot step down: no electable secondaries available. "
                        "All other nodes are either down or still in their stepdown period. "
                        "Please wait for other nodes to become eligible or start more nodes."
                    )
                else:
                    raise
        except PyMongoError as e:
            # replSetStepDown closes the connection, which raises an error
            # This is expected behavior - check if it says "connection closed" or similar
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['connection closed', 'socket', 'network', 'not primary', 'not master']):
                # This is expected - the stepdown worked and closed our connection
                logger.info(f"Primary stepped down for {step_down_secs} seconds (connection closed as expected)")
                # Remove the cached client since the connection is now invalid
                connection_string = f"mongodb://{primary_node.host}:{primary_node.port}/?directConnection=true"
                if connection_string in self.mongo_clients:
                    try:
                        self.mongo_clients[connection_string].close()
                    except:
                        pass
                    del self.mongo_clients[connection_string]
                return True
            else:
                # This is an actual error
                logger.error(f"Error stepping down primary: {e}")
                raise

        logger.info(f"Primary stepped down for {step_down_secs} seconds")
        return True

    async def cleanup(self, replica_set_name: str):
        """Cleanup a replica set and all its nodes"""
        if replica_set_name not in self.replica_sets:
            return

        logger.info(f"Cleaning up replica set '{replica_set_name}'")

        nodes = self.replica_sets[replica_set_name]
        for node in nodes:
            try:
                await self.docker_manager.remove_node(node.node_id, force=True)
            except Exception as e:
                logger.error(f"Failed to remove node {node.node_id}: {e}")

        del self.replica_sets[replica_set_name]
        logger.info(f"Cleaned up replica set '{replica_set_name}'")


# Global instance
cluster_manager = None

def get_cluster_manager(docker_manager: DockerManager) -> ClusterManager:
    """Get or create cluster manager instance"""
    global cluster_manager
    if cluster_manager is None:
        cluster_manager = ClusterManager(docker_manager)
    return cluster_manager
