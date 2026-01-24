"""
Integration tests for cluster initialization and management.
These tests run in sequence and depend on each other.

Test order:
1. test_01_cluster_init - Initialize a 3-node replica set
2. test_02_cluster_status - Verify cluster state
3. test_03_primary_election - Check primary exists
4. test_04_add_node - Add a new secondary node
5. test_05_remove_node - Remove a node
"""
import pytest
import httpx
import time
import logging

from .conftest import (
    TEST_REPLICA_SET, 
    TEST_PORT_START, 
    TEST_BASE_URL,
    wait_for_condition
)

logger = logging.getLogger(__name__)


class TestClusterOperations:
    """Test cluster initialization and node management."""
    
    @pytest.fixture(autouse=True)
    def setup(self, http_client):
        """Store HTTP client."""
        self.client = http_client
    
    def test_01_cluster_init(self):
        """Test: Initialize a 3-node replica set."""
        logger.info(f"Initializing replica set '{TEST_REPLICA_SET}' with 3 nodes...")
        
        response = self.client.post("/api/cluster/init", json={
            "replica_set_name": TEST_REPLICA_SET,
            "node_count": 3,
            "starting_port": TEST_PORT_START
        })
        
        assert response.status_code == 200, f"Init failed: {response.text}"
        data = response.json()
        
        assert data["success"] is True
        assert data["replica_set_name"] == TEST_REPLICA_SET
        assert "status" in data
        
        logger.info(f"Replica set initialized: {data['message']}")
    
    def test_02_wait_for_cluster_ready(self):
        """Test: Wait for cluster to be healthy."""
        logger.info("Waiting for cluster to become healthy...")
        
        def check_healthy():
            response = self.client.get("/api/cluster/status")
            if response.status_code != 200:
                return False
            data = response.json()
            rs = data.get("replica_sets", {}).get(TEST_REPLICA_SET)
            if not rs:
                return False
            health = rs.get("health", "")
            has_primary = rs.get("primary") is not None
            logger.debug(f"Cluster health: {health}, has_primary: {has_primary}")
            return health == "ok" and has_primary
        
        wait_for_condition(check_healthy, timeout=90, interval=3, description="cluster healthy")
        logger.info("Cluster is healthy with primary elected!")
    
    def test_03_verify_cluster_members(self):
        """Test: Verify all 3 members are present and healthy."""
        response = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
        
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        assert len(data["members"]) == 3, f"Expected 3 members, got {len(data['members'])}"
        assert data["primary"] is not None, "No primary elected"
        
        primary_count = sum(1 for m in data["members"] if m["state_str"] == "PRIMARY")
        secondary_count = sum(1 for m in data["members"] if m["state_str"] == "SECONDARY")
        
        assert primary_count == 1, f"Expected 1 primary, got {primary_count}"
        assert secondary_count == 2, f"Expected 2 secondaries, got {secondary_count}"
        
        logger.info(f"Cluster verified: 1 primary, 2 secondaries")
    
    def test_04_add_node(self):
        """Test: Add a 4th node to the cluster."""
        logger.info("Adding a new secondary node...")
        
        response = self.client.post("/api/cluster/nodes", json={
            "replica_set_name": TEST_REPLICA_SET,
            "role": "replica",
            "priority": 1
        })
        
        assert response.status_code == 200, f"Add node failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        def check_4_nodes():
            resp = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
            if resp.status_code != 200:
                return False
            return len(resp.json().get("members", [])) == 4
        
        wait_for_condition(check_4_nodes, timeout=60, interval=3, description="4 nodes")
        logger.info("Node added successfully, cluster now has 4 nodes")
    
    def test_05_verify_4_nodes(self):
        """Test: Verify cluster has 4 members."""
        response = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["members"]) == 4
        
        healthy_count = sum(1 for m in data["members"] if m["health"] == 1)
        assert healthy_count == 4, f"Expected 4 healthy nodes, got {healthy_count}"
        
        logger.info("All 4 nodes verified as healthy")
    
    def test_06_remove_node(self):
        """Test: Remove a secondary node."""
        response = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
        assert response.status_code == 200
        data = response.json()
        
        secondary = next(
            (m for m in data["members"] if m["state_str"] == "SECONDARY"),
            None
        )
        assert secondary is not None, "No secondary found to remove"
        
        node_id = secondary["node_id"]
        logger.info(f"Removing secondary node: {node_id}")
        
        response = self.client.delete(
            f"/api/cluster/nodes/{node_id}",
            params={"replica_set_name": TEST_REPLICA_SET}
        )
        
        assert response.status_code == 200, f"Remove failed: {response.text}"
        
        def check_3_nodes():
            resp = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
            if resp.status_code != 200:
                return False
            return len(resp.json().get("members", [])) == 3
        
        wait_for_condition(check_3_nodes, timeout=30, interval=2, description="3 nodes")
        logger.info("Node removed, cluster back to 3 nodes")
