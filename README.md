# Real-Time Configuration Management Platform (CCMS)

A centralized configuration management and live synchronization platform designed for microservices and distributed systems.

## Overview
CCMS provides zero-downtime, real-time configuration distribution with an administrative approval workflow, automated audit logging, immutable versioning, and non-destructive rollbacks.

## Key Capabilities
- **Centralized Control Plane**: Web dashboard to manage and inspect service configurations.
- **Two-Phase Approval Workflow**: Changes require administrative review before deployment.
- **Real-Time Push Distribution**: Sub-100ms updates via Redis Pub/Sub directly to client services.
- **Zero-Restart Client Integration**: Decoupled sync agent updates local configuration files without requiring service restarts.
- **Audit & Version History**: Full version chain with non-destructive rollback capabilities.

## Architecture
- **Frontend**: React + Vite (Control Plane UI)
- **Backend**: FastAPI + Python (REST API & Orchestration)
- **Database**: PostgreSQL with SQLAlchemy & Alembic
- **Message Broker**: Redis Pub/Sub with TLS support
- **Client Agent**: Lightweight Python background daemon
