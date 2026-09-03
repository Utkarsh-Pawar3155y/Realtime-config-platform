from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Config, ConfigVersion, Approval
from app.schemas import RollbackRequest
from app.audit import log_audit

router = APIRouter(
    prefix="/configs",
    tags=["Rollback"]
)


@router.post("/{config_id}/rollback")
def rollback_config(
    config_id: int,
    rollback_data: RollbackRequest,
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

    # Fetch the historical target version
    target_version = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.id == rollback_data.version_id,
            ConfigVersion.config_id == config_id
        )
        .first()
    )

    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target version record with ID {rollback_data.version_id} not found for this configuration"
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
            detail="A change or rollback request is already pending approval for this configuration"
        )

    new_version_number = config.current_version + 1
    reason_text = (
        f"Rollback to version {target_version.version}"
        + (f": {rollback_data.reason}" if rollback_data.reason else "")
    )

    # Create a brand new version representing the rollback state (never delete historical versions)
    new_version = ConfigVersion(
        config_id=config.id,
        version=new_version_number,
        value=target_version.value,
        changed_by=None,
        change_reason=reason_text
    )

    db.add(new_version)
    db.flush()

    approval = Approval(
        config_version_id=new_version.id,
        requested_by=None,
        status="pending",
        comment=reason_text
    )

    db.add(approval)

    log_audit(
        db=db,
        action="CONFIG_ROLLBACK_REQUESTED",
        resource_type="config",
        resource_id=config.id,
        details={
            "config_key": config.config_key,
            "target_historical_version": target_version.version,
            "target_value": target_version.value,
            "new_proposed_version": new_version_number,
            "reason": reason_text
        }
    )

    db.commit()
    db.refresh(new_version)
    db.refresh(approval)

    return {
        "message": f"Rollback to version {target_version.version} submitted for approval as version {new_version_number}",
        "config_id": config.id,
        "config_key": config.config_key,
        "current_value": config.current_value,
        "current_version": config.current_version,
        "rollback_target_version": target_version.version,
        "proposed_value": new_version.value,
        "proposed_version": new_version.version,
        "approval_id": approval.id,
        "approval_status": approval.status
    }