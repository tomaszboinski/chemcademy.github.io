from pathlib import Path
import re

# Wszystkie symbole mnożenia, które zamieniamy na U+00B7
def normalize_math(match):
    text = match.group(0)

    # LaTeX
    text = text.replace(r"\cdot", "·")

    # Unicode
    text = text.replace("⋅", "·")
    text = text.replace("×", "·")

    # Zamień pojedyncze *
    # Nie rusza **
    text = re.sub(r'(?<!\*)\*(?!\*)', '·', text)

    return text


def process_html(content):
    """
    Zamienia symbole mnożenia wyłącznie
    wewnątrz bloków matematycznych Pandoca/MathJax.
    """

    patterns = [
        r'<span class="math.*?</span>',  # MathJax inline/display
        r'\$\$.*?\$\$',                  # $$ ... $$
        r'\$.*?\$',                      # $ ... $
        r'\\\(.*?\\\)',                  # \( ... \)
        r'\\\[.*?\\\]'                   # \[ ... \]
    ]

    for pattern in patterns:
        content = re.sub(
            pattern,
            normalize_math,
            content,
            flags=re.DOTALL
        )

    return content


def process_directory(root="."):
    root = Path(root)

    count = 0

    for file in root.rglob("*.html"):
        try:
            print(f"Przetwarzam: {file}")

            text = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            new_text = process_html(text)

            if text != new_text:
                file.write_text(
                    new_text,
                    encoding="utf-8"
                )
                count += 1

        except Exception as e:
            print(f"Błąd {file}: {e}")

    print()
    print(f"Zmodyfikowano {count} plików HTML.")


if __name__ == "__main__":
    # "." = aktualny katalog i wszystkie podkatalogi
    process_directory(".")