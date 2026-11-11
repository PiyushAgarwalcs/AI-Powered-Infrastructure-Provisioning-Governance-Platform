import pytest
from fastapi import HTTPException

import main
from requirement_parser import Environment
from service_registry import (
    DeploymentStatus,
    DuplicateServiceError,
    ServiceNotFoundError,
    ServiceRegistry,
)


def run_sync(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


@pytest.fixture
def registry(tmp_path):
    store = ServiceRegistry(tmp_path / "service-registry.sqlite3")
    store.initialize()
    return store


def test_registry_crud_and_status_updates(registry):
    created = registry.create_service(
        service_name="payments-api",
        owner="platform-team",
        environment=Environment.DEVELOPMENT,
        replica_count=2,
        resource_references=["namespace/payments-api-development"],
    )

    assert created["service_name"] == "payments-api"
    assert created["owner"] == "platform-team"
    assert created["deployment_status"] == DeploymentStatus.PENDING.value
    assert created["resource_references"] == [
        "namespace/payments-api-development"
    ]
    assert created["created_at"]
    assert registry.get_service("payments-api", "development") == created

    updated = registry.update_service(
        "payments-api",
        "development",
        replica_count=3,
        deployment_status=DeploymentStatus.RUNNING,
        resource_references=[
            "namespace/payments-api-development",
            "deployment/payments-api",
            "service/payments-api-service",
        ],
    )
    assert updated["replica_count"] == 3
    assert updated["deployment_status"] == "running"
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] >= created["updated_at"]
    assert len(registry.list_services()) == 1

    assert registry.delete_service("payments-api", "development") is True
    assert registry.list_services() == []
    assert registry.get_service("payments-api", "development") is None


def test_registry_scopes_service_name_by_environment(registry):
    registry.create_service("shared-api", "team-a", "development", 1)
    registry.create_service("shared-api", "team-a", "production", 3)

    assert len(registry.list_services()) == 2
    assert registry.get_service("shared-api", "production")["replica_count"] == 3


def test_registry_rejects_duplicate_and_unknown_service(registry):
    registry.create_service("duplicate-api", "team", "development", 1)

    with pytest.raises(DuplicateServiceError):
        registry.create_service("duplicate-api", "team", "development", 1)
    with pytest.raises(ServiceNotFoundError):
        registry.update_service(
            "missing-api", "development", deployment_status="running"
        )
    with pytest.raises(ServiceNotFoundError):
        registry.delete_service("missing-api", "development")


def test_registry_upsert_preserves_creation_timestamp(registry):
    created = registry.upsert_service(
        "orders-api",
        "team",
        "staging",
        2,
        "not-ready",
        ["deployment/orders-api"],
    )
    updated = registry.upsert_service(
        "orders-api",
        "team",
        "staging",
        3,
        "running",
        ["deployment/orders-api", "service/orders-api-service"],
    )

    assert updated["created_at"] == created["created_at"]
    assert updated["replica_count"] == 3
    assert updated["deployment_status"] == "running"


def test_service_registry_api_crud(registry, monkeypatch):
    monkeypatch.setattr(main, "service_registry", registry)
    request = main.ServiceRegistrationRequest(
        service_name="checkout-api",
        owner="payments",
        environment=Environment.STAGING,
        replica_count=2,
        resource_references=["deployment/checkout-api"],
    )
    created = run_sync(main.register_service(request))
    fetched = run_sync(
        main.get_registered_service("staging", "checkout-api")
    )
    updated = run_sync(
        main.update_registered_service(
            Environment.STAGING,
            "checkout-api",
            main.ServiceUpdateRequest(
                deployment_status=DeploymentStatus.RUNNING,
                replica_count=4,
                resource_references=[
                    "deployment/checkout-api",
                    "service/checkout-api-service",
                ],
            ),
        )
    )
    listing = run_sync(main.list_registered_services())
    deleted = run_sync(
        main.delete_registered_service(
            Environment.STAGING, "checkout-api"
        )
    )

    assert created["owner"] == "payments"
    assert fetched["service_name"] == "checkout-api"
    assert updated["deployment_status"] == "running"
    assert updated["replica_count"] == 4
    assert len(listing["services"]) == 1
    assert deleted.status_code == 204
    assert registry.list_services() == []


def test_service_registry_api_maps_conflicts_and_missing_records(registry, monkeypatch):
    monkeypatch.setattr(main, "service_registry", registry)
    request = main.ServiceRegistrationRequest(
        service_name="catalog-api",
        environment=Environment.DEVELOPMENT,
        replica_count=1,
    )
    run_sync(main.register_service(request))

    with pytest.raises(HTTPException) as duplicate:
        run_sync(main.register_service(request))
    assert duplicate.value.status_code == 409

    with pytest.raises(HTTPException) as missing:
        run_sync(
            main.get_registered_service("development", "not-registered")
        )
    assert missing.value.status_code == 404


def test_empty_service_update_is_rejected(registry):
    registry.create_service("empty-patch-api", "team", "development", 1)

    with pytest.raises(ValueError):
        registry.update_service("empty-patch-api", "development")
