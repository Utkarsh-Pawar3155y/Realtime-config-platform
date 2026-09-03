import json
import os
import sys
import threading
import time
import redis
import requests

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_CONFIG_FILE = os.path.join(AGENT_DIR, "agent_config.json")

# Fallback defaults if running standalone script directly with argv
if len(sys.argv) == 3:
    SERVICE_ID = int(sys.argv[1])
    CONFIG_FILE = os.path.abspath(sys.argv[2])
    CCMS_URL = os.getenv("CCMS_URL", "http://127.0.0.1:8000").rstrip("/")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
elif os.path.exists(AGENT_CONFIG_FILE):
    with open(AGENT_CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    SERVICE_ID = cfg["service_id"]
    CONFIG_FILE = os.path.abspath(cfg.get("config_file", ""))
    CCMS_URL = os.getenv("CCMS_URL", cfg.get("ccms_url", "http://127.0.0.1:8000")).rstrip("/")
    REDIS_URL = os.getenv("REDIS_URL", cfg.get("redis_url", "redis://localhost:6379"))
    AUTH_TOKEN = cfg.get("auth_token", "")
else:
    print("Usage: python config_agent.py <service_id> <config_file>")
    sys.exit(1)

if not CONFIG_FILE:
    print("ERROR: Target config.json path is not configured.")
    sys.exit(1)

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

service_name = None


def fetch_current_config():
    url = f"{CCMS_URL}/agent/config/{SERVICE_ID}"
    headers = {}
    if AUTH_TOKEN:
        headers["X-Agent-Token"] = AUTH_TOKEN

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch configuration ({response.status_code}): {response.text}")
    return response.json()


def send_heartbeat():
    url = f"{CCMS_URL}/agent/heartbeat/{SERVICE_ID}"
    headers = {}
    if AUTH_TOKEN:
        headers["X-Agent-Token"] = AUTH_TOKEN

    try:
        response = requests.post(url, headers=headers, timeout=5)
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
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
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

    # Preserve type
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
    global service_name
    print("Fetching current configuration from CCMS...")
    data = fetch_current_config()
    service_name = data.get("service_name", f"service-{SERVICE_ID}")
    configs = data.get("configs", {})
    write_config(configs)
    print(f"Service: {service_name}")
    print(f"Config file: {CONFIG_FILE}")
    print(f"Initial configuration ({len(configs)} keys) synchronized.\n")


def start_agent():
    synchronize_initial_config()

    # Start heartbeat loop if AUTH_TOKEN is present
    if AUTH_TOKEN:
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()

    channel = f"config-service-{SERVICE_ID}"
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel)

    print("=" * 60)
    print("CCMS CONFIG AGENT")
    print("=" * 60)
    print(f"Service ID:  {SERVICE_ID}")
    print(f"Service:     {service_name}")
    print(f"Listening:   {channel}")
    print(f"Config file: {CONFIG_FILE}")
    print("Waiting for configuration updates...\n")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        try:
            data = json.loads(message["data"])
            config_key = data["config_key"]
            new_value = data["new_value"]
            update_local_config(config_key, new_value)
        except Exception as error:
            print(f"[ERROR] {error}")


if __name__ == "__main__":
    start_agent()