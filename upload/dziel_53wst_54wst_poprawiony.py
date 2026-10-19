import pymupdf as fitz
import re
import os
import sys
import traceback

OUTPUT_SUFFIX = "_podzielone"

# TYLKO TE DWA PLIKI
FILES = {
    "53wst.pdf",
    "54wst.pdf",
}

TASK_RE = re.compile(
    r"^\s*ZADANIE\s*([AB]?\d+[AB]?)\b",
    re.IGNORECASE
)


def normalize_task_number(value):
    value = value.strip().upper()

    match = re.fullmatch(r"(\d+)([AB])", value)

    if match:
        number = match.group(1)
        letter = match.group(2)
        return f"{letter}{number}"

    return value


def clean_line(text):
    return (
        text
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .strip()
    )


def page_is_empty(page):
    """
    Sprawdza, czy strona jest praktycznie pusta.
    Strony z samymi nagłówkami/nieistotnym tekstem też mogą być pominięte
    przy szukaniu ZADANIE X.
    """
    try:
        blocks = page.get_text("blocks")
    except Exception:
        return True

    meaningful = []

    for block in blocks:
        if len(block) < 5:
            continue

        value = clean_line(block[4])

        if not value:
            continue

        # Pomijamy tylko techniczne / puste fragmenty.
        meaningful.append(value)

    return len(meaningful) == 0


def find_task_headings_on_page(page):
    """Znajduje wyłącznie nagłówki ZADANIE X na stronie."""

    headings = []

    if page_is_empty(page):
        return headings

    try:
        data = page.get_text("dict")
    except Exception as e:
        print(f"      ⚠ Błąd odczytu strony: {e}")
        return headings

    for block in data.get("blocks", []):
        if "lines" not in block:
            continue

        for line in block["lines"]:
            line_text = "".join(
                span.get("text", "")
                for span in line.get("spans", [])
            )

            line_text = clean_line(line_text)

            if not line_text:
                continue

            # Nie traktuj tych tekstów jako ZADANIE.
            if IGNORE_HEADINGS_RE.match(line_text):
                continue

            match = TASK_RE.match(line_text)

            if not match:
                continue

            headings.append({
                "type": "task",
                "number": normalize_task_number(match.group(1)),
                "rect": fitz.Rect(line["bbox"]),
                "text": line_text,
            })

    headings.sort(
        key=lambda x: (
            x["rect"].y0,
            x["rect"].x0
        )
    )

    # Fallback: jeżeli zwykły parser nie znalazł nagłówka,
    # próbujemy złożyć go z WORDS.
    if not headings:
        try:
            words = page.get_text("words")
        except Exception:
            words = []

        if words:
            # grupowanie po podobnym Y
            lines = []
            for word in sorted(words, key=lambda w: (w[1], w[0])):
                placed = False
                mid_y = (word[1] + word[3]) / 2

                for line in lines:
                    line_mid_y = sum((w[1] + w[3]) / 2 for w in line) / len(line)
                    if abs(mid_y - line_mid_y) <= 7:
                        line.append(word)
                        placed = True
                        break

                if not placed:
                    lines.append([word])

            for line in lines:
                line.sort(key=lambda w: w[0])

                joined = "".join(
                    w[4].strip().upper()
                    for w in line
                )

                match = re.search(
                    r"^ZADANIE(?:\\s*)?([AB]?\\d+[AB]?)\\b",
                    joined,
                    re.IGNORECASE
                )

                if not match:
                    continue

                number = normalize_task_number(match.group(1))

                rect = fitz.Rect(
                    min(w[0] for w in line),
                    min(w[1] for w in line),
                    max(w[2] for w in line),
                    max(w[3] for w in line)
                )

                headings.append({
                    "type": "task",
                    "number": number,
                    "rect": rect,
                    "text": f"ZADANIE {number}",
                })

    headings.sort(
        key=lambda x: (
            x["rect"].y0,
            x["rect"].x0
        )
    )

    return headings


def find_all_headings(doc):
    """
    Znajduje wszystkie wystąpienia ZADANIE X na niepustych stronach.

    WAŻNE:
    - pierwsze wystąpienie danego numeru = TREŚĆ ZADANIA
    - drugie wystąpienie danego numeru = ROZWIĄZANIE

    Nie używamy żadnego napisu typu:
    'Rozwiązania zadań etapu wstępnego'.
    """

    headings = []
    occurrences = {}

    for page_number in range(len(doc)):
        page = doc[page_number]

        page_headings = find_task_headings_on_page(page)

        for heading in page_headings:
            number = heading["number"]

            occurrences[number] = occurrences.get(number, 0) + 1
            occurrence = occurrences[number]

            if occurrence == 1:
                heading["type"] = "task"
            elif occurrence == 2:
                heading["type"] = "solution"
            else:
                # Trzecie i kolejne wystąpienie tego samego numeru
                # traktujemy jako kolejne rozwiązanie tego zadania.
                heading["type"] = "solution"

            heading["occurrence"] = occurrence
            heading["page"] = page_number

            headings.append(heading)

    return headings


def create_sections(doc, headings):
    """
    Każdy znaleziony nagłówek wyznacza początek sekcji.
    Sekcja kończy się tuż przed następnym nagłówkiem ZADANIE X.
    """

    sections = []

    for i, heading in enumerate(headings):

        start_page = heading["page"]
        start_y = heading["rect"].y0

        if i + 1 < len(headings):

            next_heading = headings[i + 1]

            end_page = next_heading["page"]
            end_y = next_heading["rect"].y0

        else:

            end_page = len(doc) - 1
            end_y = doc[end_page].rect.height

        sections.append({
            "type": heading["type"],
            "number": heading["number"],
            "occurrence": heading["occurrence"],
            "start_page": start_page,
            "start_y": start_y,
            "end_page": end_page,
            "end_y": end_y,
            "heading": heading["text"],
        })

    return sections


def add_section_to_pdf(source, output, section):
    start_page = section["start_page"]
    end_page = section["end_page"]

    start_y = section["start_y"]
    end_y = section["end_y"]

    for page_number in range(start_page, end_page + 1):

        source_page = source[page_number]

        width = source_page.rect.width
        height = source_page.rect.height

        if page_number == start_page:

            if start_page == end_page:
                crop = fitz.Rect(
                    0,
                    start_y,
                    width,
                    end_y
                )
            else:
                crop = fitz.Rect(
                    0,
                    start_y,
                    width,
                    height
                )

        elif page_number == end_page:

            crop = fitz.Rect(
                0,
                0,
                width,
                end_y
            )

        else:

            crop = fitz.Rect(
                0,
                0,
                width,
                height
            )

        if crop.height <= 1:
            continue

        new_page = output.new_page(
            width=crop.width,
            height=crop.height
        )

        new_page.show_pdf_page(
            new_page.rect,
            source,
            page_number,
            clip=crop
        )


def sort_key(number):
    match = re.search(r"(\d+)", str(number))

    if match:
        numeric = int(match.group(1))
    else:
        numeric = 999999

    number_string = str(number)

    if number_string.startswith("A"):
        group = 1
    elif number_string.startswith("B"):
        group = 2
    else:
        group = 0

    return group, numeric


def process_pdf(input_pdf):

    filename = os.path.basename(input_pdf)

    print()
    print("=" * 70)
    print(f" PRZETWARZANIE: {filename}")
    print("=" * 70)

    try:
        source = fitz.open(input_pdf)
    except Exception as e:
        print(f"❌ Nie można otworzyć PDF: {e}")
        return 0

    print(f"📄 Stron: {len(source)}")
    print()
    print("🔎 Szukanie wystąpień ZADANIE X...")

    headings = find_all_headings(source)

    if not headings:
        print("❌ Nie znaleziono nagłówków ZADANIE X.")
        source.close()
        return 0

    print()
    print(f"✅ Znaleziono wystąpień: {len(headings)}")
    print()

    for heading in headings:
        print(
            f"   {heading['type']:8s} "
            f"{heading['number']:>5}  "
            f"wystąpienie #{heading['occurrence']}  "
            f"strona {heading['page'] + 1:>3}"
        )

    sections = create_sections(source, headings)

    tasks = {}
    solutions = {}

    for section in sections:

        number = section["number"]

        if section["type"] == "task":
            tasks[number] = section

        elif section["type"] == "solution":
            # Drugie wystąpienie jest rozwiązaniem.
            # Gdyby było trzecie, zachowujemy ostatnie.
            solutions[number] = section

    print()
    print(f"📝 Zadań: {len(tasks)}")
    print(f"📖 Rozwiązań: {len(solutions)}")

    base_name = os.path.splitext(filename)[0]

    output_dir = os.path.join(
        os.path.dirname(input_pdf),
        base_name + OUTPUT_SUFFIX
    )

    os.makedirs(output_dir, exist_ok=True)

    all_numbers = sorted(
        set(tasks.keys()) | set(solutions.keys()),
        key=sort_key
    )

    created = 0

    print()
    print("=" * 70)
    print(" TWORZENIE PLIKÓW")
    print("=" * 70)

    for number in all_numbers:

        print()
        print(f"▶ ZADANIE {number}")

        if number not in tasks:
            print("   ⚠ Brak pierwszego wystąpienia (treści zadania).")
            continue

        if number not in solutions:
            print("   ⚠ Brak drugiego wystąpienia (rozwiązania).")
            continue

        task = tasks[number]
        solution = solutions[number]

        output_file = os.path.join(
            output_dir,
            f"{base_name}-{number}.pdf"
        )

        print(
            f"   Zadanie:      str. "
            f"{task['start_page'] + 1} → {task['end_page'] + 1}"
        )

        print(
            f"   Rozwiązanie:  str. "
            f"{solution['start_page'] + 1} → {solution['end_page'] + 1}"
        )

        output = fitz.open()

        try:

            add_section_to_pdf(
                source,
                output,
                task
            )

            add_section_to_pdf(
                source,
                output,
                solution
            )

            if len(output) == 0:
                print("   ❌ PDF jest pusty.")
                output.close()
                continue

            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception as e:
                    print(f"   ❌ Nie można nadpisać pliku: {e}")
                    output.close()
                    continue

            output.save(
                output_file,
                garbage=4,
                deflate=True
            )

            output.close()

            print(
                f"   ✅ UTWORZONO: "
                f"{os.path.basename(output_file)}"
            )

            created += 1

        except Exception as e:

            print(f"   ❌ Błąd: {e}")
            traceback.print_exc()

            try:
                output.close()
            except Exception:
                pass

    source.close()

    print()
    print("-" * 70)
    print(f"✅ Zakończono: {filename}")
    print(f"📑 Utworzono: {created} plików")
    print(f"📁 Wyniki: {output_dir}")
    print("-" * 70)

    return created


def main():

    print()
    print("=" * 70)
    print(" DZIELENIE 53wst.pdf + 54wst.pdf")
    print("=" * 70)

    script_folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    # Domyślnie folder, w którym jest skrypt.
    # Można też podać folder jako argument.
    if len(sys.argv) > 1:
        input_dir = os.path.abspath(sys.argv[1])
    else:
        input_dir = script_folder

    if not os.path.isdir(input_dir):
        print(f"❌ Folder nie istnieje: {input_dir}")
        return

    found = []

    for filename in sorted(FILES):
        path = os.path.join(input_dir, filename)

        if os.path.isfile(path):
            found.append(path)
        else:
            print(f"⚠ Brak pliku: {filename}")

    if not found:
        print("❌ Nie znaleziono 53wst.pdf ani 54wst.pdf.")
        return

    print()
    print("📄 Do przetworzenia:")

    for path in found:
        print(f"   - {os.path.basename(path)}")

    total = 0

    for path in found:
        try:
            total += process_pdf(path)
        except Exception as e:
            print()
            print(
                f"❌ KRYTYCZNY BŁĄD dla "
                f"{os.path.basename(path)}: {e}"
            )
            traceback.print_exc()

    print()
    print("=" * 70)
    print(" GOTOWE")
    print("=" * 70)
    print(f"📑 Łącznie utworzonych plików: {total}")
    print()


if __name__ == "__main__":
    main()
