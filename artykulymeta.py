from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import quote


SITE_URL = "https://chemcademy.edu.pl"

ROOT = Path(".")
FOLDERS = [
    "articles",
    "zadania"
]
MAIN_PAGES = {
    "index.html": "Chemcademy - materiały z chemii, teoria, zadania i obliczenia chemiczne dla uczniów.",
    
    "artykuly.html": "Artykuły chemiczne - teoria, wyjaśnienia i opracowania tematów z chemii.",
    
    "zadania.html": "Zadania chemiczne z rozwiązaniami i metodami obliczeń.",
    
    "oferta.html": "Oferta Chemcademy - materiały edukacyjne, przygotowanie z chemii i pomoc w nauce.",
    
    "kontakt.html": "Kontakt z Chemcademy - informacje dotyczące współpracy i pytań.",
    
    "about_me.html": "Informacje o autorze Chemcademy i projekcie edukacyjnym z chemii.",
    
    "toc.html": "Spis treści materiałów Chemcademy.",
    
    "tocolchem.html": "Materiały przygotowujące do olimpiady chemicznej.",
    
    "toczadania.html": "Spis zadań chemicznych dostępnych w Chemcademy.",
     
    "zadaniaolchem.html" : "Spis zadań olimpiady chemicznej z podziałem na tematy."
}
def process_main_pages():

    for filename, description in MAIN_PAGES.items():

        path = ROOT / filename

        if not path.exists():
            continue

        print("STRONA:", path)

        html = path.read_text(
            encoding="utf-8"
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        head = soup.find("head")

        if not head:
            continue


        title_tag = soup.find("title")

        if title_tag:
            title = title_tag.text.strip()
        else:
            title = filename.replace(".html","")


        relative = filename

        url = (
            SITE_URL +
            "/" +
            quote(relative)
        )


        add_meta(
            head,
            "description",
            description
        )


        if not soup.find(
            "link",
            rel="canonical"
        ):

            canonical = soup.new_tag(
                "link"
            )

            canonical["rel"]="canonical"
            canonical["href"]=url

            head.append(canonical)



        add_property(
            head,
            "og:title",
            title
        )

        add_property(
            head,
            "og:description",
            description
        )

        add_property(
            head,
            "og:type",
            "website"
        )

        add_property(
            head,
            "og:url",
            url
        )


        add_meta(
            head,
            "twitter:card",
            "summary"
        )

        add_meta(
            head,
            "twitter:title",
            title
        )

        add_meta(
            head,
            "twitter:description",
            description
        )


        path.write_text(
            soup.prettify(),
            encoding="utf-8"
        )

def add_meta(head, name, content):

    if head.find(
        "meta",
        attrs={"name": name}
    ):
        return

    tag = head.new_tag(
        "meta"
    )

    tag["name"] = name
    tag["content"] = content

    head.append(tag)



def add_property(head, prop, content):

    if head.find(
        "meta",
        attrs={"property": prop}
    ):
        return

    tag = head.new_tag(
        "meta"
    )

    tag["property"] = prop
    tag["content"] = content

    head.append(tag)



def process_file(path):

    print("SEO:", path)

    html = path.read_text(
        encoding="utf-8"
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    head = soup.find("head")

    if not head:
        print("Brak head:", path)
        return


    # TITLE

    title_tag = soup.find("title")

    if title_tag:
        title = title_tag.text.strip()
    else:
        title = path.stem


    # DESCRIPTION

    description = ""

    old_desc = head.find(
        "meta",
        attrs={"name": "description"}
    )

    if old_desc:
        description = old_desc.get(
            "content",
            ""
        )


    if not description:

        for p in soup.find_all("p"):

            txt = p.get_text(
                strip=True
            )

            if len(txt) > 20:
                description = txt
                break


    if not description:
        description = (
            f"Materiały z chemii - {title}"
        )


    description = description[:155]


    # URL

    relative = str(
        path
    ).replace("\\", "/")

    url = (
        SITE_URL +
        "/" +
        quote(relative)
    )


    # META DESCRIPTION

    add_meta(
        head,
        "description",
        description
    )


    # CANONICAL

    if not soup.find(
        "link",
        rel="canonical"
    ):

        canonical = soup.new_tag(
            "link"
        )

        canonical["rel"] = "canonical"
        canonical["href"] = url

        head.append(canonical)



    # OPEN GRAPH

    add_property(
        head,
        "og:title",
        title
    )

    add_property(
        head,
        "og:description",
        description
    )

    add_property(
        head,
        "og:type",
        "article"
    )

    add_property(
        head,
        "og:url",
        url
    )


    # TWITTER

    add_meta(
        head,
        "twitter:card",
        "summary"
    )

    add_meta(
        head,
        "twitter:title",
        title
    )

    add_meta(
        head,
        "twitter:description",
        description
    )


    path.write_text(
        soup.prettify(),
        encoding="utf-8"
    )


    print("OK")



for folder in FOLDERS:

    directory = ROOT / folder

    if not directory.exists():
        continue


    for file in directory.rglob("*.html"):

        process_file(file)

process_main_pages()

print("\nSEO gotowe")