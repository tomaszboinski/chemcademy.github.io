from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


SITE_URL = "https://chemcademy.edu.pl"
ROOT = Path(".")
OUTPUT = "sitemap.xml"

IGNORE = {
    "header.html",
    "footer.html",
    "sitemap.xml",
    "mytemplate.html",
    "output.html",
    "workinprogress.html"
}


urlset = Element(
    "urlset",
    {
        "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"
    }
)


for file in ROOT.rglob("*.html"):

    # pomijanie plików technicznych
    if file.name in IGNORE:
        continue

    # ścieżka względna względem katalogu strony
    relative_path = file.relative_to(ROOT).as_posix()

    # kodowanie URL:
    # spacje -> %20
    # polskie znaki -> %XX
    url_path = "/" + quote(relative_path)

    # index.html -> /
    if url_path == "/index.html":
        url_path = "/"

    # data modyfikacji
    timestamp = datetime.fromtimestamp(
        file.stat().st_mtime
    ).strftime("%Y-%m-%d")


    url = SubElement(urlset, "url")

    loc = SubElement(url, "loc")
    loc.text = SITE_URL + url_path

    lastmod = SubElement(url, "lastmod")
    lastmod.text = timestamp



# ładniejsze formatowanie XML (Python 3.9+)
indent(urlset, space="    ")


tree = ElementTree(urlset)

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)


print(f"Generated {OUTPUT}")