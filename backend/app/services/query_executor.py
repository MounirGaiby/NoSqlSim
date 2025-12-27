import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import time
from pymongo import MongoClient, ReadPreference
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError
from bson import ObjectId

from app.services.docker_manager import DockerManager
from app.models.query import (
    QueryRequest,
    QueryResult,
    QueryMetrics,
    ReadConcernLevel,
    WriteConcernLevel,
    ReadPreferenceMode
)

logger = logging.getLogger(__name__)

# Reference to cluster_manager - will be set when needed
_cluster_manager = None

def _serialize_mongo_doc(doc: Any) -> Any:
    """
    Recursively convert MongoDB document to JSON-serializable format.
    Handles ObjectId, datetime, and nested structures.
    """
    if doc is None:
        return None
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    if isinstance(doc, dict):
        return {key: _serialize_mongo_doc(value) for key, value in doc.items()}
    if isinstance(doc, list):
        return [_serialize_mongo_doc(item) for item in doc]
    if isinstance(doc, bytes):
        return doc.decode('utf-8', errors='replace')
    return doc


def _serialize_results(results: List[Dict]) -> List[Dict]:
    """Convert a list of MongoDB documents to JSON-serializable format"""
    return [_serialize_mongo_doc(doc) for doc in results]


def get_cluster_manager():
    """Get cluster manager reference - lazy import to avoid circular imports"""
    global _cluster_manager
    if _cluster_manager is None:
        from app.services.cluster_manager import cluster_manager
        _cluster_manager = cluster_manager
    return _cluster_manager


class QueryExecutor:
    """Executes MongoDB queries with configurable read/write concerns and collects metrics"""

    def __init__(self, docker_manager: DockerManager):
        """Initialize query executor"""
        self.docker_manager = docker_manager
        logger.info("QueryExecutor initialized")

    def _get_read_preference(self, mode: ReadPreferenceMode) -> ReadPreference:
        """Convert read preference mode to PyMongo ReadPreference"""
        preferences = {
            ReadPreferenceMode.PRIMARY: ReadPreference.PRIMARY,
            ReadPreferenceMode.PRIMARY_PREFERRED: ReadPreference.PRIMARY_PREFERRED,
            ReadPreferenceMode.SECONDARY: ReadPreference.SECONDARY,
            ReadPreferenceMode.SECONDARY_PREFERRED: ReadPreference.SECONDARY_PREFERRED,
            ReadPreferenceMode.NEAREST: ReadPreference.NEAREST
        }
        return preferences.get(mode, ReadPreference.PRIMARY)

    def _get_read_concern(self, level: ReadConcernLevel) -> ReadConcern:
        """Convert read concern level to PyMongo ReadConcern"""
        concerns = {
            ReadConcernLevel.LOCAL: ReadConcern(level="local"),
            ReadConcernLevel.AVAILABLE: ReadConcern(level="available"),
            ReadConcernLevel.MAJORITY: ReadConcern(level="majority"),
            ReadConcernLevel.LINEARIZABLE: ReadConcern(level="linearizable"),
            ReadConcernLevel.SNAPSHOT: ReadConcern(level="snapshot")
        }
        return concerns.get(level, ReadConcern(level="local"))

    def _get_write_concern(self, level: WriteConcernLevel, w_value: Optional[int] = None) -> WriteConcern:
        """Convert write concern level to PyMongo WriteConcern"""
        if level == WriteConcernLevel.W0:
            return WriteConcern(w=0)
        elif level == WriteConcernLevel.W1:
            return WriteConcern(w=1)
        elif level == WriteConcernLevel.W2:
            return WriteConcern(w=2)
        elif level == WriteConcernLevel.W3:
            return WriteConcern(w=3)
        elif level == WriteConcernLevel.MAJORITY:
            return WriteConcern(w="majority")
        elif level == WriteConcernLevel.CUSTOM and w_value is not None:
            return WriteConcern(w=w_value)
        else:
            return WriteConcern(w=1)

    async def _find_working_node(self, nodes: list) -> tuple:
        """
        Find a working node to connect to
        
        Args:
            nodes: List of NodeConfig objects
            
        Returns:
            tuple: (connection_string, node_config) or raises exception
        """
        for node in nodes:
            try:
                conn_str = f"mongodb://{node.host}:{node.port}/?directConnection=true&serverSelectionTimeoutMS=2000"
                client = MongoClient(conn_str, serverSelectionTimeoutMS=2000)
                # Test connection
                client.admin.command('ping')
                client.close()
                logger.info(f"Found working node: {node.node_id} at {node.host}:{node.port}")
                return (f"mongodb://{node.host}:{node.port}/?directConnection=true", node)
            except Exception as e:
                logger.debug(f"Node {node.node_id} not available: {e}")
                continue
        raise ValueError("No available nodes found in replica set")

    async def _find_primary_node(self, nodes: list, replica_set_name: str) -> tuple:
        """
        Find the primary node in a replica set

        Args:
            nodes: List of NodeConfig objects
            replica_set_name: Name of the replica set

        Returns:
            tuple: (connection_string, node_config) for primary node
        """
        cluster_mgr = get_cluster_manager()

        # Try to get primary from cluster status
        try:
            status = await cluster_mgr.get_replica_set_status(replica_set_name)
            if status.primary:
                # Find the node config for the primary
                for node in nodes:
                    if node.node_id == status.primary:
                        conn_str = f"mongodb://{node.host}:{node.port}/?directConnection=true"
                        logger.info(f"Found primary node: {node.node_id} at {node.host}:{node.port}")
                        return (conn_str, node)
        except Exception as e:
            logger.warning(f"Could not get primary from status: {e}")

        # Fallback: try each node and check if it's primary
        for node in nodes:
            try:
                conn_str = f"mongodb://{node.host}:{node.port}/?directConnection=true&serverSelectionTimeoutMS=2000"
                client = MongoClient(conn_str, serverSelectionTimeoutMS=2000)
                # Check if this node is primary
                is_master = client.admin.command('isMaster')
                client.close()
                if is_master.get('ismaster', False):
                    logger.info(f"Found primary node: {node.node_id} at {node.host}:{node.port}")
                    return (f"mongodb://{node.host}:{node.port}/?directConnection=true", node)
            except Exception as e:
                logger.debug(f"Node {node.node_id} check failed: {e}")
                continue

        raise ValueError("No primary node found in replica set")

    async def _find_specific_node(self, nodes: list, target_node_id: str) -> tuple:
        """
        Find a specific node by ID

        Args:
            nodes: List of NodeConfig objects
            target_node_id: Node ID to find

        Returns:
            tuple: (connection_string, node_config) for the target node
        """
        for node in nodes:
            if node.node_id == target_node_id:
                conn_str = f"mongodb://{node.host}:{node.port}/?directConnection=true"
                logger.info(f"Targeting specific node: {node.node_id} at {node.host}:{node.port}")
                return (conn_str, node)

        raise ValueError(f"Node '{target_node_id}' not found in replica set")

    async def execute_read_query(
        self,
        replica_set_name: str,
        query_request: QueryRequest
    ) -> QueryResult:
        """
        Execute a read query with specified read concern and preference

        Args:
            replica_set_name: Name of the replica set
            query_request: Query request with read settings

        Returns:
            QueryResult: Query execution results and metrics
        """
        start_time = time.time()
        logger.info(f"Executing read query on {replica_set_name}")
        logger.info(f"Read concern: {query_request.read_concern}, Preference: {query_request.read_preference}")

        try:
            # Get nodes for replica set from cluster manager
            cluster_mgr = get_cluster_manager()
            if replica_set_name not in cluster_mgr.replica_sets:
                raise ValueError(f"Replica set '{replica_set_name}' not found")
            
            nodes = cluster_mgr.replica_sets[replica_set_name]

            # Find target node: specific node if provided, otherwise based on read preference
            if query_request.target_node_id:
                connection_string, target_node = await self._find_specific_node(nodes, query_request.target_node_id)
            elif query_request.read_preference == ReadPreferenceMode.PRIMARY:
                connection_string, target_node = await self._find_primary_node(nodes, replica_set_name)
            else:
                connection_string, target_node = await self._find_working_node(nodes)

            logger.info(f"Connecting to {target_node.node_id} with connection string: {connection_string}")

            # Create MongoDB client with read settings
            read_concern = self._get_read_concern(query_request.read_concern)

            client = MongoClient(
                connection_string,
                readConcernLevel=read_concern.level,
                serverSelectionTimeoutMS=5000
            )

            # Execute query
            db = client[query_request.database]
            collection = db[query_request.collection]

            # Perform the query operation
            if query_request.operation == "find":
                cursor = collection.find(query_request.filter or {})
                if query_request.limit:
                    cursor = cursor.limit(query_request.limit)
                results = list(cursor)
            elif query_request.operation == "findOne":
                results = [collection.find_one(query_request.filter or {})]
            elif query_request.operation == "count":
                count = collection.count_documents(query_request.filter or {})
                results = [{"count": count}]
            elif query_request.operation == "aggregate":
                results = list(collection.aggregate(query_request.pipeline or []))
            else:
                raise ValueError(f"Unsupported operation: {query_request.operation}")

            # Calculate metrics
            execution_time_ms = (time.time() - start_time) * 1000

            # Get server info to determine which node served the query
            server_info = client.server_info()
            nodes_accessed = [str(client.address)]

            # Close client
            client.close()

            # Prepare result
            metrics = QueryMetrics(
                execution_time_ms=execution_time_ms,
                nodes_accessed=nodes_accessed,
                documents_returned=len(results),
                read_concern_used=query_request.read_concern.value,
                read_preference_used=query_request.read_preference.value,
                timestamp=datetime.utcnow()
            )

            logger.info(f"Read query completed in {execution_time_ms:.2f}ms, returned {len(results)} documents")

            # Serialize results to handle ObjectId and other BSON types
            serialized_results = _serialize_results(results)

            return QueryResult(
                success=True,
                data=serialized_results,
                metrics=metrics,
                message=f"Query executed successfully on {replica_set_name}"
            )

        except PyMongoError as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"MongoDB error executing read query: {e}")

            return QueryResult(
                success=False,
                data=[],
                metrics=QueryMetrics(
                    execution_time_ms=execution_time_ms,
                    nodes_accessed=[],
                    documents_returned=0,
                    read_concern_used=query_request.read_concern.value,
                    read_preference_used=query_request.read_preference.value,
                    timestamp=datetime.utcnow()
                ),
                message=f"Query failed: {str(e)}",
                error=str(e)
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Error executing read query: {e}")

            return QueryResult(
                success=False,
                data=[],
                metrics=QueryMetrics(
                    execution_time_ms=execution_time_ms,
                    nodes_accessed=[],
                    documents_returned=0,
                    read_concern_used=query_request.read_concern.value,
                    read_preference_used=query_request.read_preference.value,
                    timestamp=datetime.utcnow()
                ),
                message=f"Query execution error: {str(e)}",
                error=str(e)
            )

    async def execute_write_query(
        self,
        replica_set_name: str,
        query_request: QueryRequest
    ) -> QueryResult:
        """
        Execute a write query with specified write concern

        Args:
            replica_set_name: Name of the replica set
            query_request: Query request with write settings

        Returns:
            QueryResult: Query execution results and metrics
        """
        start_time = time.time()
        logger.info(f"Executing write query on {replica_set_name}")
        logger.info(f"Write concern: {query_request.write_concern}")

        try:
            # Get nodes for replica set from cluster manager
            cluster_mgr = get_cluster_manager()
            if replica_set_name not in cluster_mgr.replica_sets:
                raise ValueError(f"Replica set '{replica_set_name}' not found")
            
            nodes = cluster_mgr.replica_sets[replica_set_name]

            # Find target node: specific node if provided (for testing), otherwise primary
            if query_request.target_node_id:
                connection_string, target_node = await self._find_specific_node(nodes, query_request.target_node_id)
                logger.info(f"Targeting specific node for write (testing): {target_node.node_id}")
            else:
                # Writes normally go to primary
                connection_string, target_node = await self._find_primary_node(nodes, replica_set_name)

            logger.info(f"Connecting to {target_node.node_id} for write: {connection_string}")

            # Create MongoDB client with write settings
            write_concern = self._get_write_concern(
                query_request.write_concern,
                query_request.write_concern_w
            )

            client = MongoClient(
                connection_string,
                w=write_concern.document.get("w"),
                serverSelectionTimeoutMS=5000
            )

            # Execute query
            db = client[query_request.database]
            collection = db[query_request.collection]

            # Perform the write operation
            result_data = []
            documents_affected = 0

            if query_request.operation == "insertOne":
                result = collection.insert_one(query_request.document)
                result_data = [{"insertedId": str(result.inserted_id)}]
                documents_affected = 1

            elif query_request.operation == "insertMany":
                result = collection.insert_many(query_request.documents)
                result_data = [{"insertedIds": [str(id) for id in result.inserted_ids]}]
                documents_affected = len(result.inserted_ids)

            elif query_request.operation == "updateOne":
                result = collection.update_one(
                    query_request.filter or {},
                    query_request.update
                )
                result_data = [{
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count
                }]
                documents_affected = result.modified_count

            elif query_request.operation == "updateMany":
                result = collection.update_many(
                    query_request.filter or {},
                    query_request.update
                )
                result_data = [{
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count
                }]
                documents_affected = result.modified_count

            elif query_request.operation == "deleteOne":
                result = collection.delete_one(query_request.filter or {})
                result_data = [{"deletedCount": result.deleted_count}]
                documents_affected = result.deleted_count

            elif query_request.operation == "deleteMany":
                result = collection.delete_many(query_request.filter or {})
                result_data = [{"deletedCount": result.deleted_count}]
                documents_affected = result.deleted_count

            else:
                raise ValueError(f"Unsupported operation: {query_request.operation}")

            # Calculate metrics
            execution_time_ms = (time.time() - start_time) * 1000

            # Get server info
            nodes_accessed = [str(client.address)]

            # Close client
            client.close()

            # Prepare result
            metrics = QueryMetrics(
                execution_time_ms=execution_time_ms,
                nodes_accessed=nodes_accessed,
                documents_returned=documents_affected,
                write_concern_used=query_request.write_concern.value,
                timestamp=datetime.utcnow()
            )

            logger.info(f"Write query completed in {execution_time_ms:.2f}ms, affected {documents_affected} documents")

            # Serialize results to handle ObjectId and other BSON types
            serialized_result_data = _serialize_results(result_data)

            return QueryResult(
                success=True,
                data=serialized_result_data,
                metrics=metrics,
                message=f"Write operation executed successfully on {replica_set_name}"
            )

        except PyMongoError as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"MongoDB error executing write query: {e}")

            return QueryResult(
                success=False,
                data=[],
                metrics=QueryMetrics(
                    execution_time_ms=execution_time_ms,
                    nodes_accessed=[],
                    documents_returned=0,
                    write_concern_used=query_request.write_concern.value,
                    timestamp=datetime.utcnow()
                ),
                message=f"Write operation failed: {str(e)}",
                error=str(e)
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Error executing write query: {e}")

            return QueryResult(
                success=False,
                data=[],
                metrics=QueryMetrics(
                    execution_time_ms=execution_time_ms,
                    nodes_accessed=[],
                    documents_returned=0,
                    write_concern_used=query_request.write_concern.value,
                    timestamp=datetime.utcnow()
                ),
                message=f"Write execution error: {str(e)}",
                error=str(e)
            )

    async def execute_query(
        self,
        replica_set_name: str,
        query_request: QueryRequest
    ) -> QueryResult:
        """
        Execute a query (read or write) based on operation type

        Args:
            replica_set_name: Name of the replica set
            query_request: Query request

        Returns:
            QueryResult: Query execution results and metrics
        """
        # Determine if operation is read or write
        read_operations = ["find", "findOne", "count", "aggregate"]
        write_operations = ["insertOne", "insertMany", "updateOne", "updateMany", "deleteOne", "deleteMany"]

        if query_request.operation in read_operations:
            return await self.execute_read_query(replica_set_name, query_request)
        elif query_request.operation in write_operations:
            return await self.execute_write_query(replica_set_name, query_request)
        else:
            return QueryResult(
                success=False,
                data=[],
                metrics=QueryMetrics(
                    execution_time_ms=0,
                    nodes_accessed=[],
                    documents_returned=0,
                    timestamp=datetime.utcnow()
                ),
                message=f"Unknown operation: {query_request.operation}",
                error=f"Operation '{query_request.operation}' is not supported"
            )


# Global instance
query_executor = None

def get_query_executor(docker_manager: DockerManager) -> QueryExecutor:
    """Get or create query executor instance"""
    global query_executor
    if query_executor is None:
        query_executor = QueryExecutor(docker_manager)
    return query_executor
