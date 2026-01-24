import logging
from typing import Dict
from datetime import datetime
import uuid

from app.services.docker_manager import DockerManager
from app.models.failure import FailureState, PartitionConfig

logger = logging.getLogger(__name__)


class FailureSimulator:
    """Simulates various failure scenarios in MongoDB clusters"""

    def __init__(self, docker_manager: DockerManager):
        """Initialize failure simulator"""
        self.docker_manager = docker_manager
        self.active_failures: Dict[str, FailureState] = {}

    async def crash_node(
        self,
        node_id: str,
        crash_type: str = "clean"
    ) -> FailureState:
        """
        Crash a MongoDB node

        Args:
            node_id: Node identifier
            crash_type: Type of crash (clean=stop, hard=kill)

        Returns:
            FailureState: State of the created failure
        """
        failure_id = f"crash-{node_id}-{uuid.uuid4().hex[:8]}"

        logger.info(f"Crashing node {node_id} ({crash_type} crash)")

        try:
            if crash_type == "hard":
                success = await self.docker_manager.kill_node(node_id)
            else:
                success = await self.docker_manager.stop_node(node_id)

            if not success:
                raise Exception(f"Failed to crash node {node_id}")

            failure_state = FailureState(
                failure_id=failure_id,
                failure_type="node_crash",
                affected_nodes=[node_id],
                started_at=datetime.utcnow(),
                config={"crash_type": crash_type},
                description=f"{crash_type.capitalize()} crash of node {node_id}"
            )

            self.active_failures[failure_id] = failure_state
            logger.info(f"Node {node_id} crashed successfully")

            return failure_state

        except Exception as e:
            logger.error(f"Failed to crash node {node_id}: {e}")
            raise

    async def restore_node(self, node_id: str) -> bool:
        """
        Restore a crashed node

        Args:
            node_id: Node identifier

        Returns:
            bool: True if successful
        """
        logger.info(f"Restoring node {node_id}")

        try:
            success = await self.docker_manager.start_node(node_id)

            if success:
                # Remove failure states for this node
                failures_to_remove = [
                    fid for fid, failure in self.active_failures.items()
                    if node_id in failure.affected_nodes and failure.failure_type == "node_crash"
                ]

                for fid in failures_to_remove:
                    del self.active_failures[fid]
                    logger.info(f"Removed failure state {fid}")

                logger.info(f"Node {node_id} restored successfully")

            return success

        except Exception as e:
            logger.error(f"Failed to restore node {node_id}: {e}")
            return False

    async def create_network_partition(
        self,
        replica_set_name: str,
        partition_config: PartitionConfig
    ) -> FailureState:
        """
        Create a network partition between two groups of nodes.
        
        This implementation uses Docker network manipulation to isolate nodes.
        Nodes in different partition groups cannot communicate with each other,
        but the backend can still reach all nodes for monitoring.

        Args:
            replica_set_name: Name of the replica set
            partition_config: Partition configuration

        Returns:
            FailureState: State of the created failure
        """
        failure_id = f"partition-{replica_set_name}-{uuid.uuid4().hex[:8]}"

        logger.info(f"Creating network partition in {replica_set_name}")
        logger.info(f"Group A: {partition_config.group_a}")
        logger.info(f"Group B: {partition_config.group_b}")

        try:
            # Strategy: Use /etc/hosts manipulation to block inter-node communication
            # This works on all platforms and doesn't require iptables or tc
            
            # Get container IPs for all nodes
            node_ips = {}
            for node_id in partition_config.group_a + partition_config.group_b:
                container_name = self.docker_manager._get_container_name(node_id)
                container = self.docker_manager.client.containers.get(container_name)
                container.reload()  # Refresh container info
                
                # Get internal container hostname (used for replica set communication)
                internal_hostname = f"mongo-{node_id}"
                
                # Get IP from default network
                networks = container.attrs['NetworkSettings']['Networks']
                if 'nosqlsim_default' in networks:
                    ip = networks['nosqlsim_default']['IPAddress']
                    node_ips[node_id] = {'ip': ip, 'hostname': internal_hostname, 'container': container}
                    logger.info(f"Node {node_id}: {internal_hostname} -> {ip}")
                else:
                    logger.warning(f"Node {node_id} not on nosqlsim_default network")
            
            # For nodes in group A, block communication to group B by adding fake /etc/hosts entries
            for node_id in partition_config.group_a:
                if node_id not in node_ips:
                    continue
                container = node_ips[node_id]['container']
                
                # Block each node in group B
                for target_node_id in partition_config.group_b:
                    if target_node_id not in node_ips:
                        continue
                    target_hostname = node_ips[target_node_id]['hostname']
                    # Point the target hostname to a non-routable IP (this blocks DNS resolution)
                    # Using 127.0.0.255 which will fail to connect
                    try:
                        exec_result = container.exec_run(
                            f"sh -c 'echo \"127.0.0.255 {target_hostname}\" >> /etc/hosts'",
                            user='root'
                        )
                        if exec_result.exit_code == 0:
                            logger.info(f"Blocked {node_id} -> {target_node_id} ({target_hostname})")
                        else:
                            logger.warning(f"Failed to block {node_id} -> {target_node_id}: {exec_result.output.decode()}")
                    except Exception as e:
                        logger.error(f"Error blocking {node_id} -> {target_node_id}: {e}")
            
            # For nodes in group B, block communication to group A
            for node_id in partition_config.group_b:
                if node_id not in node_ips:
                    continue
                container = node_ips[node_id]['container']
                
                for target_node_id in partition_config.group_a:
                    if target_node_id not in node_ips:
                        continue
                    target_hostname = node_ips[target_node_id]['hostname']
                    try:
                        exec_result = container.exec_run(
                            f"sh -c 'echo \"127.0.0.255 {target_hostname}\" >> /etc/hosts'",
                            user='root'
                        )
                        if exec_result.exit_code == 0:
                            logger.info(f"Blocked {node_id} -> {target_node_id} ({target_hostname})")
                        else:
                            logger.warning(f"Failed to block {node_id} -> {target_node_id}: {exec_result.output.decode()}")
                    except Exception as e:
                        logger.error(f"Error blocking {node_id} -> {target_node_id}: {e}")

            affected_nodes = partition_config.group_a + partition_config.group_b

            failure_state = FailureState(
                failure_id=failure_id,
                failure_type="network_partition",
                affected_nodes=affected_nodes,
                started_at=datetime.utcnow(),
                config=partition_config.model_dump(),
                description=partition_config.description or f"Network partition in {replica_set_name}"
            )

            self.active_failures[failure_id] = failure_state
            logger.info(f"Network partition created: {failure_id}")

            return failure_state

        except Exception as e:
            logger.error(f"Failed to create network partition: {e}")
            raise

    async def heal_network_partition(self) -> bool:
        """
        Heal all network partitions by restoring /etc/hosts

        Returns:
            bool: True if successful
        """
        logger.info("Healing all network partitions")

        try:
            # Get all partition failures
            partition_failures = [
                f for f in self.active_failures.values()
                if f.failure_type == "network_partition"
            ]

            if not partition_failures:
                logger.info("No active partitions to heal")
                return True

            # Restore all affected nodes
            affected_nodes = set()
            for failure in partition_failures:
                affected_nodes.update(failure.affected_nodes)

            for node_id in affected_nodes:
                try:
                    container_name = self.docker_manager._get_container_name(node_id)
                    container = self.docker_manager.client.containers.get(container_name)

                    # Remove fake /etc/hosts entries (entries pointing to 127.0.0.255)
                    # Use a method that works on minimal containers
                    try:
                        # This approach: filter to temp file, then overwrite hosts using cat
                        exec_result = container.exec_run(
                            "sh -c 'grep -v 127.0.0.255 /etc/hosts > /tmp/hosts.fixed && cat /tmp/hosts.fixed > /etc/hosts && rm /tmp/hosts.fixed'",
                            user='root'
                        )
                        if exec_result.exit_code == 0:
                            logger.info(f"Restored /etc/hosts for {node_id}")
                        else:
                            logger.warning(f"Could not restore /etc/hosts for {node_id}: {exec_result.output.decode()}")
                    except Exception as e:
                        logger.warning(f"Could not restore /etc/hosts for {node_id}: {e}")

                except Exception as e:
                    logger.error(f"Failed to restore node {node_id}: {e}")

            # Detach all nodes from partition networks after clearing iptables
            for node_id in affected_nodes:
                try:
                    await self.docker_manager.detach_from_network(
                        node_id,
                        "nosqlsim_partition_a"
                    )
                    logger.info(f"Detached {node_id} from partition A")
                except Exception as e:
                    logger.debug(f"Could not detach {node_id} from partition A: {e}")

                try:
                    await self.docker_manager.detach_from_network(
                        node_id,
                        "nosqlsim_partition_b"
                    )
                    logger.info(f"Detached {node_id} from partition B")
                except Exception as e:
                    logger.debug(f"Could not detach {node_id} from partition B: {e}")

                # Re-attach to default network if needed (in case it was detached as fallback)
                try:
                    await self.docker_manager.attach_to_network(
                        node_id,
                        "nosqlsim_default"
                    )
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Could not re-attach {node_id} to default network: {e}")

            # Remove partition failures
            failures_to_remove = [
                fid for fid, failure in self.active_failures.items()
                if failure.failure_type == "network_partition"
            ]

            for fid in failures_to_remove:
                del self.active_failures[fid]

            # Clean up partition networks (only after detaching all nodes)
            try:
                network_a = self.docker_manager.client.networks.get("nosqlsim_partition_a")
                network_a.reload()
                if len(network_a.attrs.get('Containers', {})) == 0:
                    network_a.remove()
                    logger.info("Removed partition network A")
                else:
                    logger.warning("Partition network A still has containers, skipping removal")
            except Exception as e:
                logger.debug(f"Could not remove partition network A: {e}")

            try:
                network_b = self.docker_manager.client.networks.get("nosqlsim_partition_b")
                network_b.reload()
                if len(network_b.attrs.get('Containers', {})) == 0:
                    network_b.remove()
                    logger.info("Removed partition network B")
                else:
                    logger.warning("Partition network B still has containers, skipping removal")
            except Exception as e:
                logger.debug(f"Could not remove partition network B: {e}")

            logger.info("All network partitions healed")
            return True

        except Exception as e:
            logger.error(f"Failed to heal network partitions: {e}")
            return False

    async def inject_latency(
        self,
        node_id: str,
        latency_ms: int,
        jitter_ms: int = 0
    ) -> FailureState:
        """
        Inject network latency to a node (future implementation)

        Args:
            node_id: Node identifier
            latency_ms: Latency in milliseconds
            jitter_ms: Random jitter in milliseconds

        Returns:
            FailureState: State of the created failure
        """
        failure_id = f"latency-{node_id}-{uuid.uuid4().hex[:8]}"

        logger.info(f"Injecting {latency_ms}ms latency to node {node_id}")

        failure_state = FailureState(
            failure_id=failure_id,
            failure_type="latency_injection",
            affected_nodes=[node_id],
            started_at=datetime.utcnow(),
            config={"latency_ms": latency_ms, "jitter_ms": jitter_ms},
            description=f"Network latency injection: {latency_ms}ms on {node_id}"
        )

        self.active_failures[failure_id] = failure_state
        logger.warning("Latency injection is not fully implemented yet")

        return failure_state

    async def clear_failure(self, failure_id: str) -> bool:
        """
        Clear a specific failure

        Args:
            failure_id: Failure identifier

        Returns:
            bool: True if successful
        """
        if failure_id not in self.active_failures:
            logger.warning(f"Failure {failure_id} not found")
            return False

        failure = self.active_failures[failure_id]

        logger.info(f"Clearing failure {failure_id} ({failure.failure_type})")

        try:
            if failure.failure_type == "node_crash":
                # Restore crashed nodes
                for node_id in failure.affected_nodes:
                    await self.restore_node(node_id)

            elif failure.failure_type == "network_partition":
                await self.heal_network_partition()

            elif failure.failure_type == "latency_injection":
                pass

            del self.active_failures[failure_id]
            logger.info(f"Failure {failure_id} cleared")
            return True

        except Exception as e:
            logger.error(f"Failed to clear failure {failure_id}: {e}")
            return False

    def get_active_failures(self) -> Dict[str, FailureState]:
        """Get all active failures"""
        return self.active_failures.copy()

    async def clear_all_failures(self):
        """Clear all active failures"""
        logger.info("Clearing all failures")

        failure_ids = list(self.active_failures.keys())
        for failure_id in failure_ids:
            await self.clear_failure(failure_id)

        logger.info("All failures cleared")


# Global instance
failure_simulator = None

def get_failure_simulator(docker_manager: DockerManager) -> FailureSimulator:
    """Get or create failure simulator instance"""
    global failure_simulator
    if failure_simulator is None:
        failure_simulator = FailureSimulator(docker_manager)
    return failure_simulator
