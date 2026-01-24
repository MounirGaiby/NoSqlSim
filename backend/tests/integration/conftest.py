"""
Pytest configuration for integration tests
"""
import pytest
import asyncio
import httpx
import docker
import time
import logging
from typing import Generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEST_BASE_URL = "http://localhost:8000"
TEST_REPLICA_SET = "test-rs"
TEST_PORT_START = 27100

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def docker_client():
    """Get Docker client."""
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture(scope="session")
def http_client() -> Generator[httpx.Client, None, None]:
    """HTTP client for API calls."""
    with httpx.Client(base_url=TEST_BASE_URL, timeout=60.0) as client:
        yield client


@pytest.fixture(scope="session")
def async_http_client():
    """Async HTTP client for API calls."""
    return httpx.AsyncClient(base_url=TEST_BASE_URL, timeout=60.0)


def cleanup_test_containers(docker_client: docker.DockerClient):
    """Remove all test containers and networks."""
    logger.info("Cleaning up test containers...")
    
    try:
        containers = docker_client.containers.list(all=True, filters={"name": "test-rs"})
        for container in containers:
            logger.info(f"Removing container: {container.name}")
            container.remove(force=True)
    except Exception as e:
        logger.warning(f"Error removing containers: {e}")
    
    try:
        containers = docker_client.containers.list(all=True, filters={"name": "nosqlsim"})
        for container in containers:
            if "test" in container.name.lower():
                logger.info(f"Removing container: {container.name}")
                container.remove(force=True)
    except Exception as e:
        logger.warning(f"Error removing containers: {e}")
    
    try:
        networks = docker_client.networks.list(filters={"name": "nosqlsim"})
        for network in networks:
            logger.info(f"Removing network: {network.name}")
            try:
                network.remove()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error removing networks: {e}")


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown(docker_client):
    """Setup before all tests and cleanup after all tests."""
    cleanup_test_containers(docker_client)
    
    yield
    
    logger.info("Test session complete. Cleaning up...")
    cleanup_test_containers(docker_client)


def wait_for_condition(condition_fn, timeout=60, interval=2, description="condition"):
    """Wait for a condition to be true."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if condition_fn():
                return True
        except Exception as e:
            logger.debug(f"Waiting for {description}: {e}")
        time.sleep(interval)
    raise TimeoutError(f"Timeout waiting for {description} after {timeout}s")
