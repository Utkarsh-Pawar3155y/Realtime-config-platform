from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Service,
    Config,
    Approval,
    ConfigVersion,
    AuditLog
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/services")
def get_services(
    db: Session = Depends(get_db)
):
    services = db.query(Service).order_by(Service.created_at.desc()).all()
    now = datetime.now(timezone.utc)
    result = []

    for service in services:
        if service.last_seen is None:
            status_val = "offline"
        else:
            last_seen = service.last_seen
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)

            elapsed = (now - last_seen).total_seconds()
            if elapsed <= 30:
                status_val = "online"
            else:
                status_val = "offline"

        if service.status != status_val:
            service.status = status_val

        result.append({
            "id": service.id,
            "service_name": service.service_name,
            "environment": service.environment,
            "description": service.description,
            "status": status_val,
            "last_seen": service.last_seen.isoformat() if service.last_seen else None,
            "created_at": service.created_at.isoformat() if service.created_at else None
        })

    db.commit()
    return result


@router.get("/services/{service_id}/configs")
def get_service_configs(
    service_id: int,
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )

    configs = (
        db.query(Config)
        .filter(Config.service_id == service_id)
        .order_by(Config.config_key.asc())
        .all()
    )

    return [
        {
            "id": config.id,
            "service_id": config.service_id,
            "config_key": config.config_key,
            "current_value": config.current_value,
            "current_version": config.current_version,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        }
        for config in configs
    ]


@router.get("/approvals/pending")
def get_pending_approvals(
    db: Session = Depends(get_db)
):
    approvals = (
        db.query(Approval)
        .filter(Approval.status == "pending")
        .order_by(Approval.created_at.desc())
        .all()
    )

    result = []

    for approval in approvals:
        version = (
            db.query(ConfigVersion)
            .filter(ConfigVersion.id == approval.config_version_id)
            .first()
        )

        if not version:
            continue

        config = (
            db.query(Config)
            .filter(Config.id == version.config_id)
            .first()
        )

        if not config:
            continue

        service = (
            db.query(Service)
            .filter(Service.id == config.service_id)
            .first()
        )

        result.append({
            "approval_id": approval.id,
            "service_id": service.id if service else None,
            "service_name": service.service_name if service else "Unknown",
            "config_id": config.id,
            "config_key": config.config_key,
            "current_value": config.current_value,
            "proposed_value": version.value,
            "proposed_version": version.version,
            "reason": approval.comment or version.change_reason,
            "requested_by": approval.requested_by,
            "status": approval.status,
            "created_at": approval.created_at.isoformat() if approval.created_at else None
        })

    return result


@router.get("/history/{service_id}")
def get_configuration_history(
    service_id: int,
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )

    configs = (
        db.query(Config)
        .filter(Config.service_id == service_id)
        .order_by(Config.config_key.asc())
        .all()
    )

    result = []

    for config in configs:
        versions = (
            db.query(ConfigVersion)
            .filter(ConfigVersion.config_id == config.id)
            .order_by(ConfigVersion.version.desc())
            .all()
        )

        for version in versions:
            result.append({
                "version_id": version.id,
                "config_id": config.id,
                "config_key": config.config_key,
                "version": version.version,
                "value": version.value,
                "reason": version.change_reason,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "is_current": (version.version == config.current_version)
            })

    return result


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]