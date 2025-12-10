from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
import logging

from app.models.query import QueryRequest, QueryResult, QueryHistoryItem
from app.services.query_executor import get_query_executor
from app.services.docker_manager import docker_manager
from app.services.cluster_manager import cluster_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory query history (for this session)
query_history: List[QueryHistoryItem] = []
MAX_HISTORY_SIZE = 100


@router.post("/execute", response_model=QueryResult)
async def execute_query(request: QueryRequest):
    """
    Execute a MongoDB query with specified read/write concerns

    This endpoint allows you to run queries against the MongoDB cluster with
    full control over consistency guarantees.
    """
    logger.info(f"Executing query: {request.operation} on {request.database}.{request.collection}")

    try:
        # Get query executor
        query_exec = get_query_executor(docker_manager)

        # Determine replica set name
        replica_set_name = request.replica_set_name
        if not replica_set_name:
            # If not specified, use the first available replica set
            status = await cluster_manager.get_cluster_status()
            if not status or not status.replica_sets:
                raise HTTPException(
                    status_code=404,
                    detail="No replica sets found. Please initialize a cluster first."
                )
            replica_set_name = status.replica_sets[0].set_name

        # Execute the query
        result = await query_exec.execute_query(replica_set_name, request)

        # Add to history
        history_item = QueryHistoryItem(
            timestamp=datetime.utcnow(),
            request=request,
            result=result
        )
        query_history.append(history_item)

        # Limit history size
        if len(query_history) > MAX_HISTORY_SIZE:
            query_history.pop(0)

        logger.info(f"Query executed successfully: {result.message}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")


@router.get("/history", response_model=List[QueryHistoryItem])
async def get_query_history():
    """
    Get query execution history

    Returns the list of queries executed in this session, including
    their results and performance metrics.
    """
    logger.info(f"Retrieving query history ({len(query_history)} items)")
    return query_history


@router.delete("/history")
async def clear_query_history():
    """Clear query execution history"""
    global query_history
    count = len(query_history)
    query_history = []
    logger.info(f"Cleared {count} items from query history")
    return {"success": True, "message": f"Cleared {count} queries from history"}


@router.post("/test-data")
async def insert_test_data(replica_set_name: str = None):
    """
    Insert sample test data for educational purposes

    This creates a 'testdb.testcol' collection with sample documents
    that can be used to demonstrate read/write concerns.
    """
    logger.info("Inserting test data")

    try:
        # Determine replica set name
        if not replica_set_name:
            status = await cluster_manager.get_cluster_status()
            if not status or not status.replica_sets:
                raise HTTPException(
                    status_code=404,
                    detail="No replica sets found. Please initialize a cluster first."
                )
            replica_set_name = status.replica_sets[0].set_name

        # Create test documents
        test_documents = [
            {"name": "Alice", "age": 30, "city": "New York", "score": 85},
            {"name": "Bob", "age": 25, "city": "San Francisco", "score": 92},
            {"name": "Charlie", "age": 35, "city": "Chicago", "score": 78},
            {"name": "Diana", "age": 28, "city": "Boston", "score": 95},
            {"name": "Eve", "age": 32, "city": "Seattle", "score": 88},
        ]

        # Insert using QueryExecutor
        query_exec = get_query_executor(docker_manager)
        insert_request = QueryRequest(
            replica_set_name=replica_set_name,
            database="testdb",
            collection="testcol",
            operation="insertMany",
            documents=test_documents
        )

        result = await query_exec.execute_write_query(replica_set_name, insert_request)

        if result.success:
            logger.info(f"Inserted {len(test_documents)} test documents")
            return {
                "success": True,
                "message": f"Inserted {len(test_documents)} test documents",
                "documents": test_documents
            }
        else:
            raise HTTPException(status_code=500, detail=result.error or "Failed to insert test data")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inserting test data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to insert test data: {str(e)}")
