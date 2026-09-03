import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Approval, ConfigVersion, Config
from app.redis_client import redis_client
from app.schemas import ApprovalRejectRequest
from app.audit import log_audit

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"]
)


@router.post("/{approval_id}/approve")
def approve_change(
    approval_id: int,
    db: Session = Depends(get_db)
):
    approval = (
        db.query(Approval)
        .filter(Approval.id == approval_id)
        .first()
    )

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request with ID {approval_id} not found"
        )

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request is already '{approval.status}'"
        )

    version = (
        db.query(ConfigVersion)
        .filter(ConfigVersion.id == approval.config_version_id)
        .first()
    )

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated configuration version not found"
        )

    config = (
        db.query(Config)
        .filter(Config.id == version.config_id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated configuration not found"
        )

    # Approve and apply configuration change
    approval.status = "approved"
    approval.approved_by = None
    approval.approved_at = datetime.now(timezone.utc)

    old_value = config.current_value
    config.current_value = version.value
    config.current_version = version.version

    # Log audit entry
    log_audit(
        db=db,
        action="CONFIG_CHANGE_APPROVED",
        resource_type="approval",
        resource_id=approval.id,
        details={
            "config_id": config.id,
            "config_key": config.config_key,
            "old_value": old_value,
            "new_value": config.current_value,
            "version": config.current_version
        }
    )

    db.commit()

    # Distribute real-time configuration update via Redis Pub/Sub
    service_id = config.service_id
    channel = f"config-service-{service_id}"

    message = {
        "config_id": config.id,
        "config_key": config.config_key,
        "new_value": config.current_value,
        "version": config.current_version
    }

    try:
        redis_client.publish(
            channel,
            json.dumps(message)
        )
    except Exception as e:
        logger.error(f"Failed to publish config update to Redis: {e}")

    return {
        "message": "Configuration change approved and deployed in real-time",
        "approval_id": approval.id,
        "config_id": config.id,
        "config_key": config.config_key,
        "new_value": config.current_value,
        "new_version": config.current_version,
        "approval_status": approval.status,
        "redis_channel": channel
    }


@router.post("/{approval_id}/reject")
def reject_change(
    approval_id: int,
    reject_data: ApprovalRejectRequest = None,
    db: Session = Depends(get_db)
):
    approval = (
        db.query(Approval)
        .filter(Approval.id == approval_id)
        .first()
    )

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request with ID {approval_id} not found"
        )

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request is already '{approval.status}'"
        )

    version = (
        db.query(ConfigVersion)
        .filter(ConfigVersion.id == approval.config_version_id)
        .first()
    )

    approval.status = "rejected"
    approval.approved_by = None
    approval.approved_at = datetime.now(timezone.utc)
    if reject_data and reject_data.comment:
        approval.comment = f"{approval.comment or ''} | Rejected: {reject_data.comment}".strip(" | ")

    log_audit(
        db=db,
        action="CONFIG_CHANGE_REJECTED",
        resource_type="approval",
        resource_id=approval.id,
        details={
            "config_version_id": approval.config_version_id,
            "version": version.version if version else None,
            "rejected_comment": reject_data.comment if reject_data else None
        }
    )

    db.commit()

    return {
        "message": "Configuration change request rejected",
        "approval_id": approval.id,
        "approval_status": "rejected"
    }