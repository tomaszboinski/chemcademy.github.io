import os
import re

# folder z plikami HTML
folder = "."

for root, dirs, files in os.walk(folder):
    for file in files:
        if file.endswith(".html"):
            path = os.path.join(root, file)

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # zmiana istniejącego lang/xml:lang
            new_content = re.sub(
                r'<html[^>]*>',
                '<html lang="pl" xml:lang="pl" xmlns="http://www.w3.org/1999/xhtml">',
                content,
                count=1
            )

            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                print(f"Zmieniono: {path}")
            else:
                print(f"Bez zmian: {path}")