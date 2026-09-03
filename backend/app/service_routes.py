from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service, Config, ConfigVersion, Approval
from app.schemas import (
    ServiceRegisterRequest,
    ServiceRegisterResponse,
    ServiceDeleteResponse
)
from app.services import register_service
from app.audit import log_audit

router = APIRouter(
    prefix="/services",
    tags=["Services"]
)


@router.post(
    "/register",
    response_model=ServiceRegisterResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    service_data: ServiceRegisterRequest,
    db: Session = Depends(get_db)
):
    try:
        service = register_service(
            db,
            service_data
        )
        return service
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.get("/{service_id}", response_model=ServiceRegisterResponse)
def get_service_by_id(
    service_id: int,
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )
    return service


@router.delete(
    "/{service_id}",
    response_model=ServiceDeleteResponse
)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )

    service_name = service.service_name

    # Cascade deletion through ORM relationships
    db.delete(service)
    db.commit()

    # Log audit entry
    log_audit(
        db=db,
        action="SERVICE_DELETED",
        resource_type="service",
        resource_id=service_id,
        details={
            "service_name": service_name
        }
    )
    db.commit()

    return {
        "message": f"Service '{service_name}' (ID: {service_id}) and all associated configurations were deleted successfully.",
        "service_id": service_id,
        "service_name": service_name
    }