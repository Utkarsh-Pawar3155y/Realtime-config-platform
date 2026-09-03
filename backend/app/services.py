import secrets
from sqlalchemy.orm import Session
from app.models import Service
from app.schemas import ServiceRegisterRequest
from app.audit import log_audit


def register_service(
    db: Session,
    service_data: ServiceRegisterRequest
) -> Service:
    normalized_name = service_data.service_name.strip()
    existing_service = (
        db.query(Service)
        .filter(Service.service_name == normalized_name)
        .first()
    )

    if existing_service:
        raise ValueError(f"Service '{normalized_name}' already exists")

    auth_token = secrets.token_urlsafe(32)

    # Initial status is offline until agent starts and sends first heartbeat
    service = Service(
        service_name=normalized_name,
        environment=service_data.environment.strip(),
        description=service_data.description.strip() if service_data.description else None,
        auth_token=auth_token,
        status="offline"
    )

    db.add(service)
    db.commit()
    db.refresh(service)

    # Log audit entry
    log_audit(
        db=db,
        action="SERVICE_REGISTERED",
        resource_type="service",
        resource_id=service.id,
        details={
            "service_name": service.service_name,
            "environment": service.environment
        }
    )
    db.commit()

    return service