from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models import AuditLog


def log_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None
) -> AuditLog:
    """Create and persist an audit log entry."""
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {}
    )
    db.add(audit_entry)
    return audit_entry