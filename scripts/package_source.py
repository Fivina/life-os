"""Create a deterministic source-only Life OS archive."""

from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".cache", ".tmp", ".tmp-v14", ".tmp-v15", "artifacts",
}
EXCLUDED_SUFFIXES = {
    ".log", ".pyc", ".pyo", ".tsbuildinfo", ".db", ".sqlite", ".sqlite3", ".zip",
    ".safetensors", ".ckpt", ".onnx", ".pt", ".pth",
}
EXCLUDED_GENERATED = {Path("apps/web/vite.config.js"), Path("apps/web/vite.config.d.ts")}
ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def is_secret_env(path: Path) -> bool:
    name = path.name.lower()
    return (name == ".env" or name.endswith(".env") or ".env." in name) and not name.endswith(".env.example")


def source_files(destination: Path) -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == destination:
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if is_secret_env(relative) or relative in EXCLUDED_GENERATED or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(relative)
    forbidden = [path for path in files if is_secret_env(path)]
    if forbidden:
        raise RuntimeError(f"Refusing to package secret environment files: {forbidden}")
    return sorted(files, key=lambda path: path.as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default=str(ROOT / ".cache" / "build" / "life-os-source.zip"))
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = source_files(destination)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in files:
            info = zipfile.ZipInfo(relative.as_posix(), date_time=ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (ROOT / relative).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    print(f"Created {destination} with {len(files)} source files.")


if __name__ == "__main__":
    main()
