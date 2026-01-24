"""
Integration tests for failure simulation.
These tests run after cluster and query tests.

Test order:
1. test_01_crash_secondary - Crash a secondary node
2. test_02_verify_degraded - Verify cluster detects the crash
3. test_03_restore_node - Restore the crashed node
4. test_04_crash_primary - Crash the primary node
5. test_05_verify_election - Verify new primary is elected
6. test_06_restore_primary - Restore the crashed primary
"""
import pytest
import httpx
import time
import logging

from .conftest import TEST_REPLICA_SET, wait_for_condition

logger = logging.getLogger(__name__)


class TestFailureSimulation:
    """Test node crash and restore functionality."""
    
    crashed_node_id = None
    original_primary = None
    
    @pytest.fixture(autouse=True)
    def setup(self, http_client):
        """Store HTTP client."""
        self.client = http_client
    
    def _get_cluster_status(self):
        """Helper to get cluster status."""
        response = self.client.get(f"/api/cluster/status/{TEST_REPLICA_SET}")
        assert response.status_code == 200
        return response.json()
    
    def _get_secondary(self):
        """Get a secondary node."""
        data = self._get_cluster_status()
        return next(
            (m for m in data["members"] if m["state_str"] == "SECONDARY" and m["health"] == 1),
            None
        )
    
    def _get_primary(self):
        """Get the primary node."""
        data = self._get_cluster_status()
        return next(
            (m for m in data["members"] if m["state_str"] == "PRIMARY"),
            None
        )
    
    def test_01_crash_secondary(self):
        """Test: Crash a secondary node."""
        secondary = self._get_secondary()
        assert secondary is not None, "No healthy secondary found"
        
        TestFailureSimulation.crashed_node_id = secondary["node_id"]
        logger.info(f"Crashing secondary node: {self.crashed_node_id}")
        
        response = self.client.post("/api/failures/crash", json={
            "node_id": self.crashed_node_id,
            "crash_type": "clean"
        })
        
        assert response.status_code == 200, f"Crash failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Secondary node crashed successfully")
    
    def test_02_verify_node_down(self):
        """Test: Verify the crashed node is detected as down."""
        logger.info("Waiting for node to be detected as down...")
        
        def check_node_down():
            data = self._get_cluster_status()
            node = next(
                (m for m in data["members"] if m["node_id"] == TestFailureSimulation.crashed_node_id),
                None
            )
            if not node:
                return False
            is_down = node["health"] != 1 or node["state_str"] in ["DOWN", "(not reachable/healthy)"]
            logger.debug(f"Node {TestFailureSimulation.crashed_node_id}: health={node['health']}, state={node['state_str']}")
            return is_down
        
        wait_for_condition(check_node_down, timeout=30, interval=2, description="node down")
        logger.info("Crashed node detected as down")
    
    def test_03_cluster_still_operational(self):
        """Test: Verify cluster is still operational with 2 nodes."""
        logger.info("Verifying cluster is still operational...")
        
        response = self.client.post("/api/queries/execute", json={
            "replica_set_name": TEST_REPLICA_SET,
            "database": "testdb",
            "collection": "testcol",
            "operation": "insertOne",
            "document": {"test": "during_failure", "timestamp": time.time()},
            "write_concern": "majority"
        })
        
        assert response.status_code == 200, f"Write during failure failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Write succeeded with majority during partial failure")
    
    def test_04_restore_secondary(self):
        """Test: Restore the crashed secondary node."""
        logger.info(f"Restoring node: {TestFailureSimulation.crashed_node_id}")
        
        response = self.client.post("/api/failures/restore", json={
            "node_id": TestFailureSimulation.crashed_node_id
        })
        
        assert response.status_code == 200, f"Restore failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        def check_node_healthy():
            status = self._get_cluster_status()
            node = next(
                (m for m in status["members"] if m["node_id"] == TestFailureSimulation.crashed_node_id),
                None
            )
            if not node:
                return False
            return node["health"] == 1 and node["state_str"] == "SECONDARY"
        
        wait_for_condition(check_node_healthy, timeout=60, interval=3, description="node restored")
        logger.info("Secondary node restored and healthy")
    
    def test_05_crash_primary(self):
        """Test: Crash the primary node to trigger election."""
        primary = self._get_primary()
        assert primary is not None, "No primary found"
        
        TestFailureSimulation.original_primary = primary["node_id"]
        logger.info(f"Crashing primary node: {self.original_primary}")
        
        response = self.client.post("/api/failures/crash", json={
            "node_id": self.original_primary,
            "crash_type": "clean"
        })
        
        assert response.status_code == 200, f"Crash failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        
        logger.info("Primary node crashed, election should be triggered")
    
    def test_06_verify_new_primary_elected(self):
        """Test: Verify a new primary is elected."""
        logger.info("Waiting for new primary election...")
        
        def check_new_primary():
            status = self._get_cluster_status()
            new_primary = status.get("primary")
            if not new_primary:
                return False
            return new_primary != TestFailureSimulation.original_primary
        
        wait_for_condition(check_new_primary, timeout=60, interval=3, description="new primary")
        
        status = self._get_cluster_status()
        logger.info(f"New primary elected: {status['primary']}")
    
    def test_07_restore_old_primary(self):
        """Test: Restore the old primary (should become secondary)."""
        logger.info(f"Restoring old primary: {TestFailureSimulation.original_primary}")
        
        response = self.client.post("/api/failures/restore", json={
            "node_id": TestFailureSimulation.original_primary
        })
        
        assert response.status_code == 200, f"Restore failed: {response.text}"
        
        def check_all_healthy():
            status = self._get_cluster_status()
            healthy = sum(1 for m in status["members"] if m["health"] == 1)
            return healthy == len(status["members"])
        
        wait_for_condition(check_all_healthy, timeout=60, interval=3, description="all nodes healthy")
        
        status = self._get_cluster_status()
        old_primary = next(
            (m for m in status["members"] if m["node_id"] == TestFailureSimulation.original_primary),
            None
        )
        assert old_primary is not None
        assert old_primary["state_str"] in ["PRIMARY", "SECONDARY"]
        
        logger.info(f"Old primary restored as: {old_primary['state_str']}")
