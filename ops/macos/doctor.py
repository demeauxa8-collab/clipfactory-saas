"""Read-only health checks, except a temporary signed-media round trip."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import asyncpg
import httpx
import redis

REPO = Path(__file__).resolve().parents[2]
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")
API_DIR = REPO / "apps/api"
WORKER_DIR = REPO / "apps/worker"
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)

from app.services.storage import presigned_get_url
from app.settings import get_settings

failures = 0


class CheckError(RuntimeError):
    """An intentionally safe, user-facing reason with no credentials."""


def check(name: str, operation) -> None:
    global failures
    try:
        detail = operation()
        # A detail containing "WARN" is reported but never counts as a failure.
        status = "WARN" if "WARN" in str(detail) else "OK"
        print(f"{status} {name}: {detail}", flush=True)
    except CheckError as exc:
        failures += 1
        print(f"KO {name}: {exc}", flush=True)
    except Exception as exc:  # noqa: BLE001 - hide potentially sensitive client errors
        failures += 1
        # Never include exception text: HTTP and DB clients may embed credentials.
        print(f"KO {name}: {type(exc).__name__}", flush=True)


def run(*args: str, timeout: int = 20) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise CheckError("command failed")
    return result.stdout


def env_names(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"\'')
    return values


worker_env = env_names(WORKER_DIR / ".env")
settings = None
try:
    settings = get_settings()
except Exception:  # noqa: BLE001 - doctor still reports checks with missing configuration
    settings = None


def require_settings():
    if settings is None:
        raise CheckError("API environment missing")
    return settings


def tools_check():
    names = ["python3.12", "ffmpeg", "ffprobe", "yt-dlp", "deno"]
    versions = []
    for name in names:
        path = shutil.which(name)
        if path is None:
            raise CheckError(f"{name} missing")
        first_line = run(
            path, "-version" if name in ("ffmpeg", "ffprobe") else "--version"
        ).splitlines()[0]
        parts = first_line.split()
        version = parts[2] if name in ("ffmpeg", "ffprobe") else (
            parts[0] if name == "yt-dlp" else parts[1]
        )
        versions.append(f"{name} {version}")
    filters = run("ffmpeg", "-hide_banner", "-filters")
    if not re.search(r"\s+ass\s", filters) or not re.search(r"\s+subtitles\s", filters):
        raise CheckError("libass filters missing")
    return ", ".join(versions) + ", libass"


def redis_check():
    address = require_settings().redis_url
    client = redis.Redis.from_url(address, socket_timeout=3)
    if client.ping() is not True:
        raise CheckError("no PONG")
    bind = client.config_get("bind").get("bind", "")
    protected = client.config_get("protected-mode").get("protected-mode", "")
    if not bind or any(host not in ("127.0.0.1", "::1") for host in bind.split()):
        raise CheckError("Redis bind is not localhost-only")
    if protected != "yes":
        raise CheckError("Redis protected mode disabled")
    return "PONG, localhost only"


def health(url: str):
    response = httpx.get(url, timeout=10, follow_redirects=False)
    if response.status_code != 200 or response.json().get("status") != "ok":
        raise CheckError("health failed")
    return "status ok"


def public_health():
    base = require_settings().api_base_url
    if not base.startswith("https://"):
        raise CheckError("public URL must be HTTPS")
    return health(base.rstrip("/") + "/health")


def cors_check():
    response = httpx.options(
        "http://127.0.0.1:8000/health",
        headers={"Origin": "https://clipfactory-saas.vercel.app",
                 "Access-Control-Request-Method": "GET"}, timeout=10,
    )
    if response.headers.get("access-control-allow-origin") != "https://clipfactory-saas.vercel.app":
        raise CheckError("CORS origin missing")
    return "Vercel origin allowed"


async def database_check_async():
    conn = await asyncpg.connect(require_settings().database_url, statement_cache_size=0,
                                 timeout=10)
    try:
        if await conn.fetchval("select 1") != 1:
            raise CheckError("select 1 failed")
    finally:
        await conn.close()


def storage_check():
    s = require_settings()
    if s.storage_backend != "local":
        raise CheckError("local storage inactive")
    root = Path(s.storage_local_dir)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="doctor-", suffix=".mp4", dir=root,
                                     delete=False) as handle:
        handle.write(b"clipfactory-doctor")
        path = Path(handle.name)
    try:
        key = path.name
        url = presigned_get_url(key)
        media_base = s.media_base_url or s.api_base_url
        if not url.startswith(media_base.rstrip("/") + "/media/"):
            raise CheckError("wrong media URL")
        response = httpx.get(url, timeout=20)
        if response.status_code != 200 or response.content != b"clipfactory-doctor":
            raise CheckError("media round trip failed")
        partial = httpx.get(url, headers={"Range": "bytes=0-3"}, timeout=20)
        if partial.status_code != 206 or partial.content != b"clip":
            raise CheckError("public media seeking failed")
        download = httpx.get(url + "&download=1", timeout=20)
        if "attachment" not in download.headers.get("content-disposition", ""):
            raise CheckError("attachment download failed")
        expired = httpx.get(presigned_get_url(key, expires_in=-1), timeout=20)
        if expired.status_code != 403:
            raise CheckError("expired URL accepted")
    finally:
        path.unlink(missing_ok=True)
    return "signed public download and expiry verified"


def provider_check(url: str, token: str):
    if not token:
        raise CheckError("API key missing")
    response = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if response.status_code != 200:
        raise CheckError("provider rejected key")
    return "key accepted"


def asr_check():
    if worker_env.get("ASR_BACKEND", "openai") != "mlx_whisper":
        return "OpenAI selected"
    script = (
        "import asyncio,math,struct,tempfile,time,wave,os; "
        "from app.settings import get_settings; "
        "from app.pipeline.asr_mlx import transcribe_mlx; "
        "p=tempfile.mktemp(suffix='.wav'); "
        "w=wave.open(p,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); "
        "w.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(2*math.pi*440*i/16000))) "
        "if 16000<=i<32000 else b'\\0\\0' for i in range(80000))); w.close(); "
        "t=time.monotonic(); asyncio.run(transcribe_mlx(p,get_settings().mlx_whisper_model)); "
        "print(round(time.monotonic()-t,2)); os.unlink(p)"
    )
    result = run(str(WORKER_DIR / ".venv/bin/python"), "-c", script, timeout=600)
    return f"MLX decoded in {result.strip().splitlines()[-1]} s"


def youtube_check():
    binary = worker_env.get("YT_DLP_BIN") or shutil.which("yt-dlp")
    run(binary, "--simulate", "--remote-components", "ejs:github",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", timeout=90)
    return "public video accessible"


def services_check():
    for name in ("api", "worker"):
        output = run("launchctl", "print", f"gui/{os.getuid()}/com.clipfactory.{name}")
        if "state = running" not in output:
            raise CheckError("service not running")
    return "api and worker running"


def disk_check():
    free = shutil.disk_usage(Path.home()).free / 1024**3
    if free < 40:
        raise CheckError("free space below 40 GB")
    workdir = Path(worker_env.get("WORKER_TMP_DIR") or "/tmp/clipfactory")
    size = sum(p.stat().st_size for p in workdir.rglob("*") if p.is_file()) if workdir.exists() else 0
    if size > 20 * 1024**3:
        raise CheckError("worker temp above 20 GB")
    return f"{free:.1f} GB free, temp {size / 1024**3:.1f} GB"


def sleep_check():
    output = run("pmset", "-g")
    if not re.search(r"^\s*sleep\s+0\b", output, re.MULTILINE):
        raise CheckError("sleep is not zero")
    return "sleep 0"


check("Tools", tools_check)
check("Redis", redis_check)
check("Local API", lambda: health("http://127.0.0.1:8000/health"))
check("Public API", public_health)
check("CORS", cors_check)
check("Database", lambda: (asyncio.run(database_check_async()), "select 1")[1])
check("Storage", storage_check)
check("OpenRouter", lambda: provider_check("https://openrouter.ai/api/v1/key",
                                           worker_env.get("OPENROUTER_API_KEY", "")))
check("OpenAI", lambda: provider_check("https://api.openai.com/v1/models/whisper-1",
                                       worker_env.get("OPENAI_API_KEY", "")))
check("Local ASR", asr_check)
check("YouTube", youtube_check)
check("Services", services_check)
check("Disk", disk_check)
check("Sleep", sleep_check)
sys.exit(1 if failures else 0)
