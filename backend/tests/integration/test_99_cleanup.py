"""
Final cleanup test - runs last to clean up all test resources.
"""
import pytest
import logging
import docker

from .conftest import TEST_REPLICA_SET, cleanup_test_containers

logger = logging.getLogger(__name__)


class TestCleanup:
    """Final cleanup after all tests."""
    
    @pytest.fixture(autouse=True)
    def setup(self, http_client, docker_client):
        """Store clients."""
        self.client = http_client
        self.docker_client = docker_client
    
    def test_01_cleanup_containers(self):
        """Test: Clean up all test containers."""
        logger.info("Cleaning up test containers...")
        
        cleanup_test_containers(self.docker_client)
        
        remaining = self.docker_client.containers.list(
            all=True, 
            filters={"name": "test-rs"}
        )
        
        assert len(remaining) == 0, f"Some containers remain: {[c.name for c in remaining]}"
        logger.info("All test containers cleaned up successfully")
    
    def test_02_cleanup_networks(self):
        """Test: Clean up test networks."""
        logger.info("Cleaning up test networks...")
        
        networks = self.docker_client.networks.list(filters={"name": "nosqlsim"})
        for network in networks:
            try:
                network.remove()
                logger.info(f"Removed network: {network.name}")
            except Exception as e:
                logger.warning(f"Could not remove network {network.name}: {e}")
        
        logger.info("Network cleanup complete")
