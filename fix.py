import os
import json
from bs4 import BeautifulSoup


DOMAIN = "https://www.chemcademy.edu.pl"

FOLDERS = [
    "zadania",
    "articles"
]


def normalize_url(url):
    if not url:
        return url

    return (
        url
        .replace("https://chemcademy.edu.pl", DOMAIN)
        .replace("http://chemcademy.edu.pl", DOMAIN)
    )


def page_url(filepath):
    filepath = filepath.replace("\\", "/")
    return DOMAIN + "/" + filepath


def extract_meta(soup, name):

    tag = soup.find(
        "meta",
        attrs={"name": name}
    )

    if tag:
        return tag.get("content", "").strip()

    return ""


def replace_urls(soup):

    canonical = soup.find(
        "link",
        rel="canonical"
    )

    if canonical and canonical.get("href"):
        canonical["href"] = normalize_url(
            canonical["href"]
        )


    for meta in soup.find_all("meta"):

        if meta.get("content"):

            meta["content"] = normalize_url(
                meta["content"]
            )


def fix_breadcrumb(soup, filepath):

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:
            data = json.loads(script.string)

        except:
            continue


        if data.get("@type") == "BreadcrumbList":

            items = data.get(
                "itemListElement",
                []
            )

            for item in items:

                position = item.get(
                    "position"
                )

                name = item.get(
                    "name",
                    ""
                )

                if position == 1:
                    item["item"] = DOMAIN

                elif "Zadania" in name:
                    item["item"] = (
                        DOMAIN + "/zadania/"
                    )

                elif "Artyku" in name:
                    item["item"] = (
                        DOMAIN + "/articles/"
                    )

                elif position == len(items):
                    item["item"] = page_url(
                        filepath
                    )


            script.string = json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            )


def remove_article_schema(soup):

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:
            data = json.loads(script.string)

        except:
            continue


        typ = data.get("@type")

        if typ == "Article":

            script.decompose()

        elif isinstance(typ, list) and "Article" in typ:

            script.decompose()



def create_schema(soup, filepath):

    title = ""

    if soup.title:
        title = soup.title.text.strip()


    description = extract_meta(
        soup,
        "description"
    )


    schema = {

        "@context": "https://schema.org",

        "@type": "Article",

        "headline": title,

        "description": description,

        "author": {
            "@type": "Organization",
            "name": "Chemcademy"
        },

        "publisher": {
            "@type": "Organization",
            "name": "Chemcademy",
            "url": DOMAIN
        },

        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": page_url(filepath)
        },

        "url": page_url(filepath)

    }


    if "/zadania/" in filepath.replace("\\", "/"):

        schema["@type"] = [
            "Article",
            "LearningResource"
        ]

        schema["learningResourceType"] = (
            "zadanie chemiczne"
        )

        schema["educationalLevel"] = (
            "szkoła średnia"
        )


    return schema



def add_schema(soup, schema):

    script = soup.new_tag(
        "script",
        type="application/ld+json"
    )

    script.string = json.dumps(
        schema,
        ensure_ascii=False,
        indent=2
    )

    soup.head.append(script)



def process_file(filepath):

    with open(
        filepath,
        "r",
        encoding="utf-8"
    ) as f:
        html = f.read()


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    replace_urls(soup)

    fix_breadcrumb(
        soup,
        filepath
    )

    remove_article_schema(
        soup
    )


    schema = create_schema(
        soup,
        filepath
    )

    add_schema(
        soup,
        schema
    )


    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            str(soup)
        )


    print("OK:", filepath)



def main():

    for folder in FOLDERS:

        for root, dirs, files in os.walk(folder):

            for file in files:

                if file.endswith(".html"):

                    process_file(
                        os.path.join(
                            root,
                            file
                        )
                    )


if __name__ == "__main__":
    main()