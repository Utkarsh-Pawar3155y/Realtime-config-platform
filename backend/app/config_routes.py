import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service, Config, ConfigVersion
from app.audit import log_audit

router = APIRouter(
    prefix="/configs",
    tags=["Configurations"]
)


@router.post("/import/{service_id}")
async def import_config(
    service_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    service = (
        db.query(Service)
        .filter(Service.id == service_id)
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JSON configuration files (.json) are supported"
        )

    try:
        contents = await file.read()
        config_data = json.loads(contents.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format. Please upload a valid JSON file."
        )

    if not isinstance(config_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration root must be a JSON object (dictionary)."
        )

    if not config_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration file cannot be empty."
        )

    imported_configs = []

    for key, value in config_data.items():
        existing_config = (
            db.query(Config)
            .filter(
                Config.service_id == service_id,
                Config.config_key == key
            )
            .first()
        )

        if existing_config:
            existing_config.current_value = value
            existing_config.current_version += 1

            version = ConfigVersion(
                config_id=existing_config.id,
                version=existing_config.current_version,
                value=value,
                change_reason="Configuration file re-import"
            )
            db.add(version)
        else:
            config = Config(
                service_id=service_id,
                config_key=key,
                current_value=value,
                current_version=1
            )
            db.add(config)
            db.flush()

            version = ConfigVersion(
                config_id=config.id,
                version=1,
                value=value,
                change_reason="Initial configuration import"
            )
            db.add(version)

        imported_configs.append(key)

    log_audit(
        db=db,
        action="CONFIG_IMPORTED",
        resource_type="service",
        resource_id=service_id,
        details={
            "keys_imported": imported_configs,
            "count": len(imported_configs)
        }
    )

    db.commit()

    return {
        "message": "Configuration imported successfully",
        "service_id": service_id,
        "service_name": service.service_name,
        "configs_imported": imported_configs
    }