from fastapi import WebSocket
from typing import Set, Dict
import logging
import json
import asyncio
from datetime import datetime

from app.models.cluster import ClusterState

logger = logging.getLogger(__name__)


class StateBroadcaster:
    """Manages WebSocket connections and broadcasts cluster state updates"""

    def __init__(self):
        """Initialize broadcaster"""
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        logger.info("StateBroadcaster initialized")

    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection

        Args:
            websocket: WebSocket connection to add
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection

        Args:
            websocket: WebSocket connection to remove
        """
        self.active_connections.discard(websocket)

        # Remove from all subscriptions
        for topic_connections in self.subscriptions.values():
            topic_connections.discard(websocket)

        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast_cluster_state(self, state: ClusterState):
        """
        Broadcast cluster state to all connected clients

        Args:
            state: ClusterState to broadcast
        """
        if not self.active_connections:
            return

        message = {
            "type": "cluster_state",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": state.model_dump(mode='json')
        }

        message_json = json.dumps(message)

        # Send to all connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def broadcast_metrics(self, metrics: Dict):
        """
        Broadcast metrics update to all connected clients

        Args:
            metrics: Metrics dictionary to broadcast
        """
        if not self.active_connections:
            return

        message = {
            "type": "metrics",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": metrics
        }

        message_json = json.dumps(message, default=str)

        # Send to all connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def broadcast_event(self, event_type: str, data: Dict):
        """
        Broadcast a general event to all connected clients

        Args:
            event_type: Type of event
            data: Event data
        """
        if not self.active_connections:
            return

        message = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data
        }

        message_json = json.dumps(message, default=str)

        # Send to all connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def broadcast_node_logs(self, node_id: str, logs: str):
        """
        Broadcast node logs to all connected clients

        Args:
            node_id: ID of the node
            logs: Log content to broadcast
        """
        if not self.active_connections:
            return

        message = {
            "type": "node_logs",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "node_id": node_id,
                "logs": logs
            }
        }

        message_json = json.dumps(message, default=str)

        # Send to all connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def subscribe(self, websocket: WebSocket, topic: str):
        """
        Subscribe a WebSocket to a specific topic

        Args:
            websocket: WebSocket connection
            topic: Topic to subscribe to
        """
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()

        self.subscriptions[topic].add(websocket)
        logger.info(f"WebSocket subscribed to topic: {topic}")

    async def broadcast_to_topic(self, topic: str, message: Dict):
        """
        Broadcast a message to all subscribers of a topic

        Args:
            topic: Topic to broadcast to
            message: Message to broadcast
        """
        if topic not in self.subscriptions:
            return

        message["timestamp"] = datetime.utcnow().isoformat()
        message_json = json.dumps(message, default=str)

        disconnected = set()
        for connection in self.subscriptions[topic]:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)


# Global broadcaster instance
broadcaster = StateBroadcaster()
