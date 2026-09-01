from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Config, ConfigVersion, Approval
from app.schemas import ConfigChangeRequest
from app.audit import log_audit

router = APIRouter(
    prefix="/configs",
    tags=["Configuration Changes"]
)


@router.post("/{config_id}/change")
def request_config_change(
    config_id: int,
    change_data: ConfigChangeRequest,
    db: Session = Depends(get_db)
):
    config = (
        db.query(Config)
        .filter(Config.id == config_id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration with ID {config_id} not found"
        )

    # Check for existing pending approval on this config
    existing_pending = (
        db.query(Approval)
        .join(ConfigVersion, Approval.config_version_id == ConfigVersion.id)
        .filter(
            ConfigVersion.config_id == config_id,
            Approval.status == "pending"
        )
        .first()
    )

    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A change request is already pending approval for this configuration"
        )

    new_version_number = config.current_version + 1

    version = ConfigVersion(
        config_id=config.id,
        version=new_version_number,
        value=change_data.new_value,
        changed_by=None,
        change_reason=change_data.reason or f"Update value to {change_data.new_value}"
    )

    db.add(version)
    db.flush()

    approval = Approval(
        config_version_id=version.id,
        requested_by=None,
        status="pending",
        comment=change_data.reason
    )

    db.add(approval)

    log_audit(
        db=db,
        action="CONFIG_CHANGE_REQUESTED",
        resource_type="config",
        resource_id=config.id,
        details={
            "config_key": config.config_key,
            "old_value": config.current_value,
            "proposed_value": version.value,
            "proposed_version": new_version_number,
            "reason": change_data.reason
        }
    )

    db.commit()
    db.refresh(version)
    db.refresh(approval)

    return {
        "message": "Configuration change submitted for approval",
        "config_id": config.id,
        "config_key": config.config_key,
        "current_value": config.current_value,
        "current_version": config.current_version,
        "proposed_value": version.value,
        "proposed_version": version.version,
        "approval_id": approval.id,
        "approval_status": approval.status
    }