import os
import re

# Regex do znajdowania href/src w HTML, CSS, JS
pattern = re.compile(r'(?i)(href|src)\s*=\s*["\']([^"\']+)["\']')

def rename_files_and_dirs(root_dir="."):
    """
    Zmienia wszystkie pliki i katalogi na małe litery poprzez tymczasową nazwę.
    Przechodzi od najgłębszego katalogu do najwyższego.
    """
    for root, dirs, files in os.walk(root_dir, topdown=False):
        # Pliki
        for name in files:
            old_path = os.path.join(root, name)
            new_name = name.lower()
            new_path = os.path.join(root, new_name)
            if old_path != new_path:
                temp_path = old_path + "_tmp"
                os.rename(old_path, temp_path)
                os.rename(temp_path, new_path)
                print(f"RENAMED FILE: {old_path} -> {new_path}")
        # Katalogi
        for name in dirs:
            old_path = os.path.join(root, name)
            new_name = name.lower()
            new_path = os.path.join(root, new_name)
            if old_path != new_path:
                temp_path = old_path + "_tmp"
                os.rename(old_path, temp_path)
                os.rename(temp_path, new_path)
                print(f"RENAMED DIR: {old_path} -> {new_path}")

def fix_links(filepath):
    """Zamienia odwołania w HTML/CSS/JS na małe litery"""
    changed = False
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ Nie udało się otworzyć pliku {filepath}: {e}")
        return

    def replacer(match):
        nonlocal changed
        attr, path = match.groups()
        if path.startswith("http") or path.startswith("//"):
            return match.group(0)
        new_path = path.lower()
        if path != new_path:
            changed = True
            print(f"[{filepath}] {path} -> {new_path}")
        return f'{attr}="{new_path}"'

    new_content = pattern.sub(replacer, content)

    if changed:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

def main():
    # 1. Zmieniamy nazwy plików i folderów w całym repo
    rename_files_and_dirs(".")

    # 2. Poprawiamy linki wewnątrz plików
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith((".html", ".htm", ".css", ".js")):
                fix_links(os.path.join(root, file))

if __name__ == "__main__":
    main()