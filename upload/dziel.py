import os
import re
import pymupdf as fitz


# ============================================================
# KONFIGURACJA
# ============================================================

FILES = [
    "53wst.pdf",
    "54wst.pdf",
]

OUTPUT_SUFFIX = "_podzielone"


# ============================================================
# WZORCE
# ============================================================

TASK_RE = re.compile(
    r"^\s*ZADANIE\s+([AB]?\d+[AB]?)\b",
    re.IGNORECASE
)

# Marker rozpoczynający część z rozwiązaniami.
# W obu plikach po tym miejscu pojawiają się ponownie
# nagłówki "ZADANIE X", ale są to już rozwiązania.
SOLUTION_MARKER_RE = re.compile(
    r"Rozwiązania\s+zadań\s+etapu\s+wstępnego",
    re.IGNORECASE
)


# ============================================================
# NUMER ZADANIA
# ============================================================

def normalize_number(value):
    value = value.strip().upper()

    m = re.fullmatch(r"(\d+)([AB])", value)

    if m:
        return f"{m.group(2)}{m.group(1)}"

    return value


# ============================================================
# CZYSZCZENIE
# ============================================================

def clean(text):
    return (
        text
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .strip()
    )


# ============================================================
# ODCZYT NAGŁÓWKÓW Z JEDNEJ STRONY
# ============================================================

def find_tasks_on_page(page):
    """
    Zwraca wszystkie nagłówki:
        ZADANIE 1A
        ZADANIE 2A
        ...

    Nie rozstrzyga tutaj, czy jest to zadanie czy rozwiązanie.
    To rozstrzygamy dopiero po markerze.
    """

    result = []

    try:
        data = page.get_text("dict")
    except Exception:
        return result

    for block in data.get("blocks", []):

        if "lines" not in block:
            continue

        for line in block["lines"]:

            text = "".join(
                span.get("text", "")
                for span in line.get("spans", [])
            )

            text = clean(text)

            if not text:
                continue

            match = TASK_RE.match(text)

            if not match:
                continue

            rect = fitz.Rect(
                line["bbox"]
            )

            result.append({
                "number": normalize_number(
                    match.group(1)
                ),
                "rect": rect,
                "text": text,
            })

    result.sort(
        key=lambda x: (
            x["rect"].y0,
            x["rect"].x0
        )
    )

    return result


# ============================================================
# CZY STRONA ZACZYNA CZĘŚĆ ROZWIĄZAŃ
# ============================================================

def page_has_solution_marker(page):

    try:
        text = page.get_text("text")
    except Exception:
        return False

    return bool(
        SOLUTION_MARKER_RE.search(
            clean(text)
        )
    )


# ============================================================
# ZNAJDOWANIE WSZYSTKICH ZADAŃ I ROZWIĄZAŃ
# ============================================================

def find_sections(doc):

    tasks = {}
    solutions = {}

    in_solutions = False

    for page_no in range(len(doc)):

        page = doc[page_no]

        # ----------------------------------------------------
        # Najpierw marker.
        #
        # Jeżeli marker i ZADANIE 1A są na tej samej stronie,
        # ZADANIE 1A zostanie poprawnie potraktowane jako
        # rozwiązanie.
        # ----------------------------------------------------

        if (
            not in_solutions
            and page_has_solution_marker(page)
        ):
            in_solutions = True

            print(
                f"   → część rozwiązań od strony {page_no + 1}"
            )

        page_tasks = find_tasks_on_page(page)

        for item in page_tasks:

            number = item["number"]

            section = {
                "number": number,
                "start_page": page_no,
                "start_y": item["rect"].y0,
                "heading": item["text"],
            }

            if in_solutions:

                # Drugie wystąpienie = rozwiązanie.
                solutions[number] = section

            else:

                # Pierwsze wystąpienie = treść zadania.
                #
                # Nie nadpisujemy pierwszego wystąpienia.
                if number not in tasks:
                    tasks[number] = section

    return tasks, solutions


# ============================================================
# USTALENIE KOŃCA SEKCJI
# ============================================================

def finish_sections(doc, sections):

    """
    Dla każdego nagłówka ustala koniec:
    dokładnie przed następnym nagłówkiem tej samej części.

    Ważne:
    zadanie nie może "wciągnąć" pierwszej strony rozwiązań.
    """

    ordered = sorted(
        sections.values(),
        key=lambda x: (
            x["start_page"],
            x["start_y"]
        )
    )

    for i, section in enumerate(ordered):

        start_page = section["start_page"]
        start_y = section["start_y"]

        if i + 1 < len(ordered):

            next_section = ordered[i + 1]

            section["end_page"] = (
                next_section["start_page"]
            )

            section["end_y"] = (
                next_section["start_y"]
            )

        else:

            section["end_page"] = (
                len(doc) - 1
            )

            section["end_y"] = (
                doc[
                    len(doc) - 1
                ].rect.height
            )

    return sections


# ============================================================
# KOPIOWANIE SEKCJI DO NOWEGO PDF
# ============================================================

def copy_section(
    source,
    output,
    section
):

    start_page = section["start_page"]
    end_page = section["end_page"]

    start_y = section["start_y"]
    end_y = section["end_y"]

    for page_no in range(
        start_page,
        end_page + 1
    ):

        page = source[page_no]

        width = page.rect.width
        height = page.rect.height

        # ----------------------------------------------------
        # Jedna strona
        # ----------------------------------------------------

        if (
            start_page == end_page
        ):

            crop = fitz.Rect(
                0,
                start_y,
                width,
                end_y
            )

        # ----------------------------------------------------
        # Pierwsza strona
        # ----------------------------------------------------

        elif page_no == start_page:

            crop = fitz.Rect(
                0,
                start_y,
                width,
                height
            )

        # ----------------------------------------------------
        # Ostatnia strona
        # ----------------------------------------------------

        elif page_no == end_page:

            crop = fitz.Rect(
                0,
                0,
                width,
                end_y
            )

        # ----------------------------------------------------
        # Środkowa strona
        # ----------------------------------------------------

        else:

            crop = fitz.Rect(
                0,
                0,
                width,
                height
            )

        # ----------------------------------------------------
        # Nie dodajemy pustych / błędnych cropów
        # ----------------------------------------------------

        if crop.width <= 0 or crop.height <= 0:
            continue

        new_page = output.new_page(
            width=crop.width,
            height=crop.height
        )

        new_page.show_pdf_page(
            new_page.rect,
            source,
            page_no,
            clip=crop
        )


# ============================================================
# SORTOWANIE
# ============================================================

def number_key(number):

    m = re.search(
        r"(\d+)",
        str(number)
    )

    if m:
        n = int(m.group(1))
    else:
        n = 999999

    if str(number).startswith("A"):
        group = 1
    elif str(number).startswith("B"):
        group = 2
    else:
        group = 0

    return (
        group,
        n
    )


# ============================================================
# PRZETWARZANIE JEDNEGO PLIKU
# ============================================================

def process_file(input_path):

    filename = os.path.basename(
        input_path
    )

    print()
    print("=" * 70)
    print(f" {filename}")
    print("=" * 70)

    source = fitz.open(
        input_path
    )

    print(
        f" Stron: {len(source)}"
    )

    tasks, solutions = find_sections(
        source
    )

    # --------------------------------------------------------
    # Ustalamy końce sekcji.
    # --------------------------------------------------------

    tasks = finish_sections(
        source,
        tasks
    )

    solutions = finish_sections(
        source,
        solutions
    )

    print(
        f" Zadania: {len(tasks)}"
    )

    print(
        f" Rozwiązania: {len(solutions)}"
    )

    # --------------------------------------------------------
    # Pary
    # --------------------------------------------------------

    common = sorted(
        set(tasks) & set(solutions),
        key=number_key
    )

    missing_solution = sorted(
        set(tasks) - set(solutions),
        key=number_key
    )

    missing_task = sorted(
        set(solutions) - set(tasks),
        key=number_key
    )

    if missing_solution:

        print()
        print(
            " Brak rozwiązań:"
        )

        print(
            "  " +
            ", ".join(
                missing_solution
            )
        )

    if missing_task:

        print()
        print(
            " Rozwiązania bez zadania:"
        )

        print(
            "  " +
            ", ".join(
                missing_task
            )
        )

    # --------------------------------------------------------
    # Folder wynikowy
    # --------------------------------------------------------

    base = os.path.splitext(
        filename
    )[0]

    output_dir = os.path.join(
        os.path.dirname(input_path),
        base + OUTPUT_SUFFIX
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Tworzenie
    # --------------------------------------------------------

    created = 0

    print()
    print(" TWORZENIE:")

    for number in common:

        task = tasks[number]
        solution = solutions[number]

        output_path = os.path.join(
            output_dir,
            f"{base}-{number}.pdf"
        )

        print(
            f"  {number}: "
            f"zadanie str. {task['start_page'] + 1}, "
            f"rozwiązanie str. {solution['start_page'] + 1}"
        )

        output = fitz.open()

        try:

            copy_section(
                source,
                output,
                task
            )

            copy_section(
                source,
                output,
                solution
            )

            if len(output) == 0:

                print(
                    "     ❌ pusty PDF"
                )

                output.close()
                continue

            if os.path.exists(
                output_path
            ):
                os.remove(
                    output_path
                )

            output.save(
                output_path,
                garbage=4,
                deflate=True
            )

            output.close()

            print(
                f"     ✅ {os.path.basename(output_path)}"
            )

            created += 1

        except Exception as e:

            print(
                f"     ❌ {e}"
            )

            try:
                output.close()
            except Exception:
                pass

    source.close()

    print()
    print(
        f" GOTOWE: {created} plików"
    )

    print(
        f" Wyniki: {output_dir}"
    )

    return created


# ============================================================
# MAIN
# ============================================================

def main():

    script_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    print()
    print("=" * 70)
    print(" DZIELENIE 53wst + 54wst")
    print("=" * 70)

    total = 0

    for filename in FILES:

        path = os.path.join(
            script_dir,
            filename
        )

        if not os.path.isfile(path):

            print()
            print(
                f"⚠ NIE ZNALEZIONO: {filename}"
            )

            continue

        try:

            total += process_file(
                path
            )

        except Exception as e:

            print()
            print(
                f"❌ BŁĄD {filename}:"
            )

            print(
                f"   {e}"
            )

    print()
    print("=" * 70)
    print(
        f" ŁĄCZNIE UTWORZONO: {total}"
    )
    print("=" * 70)

    input(
        "\nENTER — koniec..."
    )


if __name__ == "__main__":
    main()
