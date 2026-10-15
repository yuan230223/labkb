"""Build an allowlisted source archive without runtime data or local secrets."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = [
    "README.md",
    "pyproject.toml",
    "requirements.lock",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "Dockerfile",
    "compose.yaml",
    ".env.example",
    ".gitignore",
    ".dockerignore",
]
FOLDERS = {
    "src": {".py", ".html", ".css", ".js", ".md"},
    "tests": {".py"},
    "scripts": {".py", ".ps1"},
    "docs": {".md"},
    "examples": {".jsonl"},
    ".github": {".yml", ".yaml"},
}


def main():
    files = [ROOT / name for name in TOP_LEVEL]
    for folder, extensions in FOLDERS.items():
        files.extend(
            path
            for path in (ROOT / folder).rglob("*")
            if path.suffix in extensions and "__pycache__" not in path.parts
        )
    target = ROOT / "dist" / "labkb-0.1.0-source.zip"
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for path in sorted(files):
            if not path.is_file() or path.is_symlink():
                continue
            path.resolve().relative_to(ROOT)
            archive.write(path, str(Path("labkb") / path.relative_to(ROOT)))
    print(f"{target} ({len(files)} candidate files)")


if __name__ == "__main__":
    main()
