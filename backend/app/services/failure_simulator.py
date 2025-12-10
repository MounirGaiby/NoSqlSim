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
            # Create partition networks
            network_a = self.docker_manager.client.networks.create(
                'nosqlsim_partition_a',
                driver='bridge'
            )
            network_b = self.docker_manager.client.networks.create(
                'nosqlsim_partition_b',
                driver='bridge'
            )

            # Move nodes to partition networks
            for node_id in partition_config.group_a:
                await self.docker_manager.detach_from_network(
                    node_id,
                    "nosqlsim_default"
                )
                await self.docker_manager.attach_to_network(node_id, 'nosqlsim_partition_a')

            for node_id in partition_config.group_b:
                await self.docker_manager.detach_from_network(
                    node_id,
                    "nosqlsim_default"
                )
                await self.docker_manager.attach_to_network(node_id, 'nosqlsim_partition_b')

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
        Heal all network partitions by restoring nodes to default network

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

            # Restore all affected nodes to default network
            affected_nodes = set()
            for failure in partition_failures:
                affected_nodes.update(failure.affected_nodes)

            for node_id in affected_nodes:
                try:
                    # Try to detach from partition networks
                    try:
                        await self.docker_manager.detach_from_network(
                            node_id,
                            "nosqlsim_partition_a"
                        )
                    except:
                        pass

                    try:
                        await self.docker_manager.detach_from_network(
                            node_id,
                            "nosqlsim_partition_b"
                        )
                    except:
                        pass

                    # Attach to default network
                    await self.docker_manager.attach_to_network(
                        node_id,
                        "nosqlsim_default"
                    )

                except Exception as e:
                    logger.error(f"Failed to restore node {node_id}: {e}")

            # Remove partition failures
            failures_to_remove = [
                fid for fid, failure in self.active_failures.items()
                if failure.failure_type == "network_partition"
            ]

            for fid in failures_to_remove:
                del self.active_failures[fid]

            # Clean up partition networks
            try:
                self.docker_manager.client.networks.get(
                    "nosqlsim_partition_a"
                ).remove()
            except:
                pass

            try:
                self.docker_manager.client.networks.get(
                    "nosqlsim_partition_b"
                ).remove()
            except:
                pass

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
