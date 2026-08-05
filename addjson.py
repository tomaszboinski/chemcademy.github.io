from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote
import json


SITE_URL = "https://chemcademy.edu.pl"

ROOT = Path(".")


IGNORE = {
    "header.html",
    "footer.html",
    "sitemap.xml"
}


def add_meta(head, name, content):

    tag = head.find(
        "meta",
        attrs={"name": name}
    )

    if tag:
        tag["content"] = content
        return

    tag = head.new_tag("meta")
    tag["name"] = name
    tag["content"] = content

    head.append(tag)



def add_property(head, prop, content):

    tag = head.find(
        "meta",
        attrs={"property": prop}
    )

    if tag:
        tag["content"] = content
        return

    tag = head.new_tag("meta")
    tag["property"] = prop
    tag["content"] = content

    head.append(tag)



def get_description(soup, title):

    old = soup.find(
        "meta",
        attrs={"name":"description"}
    )

    if old:
        return old.get("content","")


    for p in soup.find_all("p"):

        text = p.get_text(
            strip=True
        )

        if len(text) > 30:
            return text[:155]


    return f"Materiały chemiczne - {title}"



def fix_title(path, soup):

    old = soup.find("title")


    if "articles" in path.parts:

        name = path.stem.replace(
            "-",
            " "
        ).capitalize()

        title = (
            f"{name} - chemia teoria i obliczenia | Chemcademy"
        )


    elif "zadania" in path.parts:

        name = path.stem.replace(
            "-",
            " "
        ).capitalize()

        title = (
            f"{name} - zadanie chemiczne | Chemcademy"
        )


    elif path.name == "index.html":

        title = (
            "Chemcademy - chemia, teoria, zadania i obliczenia"
        )


    else:

        name = path.stem.replace(
            "_",
            " "
        ).capitalize()

        title = (
            f"{name} | Chemcademy"
        )


    if old:
        old.string = title
    else:
        old = soup.new_tag("title")
        old.string = title
        soup.head.append(old)


    return title



def add_canonical(head, url):

    if head.find(
        "link",
        rel="canonical"
    ):
        return


    link = head.new_tag(
        "link"
    )

    link["rel"] = "canonical"
    link["href"] = url

    head.append(link)



def add_jsonld(head, data):

    script = head.new_tag(
        "script",
        type="application/ld+json"
    )

    script.string = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    head.append(script)



def process(path):

    html = path.read_text(
        encoding="utf-8"
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    head = soup.find("head")

    if not head:
        return


    # usuń stare JSON-LD
    for s in soup.find_all(
        "script",
        attrs={
            "type":"application/ld+json"
        }
    ):
        s.decompose()



    title = fix_title(
        path,
        soup
    )


    description = get_description(
        soup,
        title
    )


    url = (
        SITE_URL +
        "/" +
        quote(
            path.as_posix()
        )
    )


    # META

    add_meta(
        head,
        "description",
        description
    )


    add_canonical(
        head,
        url
    )


    # OG

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
        "og:url",
        url
    )


    add_property(
        head,
        "og:type",
        "article" if (
            "articles" in path.parts or
            "zadania" in path.parts
        )
        else
        "website"
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


    date = datetime.fromtimestamp(
        path.stat().st_mtime
    ).strftime(
        "%Y-%m-%d"
    )


    # JSON-LD

    if "articles" in path.parts:

        schema = {

            "@context":"https://schema.org",

            "@type":"Article",

            "headline":title,

            "description":description,

            "dateModified":date,

            "author":{
                "@type":"Organization",
                "name":"Chemcademy"
            },

            "publisher":{
                "@type":"Organization",
                "name":"Chemcademy"
            },

            "mainEntityOfPage":url
        }


    elif "zadania" in path.parts:

        schema = {

            "@context":"https://schema.org",

            "@type":"LearningResource",

            "name":title,

            "description":description,

            "learningResourceType":
                "zadanie chemiczne",

            "educationalLevel":
                "szkoła średnia",

            "url":url
        }


    else:

        schema = {

            "@context":"https://schema.org",

            "@type":"WebSite",

            "name":title,

            "url":url
        }


    add_jsonld(
        head,
        schema
    )


    # BREADCRUMB

    if "articles" in path.parts or "zadania" in path.parts:

        section = (
            "Artykuły chemiczne"
            if "articles" in path.parts
            else
            "Zadania chemiczne"
        )


        breadcrumb = {

            "@context":"https://schema.org",

            "@type":"BreadcrumbList",

            "itemListElement":[

                {
                    "@type":"ListItem",
                    "position":1,
                    "name":"Chemcademy",
                    "item":SITE_URL
                },

                {
                    "@type":"ListItem",
                    "position":2,
                    "name":section,
                },

                {
                    "@type":"ListItem",
                    "position":3,
                    "name":title,
                    "item":url
                }

            ]
        }


        add_jsonld(
            head,
            breadcrumb
        )


    path.write_text(
        soup.prettify(),
        encoding="utf-8"
    )


    print("OK:", path)



for file in ROOT.rglob(
    "*.html"
):

    if file.name in IGNORE:
        continue

    process(file)


print("\nSEO zakończone")