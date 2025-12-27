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
        Create a network partition between two groups of nodes

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
            # Get or create partition networks
            try:
                network_a = self.docker_manager.client.networks.get('nosqlsim_partition_a')
                logger.info("Reusing existing partition network A")
            except:
                network_a = self.docker_manager.client.networks.create(
                    'nosqlsim_partition_a',
                    driver='bridge'
                )
                logger.info("Created new partition network A")

            try:
                network_b = self.docker_manager.client.networks.get('nosqlsim_partition_b')
                logger.info("Reusing existing partition network B")
            except:
                network_b = self.docker_manager.client.networks.create(
                    'nosqlsim_partition_b',
                    driver='bridge'
                )
                logger.info("Created new partition network B")

            # Add nodes to partition networks (keep them on default network for backend connectivity)
            # This allows backend health checks to work while nodes are isolated from each other
            for node_id in partition_config.group_a:
                # Detach from both partition networks first (clean slate)
                try:
                    await self.docker_manager.detach_from_network(node_id, 'nosqlsim_partition_a')
                except:
                    pass
                try:
                    await self.docker_manager.detach_from_network(node_id, 'nosqlsim_partition_b')
                except:
                    pass
                # Attach to partition A
                try:
                    await self.docker_manager.attach_to_network(node_id, 'nosqlsim_partition_a')
                    logger.info(f"Attached {node_id} to partition A")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.warning(f"{node_id} already in partition A")
                    else:
                        raise

            for node_id in partition_config.group_b:
                # Detach from both partition networks first (clean slate)
                try:
                    await self.docker_manager.detach_from_network(node_id, 'nosqlsim_partition_a')
                except:
                    pass
                try:
                    await self.docker_manager.detach_from_network(node_id, 'nosqlsim_partition_b')
                except:
                    pass
                # Attach to partition B
                try:
                    await self.docker_manager.attach_to_network(node_id, 'nosqlsim_partition_b')
                    logger.info(f"Attached {node_id} to partition B")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.warning(f"{node_id} already in partition B")
                    else:
                        raise

            # Use iptables to block traffic between the two partition networks
            # This simulates the partition while keeping backend connectivity
            for node_id in partition_config.group_a:
                container_name = self.docker_manager._get_container_name(node_id)
                container = self.docker_manager.client.containers.get(container_name)
                # Block traffic to nodes in group B
                for target_node_id in partition_config.group_b:
                    target_container_name = self.docker_manager._get_container_name(target_node_id)
                    target_container = self.docker_manager.client.containers.get(target_container_name)
                    try:
                        # Get IP of target node in default network
                        target_ip = target_container.attrs['NetworkSettings']['Networks']['nosqlsim_default']['IPAddress']
                        # Block traffic to this IP (both directions will be blocked when we process group B)
                        exec_result = container.exec_run(f"iptables -A OUTPUT -d {target_ip} -j DROP", privileged=True)
                        if exec_result.exit_code != 0:
                            logger.error(f"iptables command failed for {node_id}: {exec_result.output.decode()}")
                            raise Exception(f"iptables failed: {exec_result.output.decode()}")
                        logger.info(f"Blocked traffic from {node_id} to {target_node_id} ({target_ip})")
                    except Exception as e:
                        logger.error(f"Could not set iptables rule on {node_id}: {e}")
                        logger.warning("Falling back to network detachment - partition may not work correctly")
                        # Fallback: detach from default network if iptables fails
                        try:
                            await self.docker_manager.detach_from_network(node_id, "nosqlsim_default")
                        except Exception as detach_error:
                            logger.error(f"Fallback detachment also failed: {detach_error}")

            for node_id in partition_config.group_b:
                container_name = self.docker_manager._get_container_name(node_id)
                container = self.docker_manager.client.containers.get(container_name)
                # Block traffic to nodes in group A
                for target_node_id in partition_config.group_a:
                    target_container_name = self.docker_manager._get_container_name(target_node_id)
                    target_container = self.docker_manager.client.containers.get(target_container_name)
                    try:
                        target_ip = target_container.attrs['NetworkSettings']['Networks']['nosqlsim_default']['IPAddress']
                        exec_result = container.exec_run(f"iptables -A OUTPUT -d {target_ip} -j DROP", privileged=True)
                        if exec_result.exit_code != 0:
                            logger.error(f"iptables command failed for {node_id}: {exec_result.output.decode()}")
                            raise Exception(f"iptables failed: {exec_result.output.decode()}")
                        logger.info(f"Blocked traffic from {node_id} to {target_node_id} ({target_ip})")
                    except Exception as e:
                        logger.error(f"Could not set iptables rule on {node_id}: {e}")
                        logger.warning("Falling back to network detachment - partition may not work correctly")
                        # Fallback: detach from default network if iptables fails
                        try:
                            await self.docker_manager.detach_from_network(node_id, "nosqlsim_default")
                        except Exception as detach_error:
                            logger.error(f"Fallback detachment also failed: {detach_error}")

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
        Heal all network partitions by removing iptables rules and cleaning up networks

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

                    # Clear all iptables OUTPUT rules (this removes our partition blocks)
                    try:
                        container.exec_run("iptables -F OUTPUT", privileged=True)
                        logger.info(f"Cleared iptables rules for {node_id}")
                    except Exception as e:
                        logger.warning(f"Could not clear iptables for {node_id}: {e}")

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

        # TODO: Implement latency injection using tc (traffic control)
        # This requires running tc commands inside the container
        # For now, we'll just create a placeholder failure state

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
                # TODO: Remove latency injection
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
