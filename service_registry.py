"""SQLite-backed registry for provisioned infrastructure services."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from requirement_parser import Environment, InfrastructureSpec


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    NOT_READY = "not-ready"
    FAILED = "failed"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class DuplicateServiceError(Exception):
    pass


class ServiceNotFoundError(Exception):
    pass


class ServiceRegistry:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        configured_path = db_path or os.getenv("INFRASTRUCTURE_REGISTRY_DB")
        self.db_path = str(
            configured_path
            or Path(__file__).resolve().with_name("infrastructure_registry.sqlite3")
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS registered_services (
                    service_name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    replica_count INTEGER NOT NULL,
                    deployment_status TEXT NOT NULL,
                    resource_references TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (service_name, environment)
                )
                """
            )

    @staticmethod
    def _normalize(
        service_name: str,
        environment: Union[str, Environment],
        replica_count: int,
        deployment_status: Union[str, DeploymentStatus],
        resource_references: List[str],
    ) -> tuple:
        spec = InfrastructureSpec(
            service_name=service_name,
            environment=environment,
            replica_count=replica_count,
        )
        normalized_name = spec.service_name
        if len(normalized_name) > 63:
            raise ValueError("Service name must be at most 63 characters.")
        if not 1 <= replica_count <= 20:
            raise ValueError("Replica count must be between 1 and 20.")
        normalized_status = DeploymentStatus(deployment_status).value
        if not isinstance(resource_references, list) or not all(
            isinstance(reference, str) for reference in resource_references
        ):
            raise ValueError("Resource references must be a list of strings.")
        return (
            normalized_name,
            spec.environment.value,
            normalized_status,
            json.dumps(resource_references),
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> Dict[str, Any]:
        record = dict(row)
        record["resource_references"] = json.loads(record["resource_references"])
        return record

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_service(
        self,
        service_name: str,
        owner: str,
        environment: Union[str, Environment],
        replica_count: int,
        deployment_status: Union[str, DeploymentStatus] = DeploymentStatus.PENDING,
        resource_references: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        name, env, status, references = self._normalize(
            service_name,
            environment,
            replica_count,
            deployment_status,
            resource_references or [],
        )
        if len(owner) > 128:
            raise ValueError("Owner must be at most 128 characters.")
        now = self._now()
        self.initialize()
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO registered_services (
                        service_name, owner, environment, replica_count,
                        deployment_status, resource_references, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, owner, env, replica_count, status, references, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM registered_services WHERE service_name = ? AND environment = ?",
                    (name, env),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateServiceError(
                f"Service '{name}' already exists in '{env}'."
            ) from exc
        return self._record(row)

    def upsert_service(
        self,
        service_name: str,
        owner: str,
        environment: Union[str, Environment],
        replica_count: int,
        deployment_status: Union[str, DeploymentStatus],
        resource_references: List[str],
    ) -> Dict[str, Any]:
        name, env, status, references = self._normalize(
            service_name,
            environment,
            replica_count,
            deployment_status,
            resource_references,
        )
        if len(owner) > 128:
            raise ValueError("Owner must be at most 128 characters.")
        now = self._now()
        self.initialize()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO registered_services (
                    service_name, owner, environment, replica_count,
                    deployment_status, resource_references, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(service_name, environment) DO UPDATE SET
                    owner = excluded.owner,
                    replica_count = excluded.replica_count,
                    deployment_status = excluded.deployment_status,
                    resource_references = excluded.resource_references,
                    updated_at = excluded.updated_at
                """,
                (name, owner, env, replica_count, status, references, now, now),
            )
            row = connection.execute(
                "SELECT * FROM registered_services WHERE service_name = ? AND environment = ?",
                (name, env),
            ).fetchone()
        return self._record(row)

    def get_service(
        self,
        service_name: str,
        environment: Union[str, Environment],
    ) -> Optional[Dict[str, Any]]:
        spec = InfrastructureSpec(service_name=service_name, environment=environment)
        self.initialize()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM registered_services WHERE service_name = ? AND environment = ?",
                (spec.service_name, spec.environment.value),
            ).fetchone()
        return self._record(row) if row else None

    def list_services(self) -> List[Dict[str, Any]]:
        self.initialize()
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM registered_services
                ORDER BY created_at DESC, service_name, environment
                """
            ).fetchall()
        return [self._record(row) for row in rows]

    def update_service(
        self,
        service_name: str,
        environment: Union[str, Environment],
        *,
        owner: Optional[str] = None,
        replica_count: Optional[int] = None,
        deployment_status: Optional[Union[str, DeploymentStatus]] = None,
        resource_references: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        spec = InfrastructureSpec(service_name=service_name, environment=environment)
        updates = {}
        if owner is not None:
            if len(owner) > 128:
                raise ValueError("Owner must be at most 128 characters.")
            updates["owner"] = owner
        if replica_count is not None:
            if not 1 <= replica_count <= 20:
                raise ValueError("Replica count must be between 1 and 20.")
            updates["replica_count"] = replica_count
        if deployment_status is not None:
            updates["deployment_status"] = DeploymentStatus(deployment_status).value
        if resource_references is not None:
            if not isinstance(resource_references, list) or not all(
                isinstance(reference, str) for reference in resource_references
            ):
                raise ValueError("Resource references must be a list of strings.")
            updates["resource_references"] = json.dumps(resource_references)
        if not updates:
            raise ValueError("At least one service field must be provided.")
        updates["updated_at"] = self._now()
        assignments = ", ".join(f"{field} = ?" for field in updates)
        self.initialize()
        with self._connection() as connection:
            cursor = connection.execute(
                f"""
                UPDATE registered_services SET {assignments}
                WHERE service_name = ? AND environment = ?
                """,
                (*updates.values(), spec.service_name, spec.environment.value),
            )
            if cursor.rowcount == 0:
                raise ServiceNotFoundError(
                    f"Service '{spec.service_name}' was not found in '{spec.environment.value}'."
                )
            row = connection.execute(
                "SELECT * FROM registered_services WHERE service_name = ? AND environment = ?",
                (spec.service_name, spec.environment.value),
            ).fetchone()
        return self._record(row)

    def delete_service(
        self,
        service_name: str,
        environment: Union[str, Environment],
    ) -> bool:
        spec = InfrastructureSpec(service_name=service_name, environment=environment)
        self.initialize()
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM registered_services WHERE service_name = ? AND environment = ?",
                (spec.service_name, spec.environment.value),
            )
        if cursor.rowcount == 0:
            raise ServiceNotFoundError(
                f"Service '{spec.service_name}' was not found in '{spec.environment.value}'."
            )
        return True


service_registry = ServiceRegistry()
