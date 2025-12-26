import logging
import asyncio
from typing import Dict, Set, Optional
from datetime import datetime
import hashlib

from app.services.docker_manager import DockerManager
from app.websocket.broadcaster import StateBroadcaster

logger = logging.getLogger(__name__)


class LogStreamer:
    """Manages real-time log streaming from Docker containers to WebSocket clients"""

    def __init__(self, docker_manager: DockerManager, broadcaster: StateBroadcaster):
        """
        Initialize log streamer

        Args:
            docker_manager: Docker manager instance for accessing container logs
            broadcaster: WebSocket broadcaster for sending logs to clients
        """
        self.docker_manager = docker_manager
        self.broadcaster = broadcaster

        # Track active streaming tasks per node
        self.streaming_tasks: Dict[str, asyncio.Task] = {}

        # Track subscribers per node
        self.subscribers: Dict[str, Set[str]] = {}  # node_id -> set of subscriber IDs

        # Track last log hash per node to avoid sending duplicates
        self.last_log_hashes: Dict[str, str] = {}

        # Configuration
        self.poll_interval = 2.0  # seconds
        self.tail_lines = 50  # number of lines to tail
        self.max_inactive_time = 300  # 5 minutes before auto-cleanup

        logger.info("LogStreamer initialized")

    def _generate_subscriber_id(self, websocket) -> str:
        """Generate unique subscriber ID from websocket"""
        return str(id(websocket))

    def _hash_logs(self, logs: str) -> str:
        """Generate hash of log content to detect changes"""
        return hashlib.md5(logs.encode()).hexdigest()

    async def subscribe(self, node_id: str, subscriber_id: str) -> bool:
        """
        Subscribe to log stream for a node

        Args:
            node_id: ID of the node to stream logs from
            subscriber_id: Unique ID of the subscriber

        Returns:
            bool: True if subscription successful
        """
        if node_id not in self.subscribers:
            self.subscribers[node_id] = set()

        self.subscribers[node_id].add(subscriber_id)
        logger.info(f"Subscriber {subscriber_id} subscribed to logs for {node_id}")

        # Start streaming task if not already running
        if node_id not in self.streaming_tasks or self.streaming_tasks[node_id].done():
            self.streaming_tasks[node_id] = asyncio.create_task(self._stream_logs(node_id))
            logger.info(f"Started log streaming task for {node_id}")

        return True

    async def unsubscribe(self, node_id: str, subscriber_id: str) -> bool:
        """
        Unsubscribe from log stream for a node

        Args:
            node_id: ID of the node
            subscriber_id: Unique ID of the subscriber

        Returns:
            bool: True if unsubscription successful
        """
        if node_id in self.subscribers and subscriber_id in self.subscribers[node_id]:
            self.subscribers[node_id].remove(subscriber_id)
            logger.info(f"Subscriber {subscriber_id} unsubscribed from logs for {node_id}")

            # Stop streaming if no more subscribers
            if len(self.subscribers[node_id]) == 0:
                await self._stop_streaming(node_id)

            return True

        return False

    async def _stop_streaming(self, node_id: str):
        """Stop streaming logs for a node"""
        if node_id in self.streaming_tasks and not self.streaming_tasks[node_id].done():
            self.streaming_tasks[node_id].cancel()
            try:
                await self.streaming_tasks[node_id]
            except asyncio.CancelledError:
                pass
            logger.info(f"Stopped log streaming task for {node_id}")

        # Cleanup
        if node_id in self.subscribers:
            del self.subscribers[node_id]
        if node_id in self.streaming_tasks:
            del self.streaming_tasks[node_id]
        if node_id in self.last_log_hashes:
            del self.last_log_hashes[node_id]

    async def _stream_logs(self, node_id: str):
        """
        Stream logs from a node continuously

        Args:
            node_id: ID of the node to stream logs from
        """
        logger.info(f"Starting continuous log streaming for {node_id}")

        try:
            while True:
                # Check if there are still subscribers
                if node_id not in self.subscribers or len(self.subscribers[node_id]) == 0:
                    logger.info(f"No subscribers for {node_id}, stopping stream")
                    break

                try:
                    # Fetch logs from Docker container
                    logs = await self.docker_manager.get_container_logs(node_id, tail=self.tail_lines)

                    # Check if logs have changed
                    current_hash = self._hash_logs(logs)
                    if node_id not in self.last_log_hashes or self.last_log_hashes[node_id] != current_hash:
                        # Logs have changed, broadcast them
                        await self.broadcaster.broadcast_node_logs(node_id, logs)
                        self.last_log_hashes[node_id] = current_hash
                        logger.debug(f"Broadcasted new logs for {node_id} ({len(logs)} bytes)")

                except Exception as e:
                    logger.error(f"Error fetching logs for {node_id}: {e}")
                    # Send error message to subscribers
                    error_msg = f"Error fetching logs: {str(e)}"
                    await self.broadcaster.broadcast_node_logs(node_id, error_msg)

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            logger.info(f"Log streaming task cancelled for {node_id}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in log streaming for {node_id}: {e}")
        finally:
            logger.info(f"Log streaming ended for {node_id}")

    async def cleanup_subscriber(self, subscriber_id: str):
        """
        Cleanup all subscriptions for a subscriber (e.g., when websocket disconnects)

        Args:
            subscriber_id: Unique ID of the subscriber
        """
        nodes_to_cleanup = []

        for node_id, subs in self.subscribers.items():
            if subscriber_id in subs:
                nodes_to_cleanup.append(node_id)

        for node_id in nodes_to_cleanup:
            await self.unsubscribe(node_id, subscriber_id)

        if nodes_to_cleanup:
            logger.info(f"Cleaned up {len(nodes_to_cleanup)} subscriptions for subscriber {subscriber_id}")

    async def shutdown(self):
        """Shutdown all streaming tasks"""
        logger.info("Shutting down LogStreamer")

        # Cancel all streaming tasks
        for node_id, task in list(self.streaming_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.streaming_tasks.clear()
        self.subscribers.clear()
        self.last_log_hashes.clear()

        logger.info("LogStreamer shutdown complete")

    def get_active_streams(self) -> Dict[str, int]:
        """
        Get information about active streams

        Returns:
            Dict mapping node_id to subscriber count
        """
        return {
            node_id: len(subs)
            for node_id, subs in self.subscribers.items()
        }


# Global instance (will be initialized in main.py)
log_streamer: Optional[LogStreamer] = None


def get_log_streamer(docker_manager: DockerManager, broadcaster: StateBroadcaster) -> LogStreamer:
    """Get or create log streamer instance"""
    global log_streamer
    if log_streamer is None:
        log_streamer = LogStreamer(docker_manager, broadcaster)
    return log_streamer
