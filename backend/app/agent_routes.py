import io
import json
import zipfile
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Header,
    status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service, Config
from app.config import CCMS_URL, REDIS_URL

router = APIRouter(
    prefix="/agent",
    tags=["Config Agent"]
)


@router.get("/config/{service_id}")
def get_agent_config(
    service_id: int,
    x_agent_token: str | None = Header(default=None),
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
            detail="Service not found"
        )

    if not x_agent_token or x_agent_token != service.auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing agent authentication token"
        )

    configs = (
        db.query(Config)
        .filter(Config.service_id == service_id)
        .all()
    )

    return {
        "service_id": service.id,
        "service_name": service.service_name,
        "environment": service.environment,
        "configs": {
            config.config_key: config.current_value
            for config in configs
        }
    }


@router.post("/heartbeat/{service_id}")
def agent_heartbeat(
    service_id: int,
    x_agent_token: str | None = Header(default=None),
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
            detail="Service not found"
        )

    if not x_agent_token or x_agent_token != service.auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing agent authentication token"
        )

    now = datetime.now(timezone.utc)
    service.last_seen = now
    service.status = "online"

    db.commit()

    return {
        "service_id": service.id,
        "status": "online",
        "last_seen": service.last_seen.isoformat()
    }


@router.get("/download/{service_id}")
def download_agent(
    service_id: int,
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
            detail="Service not found"
        )

    agent_config = {
        "ccms_url": CCMS_URL,
        "redis_url": REDIS_URL,
        "service_id": service.id,
        "service_name": service.service_name,
        "environment": service.environment,
        "auth_token": service.auth_token,
        "config_file": ""
    }

    config_json = json.dumps(
        agent_config,
        indent=2
    )

    agent_code = r'''import json
import os
import sys
import threading
import time
import redis
import requests

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_CONFIG_FILE = os.path.join(AGENT_DIR, "agent_config.json")


def load_agent_config():
    if not os.path.exists(AGENT_CONFIG_FILE):
        print(f"ERROR: Configuration file '{AGENT_CONFIG_FILE}' not found.")
        sys.exit(1)
    with open(AGENT_CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


agent_config = load_agent_config()

CCMS_URL = os.getenv("CCMS_URL", agent_config.get("ccms_url", "http://127.0.0.1:8000")).rstrip("/")
REDIS_URL = os.getenv("REDIS_URL", agent_config.get("redis_url", "redis://localhost:6379"))
SERVICE_ID = agent_config["service_id"]
AUTH_TOKEN = agent_config["auth_token"]
CONFIG_FILE = agent_config.get("config_file", "")

if not CONFIG_FILE:
    print("=" * 60)
    print("WARNING: Target config.json path is not configured.")
    print("Please run setup.py first to configure and import your configuration.")
    print("=" * 60)
    sys.exit(1)

CONFIG_FILE = os.path.abspath(CONFIG_FILE)

# Connect to Redis (supports rediss:// for Upstash / TLS)
try:
    redis_kwargs = {
        "decode_responses": True,
        "socket_timeout": 10,
        "socket_connect_timeout": 10,
        "retry_on_timeout": True
    }
    if REDIS_URL.startswith("rediss://"):
        redis_kwargs["ssl_cert_reqs"] = None

    redis_client = redis.Redis.from_url(
        REDIS_URL,
        **redis_kwargs
    )
except Exception as err:
    print(f"[FATAL] Failed to initialize Redis connection: {err}")
    sys.exit(1)


def fetch_current_config():
    url = f"{CCMS_URL}/agent/config/{SERVICE_ID}"
    response = requests.get(
        url,
        headers={"X-Agent-Token": AUTH_TOKEN},
        timeout=10
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch configuration ({response.status_code}): {response.text}")
    return response.json()


def send_heartbeat():
    url = f"{CCMS_URL}/agent/heartbeat/{SERVICE_ID}"
    try:
        response = requests.post(
            url,
            headers={"X-Agent-Token": AUTH_TOKEN},
            timeout=5
        )
        if response.status_code == 200:
            print(f"[{time.strftime('%X')}] [HEARTBEAT] Service is ONLINE")
        else:
            print(f"[{time.strftime('%X')}] [HEARTBEAT WARN] Status {response.status_code}: {response.text}")
    except requests.RequestException as error:
        print(f"[{time.strftime('%X')}] [HEARTBEAT ERROR] Could not reach CCMS: {error}")


def heartbeat_loop():
    while True:
        send_heartbeat()
        time.sleep(10)


def write_config(config):
    directory = os.path.dirname(CONFIG_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)


def update_local_config(config_key, new_value):
    if not os.path.exists(CONFIG_FILE):
        config = {}
    else:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            try:
                config = json.load(file)
            except Exception:
                config = {}

    old_value = config.get(config_key)

    # Preserve type if old_value exists and new_value is passed as a string representation
    if old_value is not None:
        if isinstance(old_value, bool) and not isinstance(new_value, bool):
            if isinstance(new_value, str):
                new_value = new_value.strip().lower() in ("true", "1", "yes")
            else:
                new_value = bool(new_value)
        elif isinstance(old_value, int) and not isinstance(old_value, bool) and not isinstance(new_value, int):
            try:
                new_value = int(new_value)
            except (ValueError, TypeError):
                pass
        elif isinstance(old_value, float) and not isinstance(new_value, float):
            try:
                new_value = float(new_value)
            except (ValueError, TypeError):
                pass

    config[config_key] = new_value
    write_config(config)

    print(f"\n[REAL-TIME UPDATE RECEIVED]")
    print(f"  Key:     {config_key}")
    print(f"  Old:     {json.dumps(old_value)}")
    print(f"  New:     {json.dumps(new_value)}")
    print(f"  Updated: {CONFIG_FILE}\n")


def synchronize_initial_config():
    print("Synchronizing configuration from CCMS...")
    data = fetch_current_config()
    service_name = data.get("service_name", agent_config.get("service_name"))
    configs = data.get("configs", {})

    if not configs:
        print("[WARN] CCMS returned no configuration for this service.")
    else:
        write_config(configs)
        print(f"Initial configuration ({len(configs)} keys) synchronized to: {CONFIG_FILE}")


def start_agent():
    print("=" * 60)
    print("CCMS CONFIG AGENT (Production Ready)")
    print("=" * 60)
    print(f"Service ID:   {SERVICE_ID}")
    print(f"Service Name: {agent_config.get('service_name')}")
    print(f"Environment:  {agent_config.get('environment')}")
    print(f"CCMS URL:     {CCMS_URL}")
    print(f"Config File:  {CONFIG_FILE}")
    print("=" * 60)

    synchronize_initial_config()

    # Start heartbeat background thread
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        daemon=True
    )
    heartbeat_thread.start()

    channel = f"config-service-{SERVICE_ID}"
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel)

    print(f"Subscribed to Redis channel: {channel}")
    print("Listening for approved real-time configuration updates...\n")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        try:
            raw_data = message["data"]
            data = json.loads(raw_data)

            config_key = data["config_key"]
            new_value = data["new_value"]

            update_local_config(config_key, new_value)
        except Exception as error:
            print(f"[ERROR] Failed to process update message: {error}")


if __name__ == "__main__":
    start_agent()
'''

    setup_code = r'''import json
import os
import sys
import requests

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_CONFIG_FILE = os.path.join(AGENT_DIR, "agent_config.json")

if not os.path.exists(AGENT_CONFIG_FILE):
    print("ERROR: agent_config.json not found.")
    sys.exit(1)

with open(AGENT_CONFIG_FILE, "r", encoding="utf-8") as file:
    config = json.load(file)

print("=" * 60)
print("CCMS CONFIG AGENT SETUP")
print("=" * 60)
print(f"Service:     {config.get('service_name')}")
print(f"Service ID:  {config.get('service_id')}")
print(f"Environment: {config.get('environment')}")
print("=" * 60)
print()

input_path = input("Enter the full or relative path to your client service's config.json: ").strip()

if not input_path:
    print("ERROR: Path cannot be empty.")
    sys.exit(1)

config_file = os.path.abspath(input_path)

if not os.path.isfile(config_file):
    print()
    print(f"ERROR: File does not exist at: {config_file}")
    sys.exit(1)

try:
    with open(config_file, "r", encoding="utf-8") as file:
        local_config = json.load(file)
except json.JSONDecodeError as err:
    print(f"\nERROR: The file contains invalid JSON: {err}")
    sys.exit(1)

if not isinstance(local_config, dict):
    print("\nERROR: Configuration root must be a JSON object (dictionary).")
    sys.exit(1)

if not local_config:
    print("\nERROR: Configuration file is empty.")
    sys.exit(1)

print(f"\nUploading configuration ({len(local_config)} keys) to CCMS...")
import_url = f"{config['ccms_url']}/configs/import/{config['service_id']}"

try:
    with open(config_file, "rb") as file:
        response = requests.post(
            import_url,
            files={
                "file": (
                    os.path.basename(config_file),
                    file,
                    "application/json"
                )
            },
            timeout=15
        )
except requests.RequestException as error:
    print(f"\nERROR: Could not connect to CCMS at {config['ccms_url']}: {error}")
    sys.exit(1)

if response.status_code != 200:
    print(f"\nERROR: CCMS rejected configuration upload: {response.text}")
    sys.exit(1)

result = response.json()
print("\nConfiguration uploaded successfully!")
print("Imported keys:")
for key in result.get("configs_imported", []):
    print(f"  - {key}: {json.dumps(local_config.get(key))}")

config["config_file"] = config_file

with open(AGENT_CONFIG_FILE, "w", encoding="utf-8") as file:
    json.dump(config, file, indent=2)

print("\n" + "=" * 60)
print("SETUP COMPLETED SUCCESSFULLY!")
print("=" * 60)
print("You can now start the agent by running:")
print("    python config_agent.py")
print("=" * 60)
'''

    requirements = """requests>=2.31.0
redis>=5.0.0
"""

    readme = f"""CCMS Configuration Agent
==================================================
Service:     {service.service_name}
Service ID:  {service.id}
Environment: {service.environment}
==================================================

OVERVIEW
--------
This agent connects your client service to the CCMS platform without
requiring your service to expose any HTTP endpoints.

It is responsible for:
1. Fetching the initial configuration and writing it to your config.json.
2. Sending a heartbeat to CCMS every 10 seconds to indicate online status.
3. Subscribing to approved configuration changes in real time via Redis.
4. Updating your local config.json file automatically whenever a change is approved.

GETTING STARTED
---------------
1. Install Python 3.8+ on your client machine/server.

2. Install the agent dependencies:
   pip install -r requirements.txt

3. Run the initial setup script:
   python setup.py

   When prompted, enter the path to your service's config.json file.
   The script will validate the JSON and upload the initial keys to CCMS.

4. Start the agent:
   python config_agent.py

   The agent will run in the foreground (or you can run it as a systemd service / background task).
"""

    memory = io.BytesIO()

    with zipfile.ZipFile(
        memory,
        mode="w",
        compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr(
            "ccms-agent/agent_config.json",
            config_json
        )
        archive.writestr(
            "ccms-agent/config_agent.py",
            agent_code
        )
        archive.writestr(
            "ccms-agent/setup.py",
            setup_code
        )
        archive.writestr(
            "ccms-agent/requirements.txt",
            requirements
        )
        archive.writestr(
            "ccms-agent/README.md",
            readme
        )

    memory.seek(0)
    filename = f"{service.service_name}-ccms-agent.zip"

    return StreamingResponse(
        memory,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )