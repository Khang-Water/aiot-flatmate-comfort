"""Download pinned Vietnamese Piper voice assets for Docker builds."""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium"
FILES = (
    (
        "vi_VN-vais1000-medium.onnx",
        "ec7c89e2c85f4d1edc24b6120c18aaf1bda614f06b511567eb9c7c0de15e2dab",
    ),
    (
        "vi_VN-vais1000-medium.onnx.json",
        "fafb9da1354ed4b77c31af228ed41fb41cd825c14cffa105454b25e6ae751ee0",
    ),
)


def download(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 6):
        digest = hashlib.sha256()
        try:
            request = Request(url, headers={"User-Agent": "FlatMate-Comfort-Docker-Build"})
            with urlopen(request, timeout=120) as response, destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != expected_sha256:
                raise ValueError(f"SHA-256 mismatch for {destination.name}")
            return
        except (OSError, ValueError) as error:
            destination.unlink(missing_ok=True)
            if attempt == 5:
                raise RuntimeError(f"Cannot download {destination.name}") from error
            time.sleep(attempt * 2)


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("models")
    # ponytail: One pinned Render voice; add a manifest only when deployment needs multiple voices.
    for filename, checksum in FILES:
        download(f"{BASE_URL}/{filename}", output_dir / filename, checksum)


if __name__ == "__main__":
    main()
