import docker
from docker.models.containers import Container
from docker.models.networks import Network
from typing import Dict, List, Optional
import logging
from pathlib import Path

from app.config import settings
from app.models.cluster import NodeConfig

logger = logging.getLogger(__name__)


class DockerManager:
    """Manages Docker containers for MongoDB nodes"""

    def __init__(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            self.client.ping()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

        self.containers: Dict[str, Container] = {}
        self.networks: Dict[str, Network] = {}
        self._ensure_default_network()

    def _ensure_default_network(self):
        """Ensure the default nosqlsim network exists"""
        network_name = f"{settings.docker_network_prefix}_default"
        try:
            network = self.client.networks.get(network_name)
            self.networks[network_name] = network
            logger.info(f"Using existing network: {network_name}")
        except docker.errors.NotFound:
            network = self.client.networks.create(
                network_name,
                driver="bridge"
            )
            self.networks[network_name] = network
            logger.info(f"Created network: {network_name}")

    def _get_container_name(self, node_id: str) -> str:
        """Generate container name from node ID"""
        return f"{settings.docker_container_prefix}-{node_id}"

    def _get_node_hostname(self, node_id: str) -> str:
        """Generate hostname from node ID"""
        return f"mongo-{node_id}"

    async def create_replica_set_node(
        self,
        node_id: str,
        port: int,
        replica_set_name: str,
        role: str = "replica"
    ) -> Container:
        """
        Create and start a MongoDB container for a replica set node

        Args:
            node_id: Unique identifier for the node
            port: External port to expose
            replica_set_name: Name of the replica set
            role: Node role (replica or arbiter)

        Returns:
            Container: The created Docker container
        """
        container_name = self._get_container_name(node_id)
        hostname = self._get_node_hostname(node_id)

        # Check if container already exists
        if node_id in self.containers:
            logger.warning(f"Container {container_name} already exists")
            return self.containers[node_id]

        try:
            # MongoDB command
            command = f"mongod --replSet {replica_set_name} --bind_ip_all --port 27017"

            # Create container with NET_ADMIN capability for network partition simulation
            container = self.client.containers.run(
                image=f"mongo:{settings.mongodb_version}",
                name=container_name,
                hostname=hostname,
                command=command,
                ports={'27017/tcp': port},
                network=f"{settings.docker_network_prefix}_default",
                environment={
                    "MONGO_INITDB_DATABASE": "admin"
                },
                cap_add=['NET_ADMIN'],  # Required for iptables in partition simulation
                mem_limit=settings.docker_memory_limit,
                detach=True,
                remove=False
            )

            self.containers[node_id] = container
            logger.info(f"Created container {container_name} on port {port}")

            return container

        except Exception as e:
            logger.error(f"Failed to create container {container_name}: {e}")
            raise

    async def remove_node(self, node_id: str, force: bool = False) -> bool:
        """
        Remove a MongoDB container

        Args:
            node_id: Node identifier
            force: Force remove even if running

        Returns:
            bool: True if successful
        """
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                # Try to get container from Docker
                try:
                    container = self.client.containers.get(container_name)
                    self.containers[node_id] = container
                except docker.errors.NotFound:
                    logger.warning(f"Container {container_name} not found")
                    return False

            container = self.containers[node_id]

            # Stop and remove container
            if container.status == "running":
                container.stop(timeout=10)
                logger.info(f"Stopped container {container_name}")

            container.remove(force=force)
            logger.info(f"Removed container {container_name}")

            del self.containers[node_id]
            return True

        except Exception as e:
            logger.error(f"Failed to remove container {container_name}: {e}")
            return False

    async def stop_node(self, node_id: str) -> bool:
        """Stop a MongoDB container (for crash simulation)"""
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container

            container = self.containers[node_id]
            container.stop(timeout=5)
            logger.info(f"Stopped container {container_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop container {container_name}: {e}")
            return False

    async def start_node(self, node_id: str) -> bool:
        """Start a stopped MongoDB container"""
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container

            container = self.containers[node_id]
            container.start()
            logger.info(f"Started container {container_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start container {container_name}: {e}")
            return False

    async def kill_node(self, node_id: str) -> bool:
        """Kill a MongoDB container (hard crash)"""
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container

            container = self.containers[node_id]
            container.kill()
            logger.info(f"Killed container {container_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to kill container {container_name}: {e}")
            return False

    async def get_container_stats(self, node_id: str) -> Dict:
        """Get container resource stats"""
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container

            container = self.containers[node_id]
            stats = container.stats(stream=False)
            return stats

        except Exception as e:
            logger.error(f"Failed to get stats for {container_name}: {e}")
            return {}

    def get_node_connection_string(self, node_id: str) -> str:
        """Get MongoDB connection string for a node"""
        hostname = self._get_node_hostname(node_id)
        # For internal network communication
        return f"{hostname}:27017"

    def get_node_external_connection_string(self, node_id: str, port: int) -> str:
        """Get external MongoDB connection string for a node"""
        return f"localhost:{port}"

    def get_replica_set_connection_string(self, replica_set_name: str, nodes: list) -> str:
        """
        Get MongoDB connection string for a replica set using external ports
        
        NOTE: We use directConnection=true to connect to individual nodes because
        the replica set is configured with internal Docker hostnames that are not
        accessible from the host machine. This bypasses replica set discovery.
        
        Args:
            replica_set_name: Name of the replica set
            nodes: List of NodeConfig objects with host and port info
            
        Returns:
            str: MongoDB connection string for the replica set
        """
        if not nodes:
            raise ValueError(f"No nodes provided for replica set '{replica_set_name}'")
        
        # For external access, we need to connect directly to a node
        # We'll try to find an available node (preferring the first one which is often primary)
        # Using directConnection=true bypasses replica set discovery which would fail
        # because the internal Docker hostnames are not accessible from host
        first_node = nodes[0]
        
        return f"mongodb://{first_node.host}:{first_node.port}/?directConnection=true"

    def get_replica_set_primary_connection_string(self, nodes: list) -> str:
        """
        Get connection string for the primary node in a replica set
        Falls back to first node if no primary can be determined
        
        Args:
            nodes: List of NodeConfig objects
            
        Returns:
            str: MongoDB connection string with directConnection=true
        """
        if not nodes:
            raise ValueError("No nodes provided")
        
        # Default to first node
        node = nodes[0]
        return f"mongodb://{node.host}:{node.port}/?directConnection=true"

    async def attach_to_network(self, node_id: str, network_name: str):
        """Attach a container to a Docker network"""
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container

            # Always refresh network object from Docker to avoid using stale cached references
            try:
                network = self.client.networks.get(network_name)
                self.networks[network_name] = network
            except docker.errors.NotFound:
                network = self.client.networks.create(network_name, driver="bridge")
                self.networks[network_name] = network

            container = self.containers[node_id]

            network.connect(container)
            logger.info(f"Attached {container_name} to network {network_name}")

        except Exception as e:
            logger.error(f"Failed to attach {container_name} to {network_name}: {e}")
            raise

    async def detach_from_network(self, node_id: str, network_name: str):
        """Detach a container from a Docker network"""
        container_name = self._get_container_name(node_id)

        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container

            # Always refresh network object from Docker to avoid using stale cached references
            try:
                network = self.client.networks.get(network_name)
                self.networks[network_name] = network
            except docker.errors.NotFound:
                logger.debug(f"Network {network_name} not found, nothing to detach")
                return

            container = self.containers[node_id]

            network.disconnect(container)
            logger.info(f"Detached {container_name} from network {network_name}")

        except Exception as e:
            logger.error(f"Failed to detach {container_name} from {network_name}: {e}")
            raise

    async def get_container_logs(self, node_id: str, tail: int = 100) -> str:
        """Get logs from a container"""
        container_name = self._get_container_name(node_id)
        try:
            if node_id not in self.containers:
                container = self.client.containers.get(container_name)
                self.containers[node_id] = container
            
            container = self.containers[node_id]
            # logs returns bytes, decode to string
            return container.logs(tail=tail).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to get logs for {container_name}: {e}")
            return f"Error retrieving logs: {str(e)}"

    async def cleanup_all(self):
        """Cleanup all nosqlsim containers and networks"""
        logger.info("Cleaning up all nosqlsim resources")

        # Remove containers
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"name": settings.docker_container_prefix}
            )
            for container in containers:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.info(f"Removed container {container.name}")
                except Exception as e:
                    logger.error(f"Failed to remove container {container.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")

        # Remove networks (except default)
        try:
            networks = self.client.networks.list(
                names=[f"{settings.docker_network_prefix}_*"]
            )
            for network in networks:
                # Do not remove the default network as it might be used by other services or difficult to recreate cleanly
                if network.name != f"{settings.docker_network_prefix}_default":
                    try:
                        network.remove()
                        logger.info(f"Removed network {network.name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove network {network.name} (might be in use): {e}")
        except Exception as e:
            logger.error(f"Failed to list networks: {e}")

        self.containers.clear()
        self.networks.clear()


# Global instance
docker_manager = DockerManager()
