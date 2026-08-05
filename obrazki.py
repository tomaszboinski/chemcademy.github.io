import os
import re

ROOT = "."
ARTICLES_DIR = os.path.join(ROOT, "articles")


def collect_changes():
    changes = []

    for article in os.listdir(ARTICLES_DIR):
        article_path = os.path.join(ARTICLES_DIR, article)
        media_path = os.path.join(article_path, "media")

        if not os.path.isdir(media_path):
            continue

        counter = 1

        files = sorted(
            os.listdir(media_path),
            key=lambda x: (
                int(re.search(r'\d+', x).group())
                if re.search(r'\d+', x)
                else 9999
            )
        )

        for filename in files:
            if not filename.lower().startswith("image"):
                continue

            old_path = os.path.join(media_path, filename)

            if not os.path.isfile(old_path):
                continue

            ext = os.path.splitext(filename)[1]

            new_filename = f"{article}-{counter}{ext}"
            new_path = os.path.join(media_path, new_filename)

            changes.append({
                "article": article,
                "old": f"{article}/media/{filename}",
                "new": f"{article}/media/{new_filename}",
                "alt": f"{article} - rysunek-{counter}",
                "old_path": old_path,
                "new_path": new_path
            })

            counter += 1

    return changes


def rename_files(changes):
    for change in changes:
        if change["old_path"] != change["new_path"]:
            os.rename(
                change["old_path"],
                change["new_path"]
            )


def update_html(changes):
    for root, dirs, files in os.walk(ARTICLES_DIR):
        for file in files:

            if not file.endswith(".html"):
                continue

            html_path = os.path.join(root, file)

            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()

            original = content

            for change in changes:

                old = change["old"]
                new = change["new"]
                alt = change["alt"]

                # zmiana ścieżki obrazka
                content = content.replace(old, new)

                # dodanie alt do img
                pattern = (
                    r'(<img[^>]+src="' +
                    re.escape(new) +
                    r'"[^>]*)(>)'
                )

                replacement = (
                    r'\1 alt="' +
                    alt +
                    r'"\2'
                )

                content = re.sub(
                    pattern,
                    replacement,
                    content
                )

            if content != original:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(content)


if __name__ == "__main__":

    print("Szukam obrazów...")
    
    changes = collect_changes()

    print(f"Znaleziono obrazów: {len(changes)}")

    rename_files(changes)

    print("Nazwy obrazów zmienione.")

    update_html(changes)

    print("HTML zaktualizowane.")
    print("Gotowe.")