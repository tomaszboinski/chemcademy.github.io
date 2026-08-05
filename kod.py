from pathlib import Path

# =====================================
# KONFIGURACJA
# =====================================

ROOT = Path(".")
OUTPUT = "project_dump.txt"

# Jakie pliki chcemy zczytać
INCLUDE_EXTENSIONS = {
    ".html",
    ".css",
    ".js",
    ".json",
    ".txt",
    ".md",
    ".svg"
}

IGNORE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    ".next",
    ".cache"
}

IGNORE_FILES = {
    ".DS_Store",
    "Thumbs.db"
}

MAX_FILE_SIZE = 1024 * 1024   # 1 MB


# =====================================
# STRUKTURA
# =====================================

def build_tree(directory: Path, prefix=""):
    lines = []

    items = sorted(
        [
            x for x in directory.iterdir()
            if x.name not in IGNORE_DIRS
            and x.name not in IGNORE_FILES
        ],
        key=lambda x: (x.is_file(), x.name.lower())
    )

    for i, item in enumerate(items):
        connector = "└── " if i == len(items)-1 else "├── "
        lines.append(prefix + connector + item.name)

        if item.is_dir():
            extension = "    " if i == len(items)-1 else "│   "
            lines.extend(build_tree(item, prefix + extension))

    return lines


# =====================================
# ZAPIS
# =====================================

with open(OUTPUT, "w", encoding="utf-8") as out:

    out.write("="*80 + "\n")
    out.write("PROJECT STRUCTURE\n")
    out.write("="*80 + "\n\n")

    out.write(ROOT.resolve().name + "\n")

    for line in build_tree(ROOT):
        out.write(line + "\n")

    out.write("\n\n")
    out.write("="*80 + "\n")
    out.write("FILES\n")
    out.write("="*80 + "\n\n")

    for file in sorted(ROOT.rglob("*")):

        if not file.is_file():
            continue

        if any(part in IGNORE_DIRS for part in file.parts):
            continue

        if file.name in IGNORE_FILES:
            continue

        if file.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue

        if file.stat().st_size > MAX_FILE_SIZE:
            continue

        rel = file.relative_to(ROOT)

        out.write("\n")
        out.write("="*80 + "\n")
        out.write(f"FILE: {rel}\n")
        out.write("="*80 + "\n\n")

        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = file.read_text(encoding="latin-1")
            except Exception:
                text = "<< NIE MOŻNA ODCZYTAĆ PLIKU >>"

        out.write(text)
        out.write("\n\n")

print(f"\nGotowe! Utworzono {OUTPUT}")