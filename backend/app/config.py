from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application configuration"""

    # Application
    app_name: str = "NoSqlSim"
    app_version: str = "1.0.0"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

    # MongoDB
    mongodb_version: str = "7.0"
    mongodb_start_port: int = 27017
    mongodb_max_nodes: int = 20

    # Docker
    docker_network_prefix: str = "nosqlsim"
    docker_container_prefix: str = "nosqlsim"
    docker_memory_limit: str = "512m"

    # Cluster defaults
    default_replica_set_name: str = "rs0"
    default_election_timeout_ms: int = 10000
    default_heartbeat_interval_ms: int = 2000

    # Monitoring
    cluster_poll_interval_seconds: int = 1
    metrics_retention_seconds: int = 300

    # WebSocket
    ws_heartbeat_interval: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
