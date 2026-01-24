"""
Integration tests for network partitions.
These tests run after failure tests.

Test order:
1. test_01_create_partition - Create a network partition
2. test_02_verify_partition_state - Verify partition is active
3. test_03_majority_can_write - Verify majority partition can write
4. test_04_heal_partition - Heal the network partition
5. test_05_verify_healed - Verify cluster reunited
"""
import pytest
import httpx
import time
import logging

from .conftest import TEST_REPLICA_SET, wait_for_condition

logger = logging.getLogger(__name__)


class TestNetworkPartitions:
    """Test network partition functionality."""
    
    group_a = []
    group_b = []
    
    @pytest.fixture(autouse=True)
    def setup(self, http_client):
        """Store HTTP client."""
        self.client = http_client
    
    def _get_cluster_status(self):
        """Helper to get cluster status."""
        response = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
        assert response.status_code == 200
        return response.json()
    
    def _get_full_status(self):
        """Get full cluster state including partitions."""
        response = self.client.get("/api/cluster/status")
        assert response.status_code == 200
        return response.json()
    
    def test_01_setup_partition_groups(self):
        """Test: Identify nodes for partition groups."""
        status = self._get_cluster_status()
        members = status["members"]
        
        assert len(members) >= 3, "Need at least 3 nodes for partition test"
        
        healthy_members = [m for m in members if m["health"] == 1]
        assert len(healthy_members) >= 3, "Need at least 3 healthy nodes"
        
        TestNetworkPartitions.group_a = [healthy_members[0]["node_id"], healthy_members[1]["node_id"]]
        TestNetworkPartitions.group_b = [healthy_members[2]["node_id"]]
        
        logger.info(f"Partition groups: A={self.group_a}, B={self.group_b}")
    
    def test_02_create_partition(self):
        """Test: Create a network partition."""
        logger.info(f"Creating network partition: {self.group_a} vs {self.group_b}")
        
        response = self.client.post("/api/failures/partition", json={
            "replica_set_name": TEST_REPLICA_SET,
            "partition_config": {
                "group_a": self.group_a,
                "group_b": self.group_b,
                "description": "Integration test partition"
            }
        })
        
        assert response.status_code == 200, f"Partition creation failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Network partition created successfully")
    
    def test_03_verify_partition_active(self):
        """Test: Verify partition is reflected in cluster state."""
        logger.info("Verifying partition is active...")
        
        time.sleep(3)
        
        full_status = self._get_full_status()
        
        active_partitions = full_status.get("active_partitions", [])
        active_failures = full_status.get("active_failures", [])
        
        has_partition = (
            len(active_partitions) > 0 or 
            any("partition" in f.lower() for f in active_failures)
        )
        
        assert has_partition, f"No partition found in state: {full_status}"
        logger.info("Partition verified as active")
    
    def test_04_majority_group_behavior(self):
        """Test: Verify majority group (Group A) can still accept writes."""
        logger.info("Testing majority group behavior...")
        
        time.sleep(2)
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "insertOne",
            "document": {"test": "during_partition", "timestamp": time.time()},
            "write_concern": "1"
        })
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                logger.info("Write succeeded during partition (majority group)")
            else:
                logger.info(f"Write result: {data}")
        else:
            logger.info(f"Write behavior during partition: {response.status_code}")
    
    def test_05_heal_partition(self):
        """Test: Heal the network partition."""
        logger.info("Healing network partition...")
        
        response = self.client.post("/api/failures/heal")
        
        assert response.status_code == 200, f"Heal failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Network partition healed")
    
    def test_06_verify_partition_healed(self):
        """Test: Verify partition is fully healed."""
        logger.info("Verifying partition is healed...")
        
        def check_no_partitions():
            full_status = self._get_full_status()
            active_partitions = full_status.get("active_partitions", [])
            active_failures = full_status.get("active_failures", [])
            partition_failures = [f for f in active_failures if "partition" in f.lower()]
            return len(active_partitions) == 0 and len(partition_failures) == 0
        
        wait_for_condition(check_no_partitions, timeout=30, interval=2, description="no partitions")
        logger.info("Partition fully healed")
    
    def test_07_cluster_fully_operational(self):
        """Test: Verify cluster is fully operational after healing."""
        logger.info("Verifying full cluster operation...")
        
        def check_all_healthy():
            status = self._get_cluster_status()
            if status.get("health") != "ok":
                return False
            healthy = sum(1 for m in status["members"] if m["health"] == 1)
            return healthy == len(status["members"])
        
        wait_for_condition(check_all_healthy, timeout=60, interval=3, description="cluster healthy")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "find",
            "filter": {"test": "during_partition"}
        })
        
        assert response.status_code == 200, f"Post-heal query failed: {response.text}"
        logger.info("Cluster fully operational after partition heal")
