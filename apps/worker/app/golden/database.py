"""Own a private PostgreSQL cluster; never accept an external database URL."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def disposable_postgres(binary_directory: Path):
    root = Path(tempfile.mkdtemp(prefix="clipfactory-golden-pg-"))
    root.chmod(0o700)
    data = root / "data"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    started = False
    try:
        subprocess.run(
            [
                str(binary_directory / "initdb"),
                "-D",
                str(data),
                "-U",
                "golden",
                "-A",
                "trust",
                "--encoding=UTF8",
                "--no-locale",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                str(binary_directory / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(root / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {port} -k {root}",
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
        )
        started = True
        subprocess.run(
            [
                str(binary_directory / "createdb"),
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-U",
                "golden",
                "clipfactory_test",
            ],
            check=True,
        )
        yield f"postgresql://golden@127.0.0.1:{port}/clipfactory_test"
    finally:
        if started:
            subprocess.run(
                [
                    str(binary_directory / "pg_ctl"),
                    "-D",
                    str(data),
                    "-m",
                    "immediate",
                    "-w",
                    "stop",
                ],
                capture_output=True,
                check=True,
            )
        shutil.rmtree(root)
