from pathlib import Path
import re


ROOT = Path(".")
OUTPUT = "mapa-strony.html"


pages = []


# szuka wszystkich html
for file in ROOT.rglob("*.html"):

    # pomija samą mapę
    if file.name == OUTPUT:
        continue

    # zamienia ścieżkę Windows na /
    url = file.as_posix()

    pages.append(url)



# sortowanie
pages.sort()


html = """<!DOCTYPE html>
<html lang="pl">

<head>
<meta charset="UTF-8">

<title>Mapa strony - ChemCademy</title>

<meta name="robots" content="noindex, follow">

</head>

<body>

<h1>Mapa strony</h1>

<ul>
"""


for page in pages:

    # próba pobrania tytułu z pliku
    try:
        text = Path(page).read_text(
            encoding="utf-8"
        )

        title = re.search(
            r"<title>(.*?)</title>",
            text,
            re.IGNORECASE | re.DOTALL
        )

        if title:
            name = title.group(1).strip()
        else:
            name = page

    except:
        name = page


    html += f"""
<li>
<a href="{page}">
{name}
</a>
</li>
"""


html += """
</ul>

</body>
</html>
"""


Path(OUTPUT).write_text(
    html,
    encoding="utf-8"
)


print(
    f"Gotowe. Dodano {len(pages)} stron."
)