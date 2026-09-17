
import pymupdf as fitz
import re
import os
import sys
import traceback


# ============================================================
# USTAWIENIA
# ============================================================

OUTPUT_SUFFIX = "_podzielone"


# ============================================================
# REGEX NAGŁÓWKÓW
# ============================================================

# Przykłady:
# ZADANIE 1
# ZADANIE 12
# ZADANIE 5B
# ZADANIE B5
# ZADANIE A12

TASK_RE = re.compile(
    r"^\s*ZADANIE\s+([AB]?\d+[AB]?)\b",
    re.IGNORECASE
)
FILES_SKIP_CONTENT_CHECK = {
            "56wst-A7.pdf",
            "69wst-A4.pdf",
            "66wst-B4.pdf",
            "60i-5.pdf",
            "65wst-a5.pdf"
            
        }
# Przykłady:
# ROZWIĄZANIE ZADANIA 1
# ROZWIĄZANIE ZADANIA 5B
# ROZWIĄZANIE ZADANIA A5

SOLUTION_RE = re.compile(
    r"^\s*ROZWIĄZANI[AE]\s+ZADANIA\s+([AB]?\d+[AB]?)\b",
    re.IGNORECASE
)


# Dodatkowe nagłówki

TOPICS_RE = re.compile(
    r"^\s*(?:"
    r"TEMATYKA\s+DO\s+SAMODZIELNEGO\s+OPRACOWANIA"
    r"|CHROMATOGRAFIA\s+JONOWA"
    r"|MIARECZKOWA\s+ANALIZA\s+ILOŚCIOWA"
    r"|SPEKTROMETRIA\s+MAS"
    r"|punktacja:\s+wszystkie"
    r"|czas\s+trwania\s+zawodów"
    r"|rozwiązania\s+zadań\s+etapu"
    r"|autorami"
    r"|CZĘŚĆ\s+B\s+–\s+ZADANIA\s+FAKULTATYWNE"
    r"|Ocenianie\s+zadań:"
    r"|UWAGA:\s+ZAWODNICY\s+PRZYGOTOWUJĄCY"
    r"|PUNKTACJA:\s+za\s+każde"
    r"|uwaga:\s+wartości\s+mas"
    r"|Ocenianie\s+zadań:"
    r"|PUNKTACJA:\s+łącznie"
    r"|Rozwiązania\s+zadań\s+etapu\s+wstępnego"
    r"|Czas\s+trwania\s+zawodów:"
    r"|za\s+poprawne\s+wykonanie\s+poleceń"
    r"|CZĘ B\s+–\s+ZADANIA" 
  
    r")\b",
    re.IGNORECASE
)

# ============================================================
# NORMALIZACJA NUMERU ZADANIA
# ============================================================

def normalize_task_number(value):
    """
    Normalizuje numer zadania.

    5B  -> B5
    11A -> A11
    A5  -> A5
    B12 -> B12
    7   -> 7
    """

    value = value.strip().upper()

    match = re.fullmatch(
        r"(\d+)([AB])",
        value
    )

    if match:

        number = match.group(1)
        letter = match.group(2)

        return f"{letter}{number}"

    return value


# ============================================================
# CZYSZCZENIE LINII
# ============================================================

def clean_line(text):

    return (
        text
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .strip()
    )


# ============================================================
# SPRAWDZANIE, CZY FRAGMENT ZAWIERA TREŚĆ
# ============================================================

def has_content(page, rect):

    try:

        blocks = page.get_text(
            "blocks",
            clip=rect
        )

    except Exception:

        return False

    for block in blocks:

        if len(block) < 5:
            continue

        text = block[4].strip()

        if text:
            return True

    return False


# ============================================================
# SZUKANIE NAGŁÓWKÓW NA JEDNEJ STRONIE
# ============================================================

def find_heading_on_page(page):

    headings = []

    try:

        data = page.get_text("dict")

    except Exception as e:

        print(
            f"      ⚠ Błąd odczytu strony: {e}"
        )

        return headings

    for block in data.get("blocks", []):

        # Pomijamy obrazki

        if "lines" not in block:
            continue

        for line in block["lines"]:

            line_text = "".join(
                span.get("text", "")
                for span in line.get("spans", [])
            )

            line_text = clean_line(
                line_text
            )

            if not line_text:
                continue

            rect = fitz.Rect(
                line["bbox"]
            )

            # =================================================
            # TEMATYKA
            # =================================================

            match = TOPICS_RE.match(
                line_text
            )

            if match:

                headings.append({
                    "type": "topics",
                    "number": None,
                    "rect": rect,
                    "text": line_text
                })

                continue

            # =================================================
            # ROZWIĄZANIE
            # =================================================

            match = SOLUTION_RE.match(
                line_text
            )

            if match:

                headings.append({
                    "type": "solution",
                    "number": normalize_task_number(
                        match.group(1)
                    ),
                    "rect": rect,
                    "text": line_text
                })

                continue

            # =================================================
            # ZADANIE
            # =================================================

            match = TASK_RE.match(
                line_text
            )

            if match:

                headings.append({
                    "type": "task",
                    "number": normalize_task_number(
                        match.group(1)
                    ),
                    "rect": rect,
                    "text": line_text
                })

    # Sortowanie od góry do dołu

    headings.sort(
        key=lambda x: x["rect"].y0
    )

    return headings


# ============================================================
# SZUKANIE WSZYSTKICH NAGŁÓWKÓW W PDF
# ============================================================

def find_all_headings(doc):

    headings = []

    for page_number in range(len(doc)):

        page = doc[page_number]

        page_headings = find_heading_on_page(
            page
        )

        for heading in page_headings:

            heading["page"] = page_number

            headings.append(
                heading
            )

    return headings


# ============================================================
# TWORZENIE SEKCJI
# ============================================================

def create_sections(doc, headings):

    sections = []

    for i, heading in enumerate(headings):

        start_page = heading["page"]
        start_y = heading["rect"].y0

        # ====================================================
        # KONIEC SEKCJI
        # ====================================================

        if i + 1 < len(headings):

            next_heading = headings[i + 1]

            end_page = next_heading["page"]
            end_y = next_heading["rect"].y0

        else:

            end_page = len(doc) - 1

            end_y = doc[
                end_page
            ].rect.height

        sections.append({

            "type": heading["type"],

            "number": heading["number"],

            "start_page": start_page,

            "start_y": start_y,

            "end_page": end_page,

            "end_y": end_y,

            "heading": heading["text"]

        })

    return sections


# ============================================================
# DODAWANIE FRAGMENTU PDF DO NOWEGO PDF
# ============================================================

def add_section_to_pdf(
    source,
    output,
    section,
    skip_last_page=False,
    skip_content_check=False
):

    start_page = section["start_page"]
    end_page = section["end_page"]

    start_y = section["start_y"]
    end_y = section["end_y"]

    # =========================================================
    # NAJPIERW USTALAMY STRONY, KTÓRE NALEŻY PRZETWORZYĆ
    # =========================================================

    pages = list(
        range(
            start_page,
            end_page + 1
        )
    )

    # =========================================================
    # JEŻELI MAMY USUNĄĆ OSTATNIĄ STRONĘ
    #
    # Usuwamy ją z listy RAZ.
    # Dzięki temu żadna strona nie może zostać dodana
    # drugi raz przez kolejne pętle.
    # =========================================================

    if skip_last_page and len(pages) >= 2:

        pages = pages[:-1]

    # Jeżeli po wszystkim nic nie zostało

    if not pages:

        return

    # =========================================================
    # PRZECHODZIMY PO KAŻDEJ STRONIE DOKŁADNIE RAZ
    # =========================================================

    for index, page_number in enumerate(pages):

        source_page = source[page_number]

        width = source_page.rect.width
        height = source_page.rect.height

        # =====================================================
        # PIERWSZA STRONA SEKCJI
        # =====================================================

        if page_number == start_page:

            # Jeżeli sekcja zaczyna się i kończy
            # na tej samej stronie

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

        # =====================================================
        # OSTATNIA STRONA SEKCJI
        # =====================================================

        elif page_number == end_page:

            crop = fitz.Rect(
                0,
                0,
                width,
                end_y
            )

        # =====================================================
        # STRONA ŚRODKOWA
        # =====================================================

        else:

            crop = fitz.Rect(
                0,
                0,
                width,
                height
            )

        # =====================================================
        # SPRAWDZENIE WYSOKOŚCI
        # =====================================================

        # =====================================================
        # SPRAWDZENIE, CZY JEST TREŚĆ
        # =====================================================
        if not skip_content_check:
            if not has_content(source_page, crop):
                continue
        # =====================================================
        #

        # =====================================================
        # UTWORZENIE JEDNEJ STRONY WYNIKOWEJ
        # =====================================================

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

# ============================================================
# PRZETWARZANIE JEDNEGO PDF
# ============================================================

def process_pdf(input_pdf):

    filename = os.path.basename(
        input_pdf
    )

    print()
    print("=" * 70)
    print(f" PRZETWARZANIE: {filename}")
    print("=" * 70)

    # ========================================================
    # OTWARCIE PDF
    # ========================================================

    try:

        source = fitz.open(
            input_pdf
        )

    except Exception as e:

        print()
        print("❌ NIE MOŻNA OTWORZYĆ PDF:")
        print(f"   {e}")

        return 0

    print()
    print(
        f"📄 Plik: {input_pdf}"
    )

    print(
        f"📑 Liczba stron: {len(source)}"
    )

    # ========================================================
    # SZUKANIE NAGŁÓWKÓW
    # ========================================================

    print()
    print(
        "🔎 Szukanie nagłówków..."
    )

    headings = find_all_headings(
        source
    )

    if not headings:

        print()
        print(
            "❌ NIE ZNALEZIONO ŻADNYCH NAGŁÓWKÓW!"
        )

        print()
        print(
            "Sprawdź, czy PDF zawiera tekst:"
        )

        print(
            "   ZADANIE 1"
        )

        print(
            "   ROZWIĄZANIE ZADANIA 1"
        )

        source.close()

        return 0

    # ========================================================
    # WYPISANIE NAGŁÓWKÓW
    # ========================================================

    print()
    print(
        f"✅ Znaleziono nagłówków: {len(headings)}"
    )

    print()

    for heading in headings:

        page = (
            heading["page"] + 1
        )

        if heading["number"] is None:

            number_text = ""

        else:

            number_text = str(
                heading["number"]
            )

        print(
            f"   {heading['type']:10s} "
            f"{number_text:>5}  "
            f"strona {page:>3}  "
            f"Y={heading['rect'].y0:>7.1f}  "
            f"{heading['text']}"
        )

    # ========================================================
    # TWORZENIE SEKCJI
    # ========================================================

    sections = create_sections(
        source,
        headings
    )

    # ========================================================
    # ZADANIA
    # ========================================================

    tasks = {}

    for section in sections:

        if section["type"] != "task":
            continue

        number = section["number"]

        # Gdyby ten sam numer wystąpił ponownie,
        # zachowujemy ostatnie wystąpienie.

        tasks[number] = section

    # ========================================================
    # ROZWIĄZANIA
    # ========================================================

    solutions = {}

    for section in sections:

        if section["type"] != "solution":
            continue

        number = section["number"]

        solutions[number] = section

    # ========================================================
    # INFORMACJA O ZADANIACH
    # ========================================================

    print()
    print(
        f"📝 Zadań: {len(tasks)}"
    )

    print(
        f"📖 Rozwiązań: {len(solutions)}"
    )

    # ========================================================
    # FOLDER WYJŚCIOWY
    # ========================================================

    base_name = os.path.splitext(
        os.path.basename(input_pdf)
    )[0]

    output_dir = os.path.join(
        os.path.dirname(input_pdf),
        base_name + OUTPUT_SUFFIX
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    print()
    print(
        f"📁 Folder wynikowy:"
    )

    print(
        f"   {output_dir}"
    )

    # ========================================================
    # LISTA NUMERÓW
    # ========================================================

    all_numbers = (
        set(tasks.keys())
        |
        set(solutions.keys())
    )

    # ========================================================
    # SORTOWANIE NUMERÓW
    # ========================================================

    def sort_key(number):

        match = re.search(
            r"(\d+)",
            str(number)
        )

        if match:

            numeric = int(
                match.group(1)
            )

        else:

            numeric = 999999

        number_string = str(
            number
        )

        if number_string.startswith("A"):

            group = 1

        elif number_string.startswith("B"):

            group = 2

        else:

            group = 0

        return (
            group,
            numeric
        )

    all_numbers = sorted(
        all_numbers,
        key=sort_key
    )

    # ========================================================
    # OSTATNIE ZADANIA W GRUPACH
    # ========================================================

    normal_numbers = [
        number
        for number in tasks.keys()
        if not str(number).startswith("A")
        and not str(number).startswith("B")
    ]

    a_numbers = [
        number
        for number in tasks.keys()
        if str(number).startswith("A")
    ]

    b_numbers = [
        number
        for number in tasks.keys()
        if str(number).startswith("B")
    ]

    last_normal_task = (
        max(
            normal_numbers,
            key=sort_key
        )
        if normal_numbers
        else None
    )

    last_a_task = (
        max(
            a_numbers,
            key=sort_key
        )
        if a_numbers
        else None
    )

    last_b_task = (
        max(
            b_numbers,
            key=sort_key
        )
        if b_numbers
        else None
    )

    # ========================================================
    # TWORZENIE PLIKÓW
    # ========================================================

    print()
    print("=" * 70)
    print(" TWORZENIE PLIKÓW")
    print("=" * 70)

    created = 0

    # ========================================================
    # KAŻDE ZADANIE
    # ========================================================

    for number in all_numbers:

        print()
        print(
            f"▶ ZADANIE {number}"
        )

        # ----------------------------------------------------
        # Brak treści zadania
        # ----------------------------------------------------

        if number not in tasks:

            print(
                "   ⚠ Brak treści zadania."
            )

            continue

        # ----------------------------------------------------
        # Brak rozwiązania
        # ----------------------------------------------------

        if number not in solutions:

            print(
                "   ⚠ Brak rozwiązania."
            )

            continue

        task = tasks[number]

        solution = solutions[number]

        # ----------------------------------------------------
        # Nazwa pliku
        # ----------------------------------------------------

        output_file = os.path.join(
            output_dir,
            f"{base_name}-{number}.pdf"
        )

        print(
            f"   Zadanie:"
        )

        print(
            f"      str. {task['start_page'] + 1}"
            f" → "
            f"{task['end_page'] + 1}"
        )

        print(
            f"   Rozwiązanie:"
        )

        print(
            f"      str. {solution['start_page'] + 1}"
            f" → "
            f"{solution['end_page'] + 1}"
        )

        # ====================================================
        # NOWY PDF
        # ====================================================

        output = fitz.open()

        try:

            # =================================================
            # USUWANIE OSTATNIEJ STRONY ZADANIA
            # =================================================

            # =================================================

# Liczymy rzeczywistą liczbę stron zadania.
#
# Przykład:
# start_page = 5
# end_page   = 7
#
# Zadanie zajmuje strony:
# 5, 6, 7
#
# czyli 3 strony.

            task_page_count = (
                task["end_page"]
                - task["start_page"]
                + 1
)

# Jeżeli zadanie ma minimum 2 strony,
# usuwamy jego ostatnią stronę.
#
# Jeżeli ma tylko 1 stronę,
# niczego nie usuwamy.
 
            output_files_not_to_trim = {
                "61iiit-5.pdf",
                "62iiit-5.pdf",
                "63iiit-5.pdf",
                "64iiit-5.pdf",
                "65iiit-5.pdf",
                "62iiit-5.pdf",
                "60i-5.pdf",
                "65wst-a5.pdf",
                "66wst-b4.pdf",
                "69wst-a4.pdf",
                "56wst-a7.pdf",

            }

# Tutaj wpisujesz pliki, dla których ZAWSZE ma być usuwana ostatnia strona
            output_files_to_trim = {
                "67iii-3.pdf",
                "67ii-3.pdf",
                "67i-2.pdf"
            }

            output_filename = os.path.basename(output_file)

            skip_content_check = (
                output_filename in FILES_SKIP_CONTENT_CHECK
            )

            print(
                f"   {output_filename}: "
                f"skip_content_check={skip_content_check}"
            )
            skip_task_last_page = (
                task_page_count >= 3
                and (
                    number == last_normal_task
                    or number == last_a_task
                    or number == last_b_task
                )
                and output_filename not in output_files_not_to_trim
            )

# Dodatkowe pliki, dla których usuwamy ostatnią stronę niezależnie
            if output_filename in output_files_to_trim:
                skip_task_last_page = True 

            # =================================================
            # DODAJEMY ZADANIE
            # =================================================

            add_section_to_pdf(
                source,
                output,
                task,
                skip_last_page=skip_task_last_page,
                skip_content_check=skip_content_check
            )

            # =================================================
            # USUWANIE OSTATNIEJ STRONY ROZWIĄZANIA
            # =================================================

            skip_solution_last_page = (
                (
                    (
                        output_filename.lower() not in { "55wst-a9.pdf","65wst-a5.pdf","56wst-a7.pdf"}

                        and
                        (
                            number == last_a_task
                            or filename in [
                                "67i-2.pdf",
                                "67ii-3.pdf",
                                "67iii-3.pdf",
                              ]
                        )
                    )
                    
                )
            )
            # =================================================
            # DODAJEMY ROZWIĄZANIE
            # =================================================

            add_section_to_pdf(
                source,
                output,
                solution,
                skip_last_page=skip_solution_last_page,
                skip_content_check=skip_content_check
            )

            # =================================================
            # SPRAWDZENIE
            # =================================================

            if len(output) == 0:

                print(
                    "   ❌ PDF jest pusty."
                )

                output.close()

                continue

            # =================================================
            # JEŻELI PLIK JUŻ ISTNIEJE
            # =================================================

            if os.path.exists(
                output_file
            ):

                try:

                    os.remove(
                        output_file
                    )

                except Exception as e:

                    print(
                        "   ❌ Nie można nadpisać pliku:"
                    )

                    print(
                        f"      {e}"
                    )

                    output.close()

                    continue

            # =================================================
            # ZAPIS
            # =================================================

            output.save(
                output_file,
                garbage=4,
                deflate=True
            )

            output.close()

            print(
                f"   ✅ UTWORZONO:"
            )

            print(
                f"      {os.path.basename(output_file)}"
            )

            created += 1

        except Exception as e:

            print()
            print(
                "   ❌ BŁĄD PODCZAS TWORZENIA:"
            )

            print(
                f"      {e}"
            )

            print()

            traceback.print_exc()

            try:
                output.close()
            except:
                pass

    # ========================================================
    # ZAMKNIĘCIE PDF ŹRÓDŁOWEGO
    # ========================================================

    source.close()

    # ========================================================
    # PODSUMOWANIE PDF
    # ========================================================

    print()
    print("-" * 70)

    print(
        f"✅ Zakończono: {filename}"
    )

    print(
        f"📑 Utworzono: {created} plików"
    )

    print(
        f"📁 Wyniki: {output_dir}"
    )

    print("-" * 70)

    return created


# ============================================================
# ZNAJDOWANIE WSZYSTKICH PDF-ÓW
# ============================================================

def find_pdf_files(folder):

    pdf_files = []

    try:

        filenames = os.listdir(
            folder
        )

    except Exception as e:

        print()
        print(
            "❌ Nie można odczytać folderu:"
        )

        print(
            f"   {e}"
        )

        return []

    for filename in filenames:

        # Pomijamy pliki tymczasowe

        if filename.startswith("~"):
            continue

        # Tylko PDF

        if not filename.lower().endswith(".pdf"):
            continue

        full_path = os.path.join(
            folder,
            filename
        )

        # Tylko rzeczywiste pliki

        if not os.path.isfile(
            full_path
        ):
            continue

        pdf_files.append(
            full_path
        )

    pdf_files.sort(
        key=lambda x: os.path.basename(
            x
        ).lower()
    )

    return pdf_files


# ============================================================
# GŁÓWNA FUNKCJA
# ============================================================

def main():

    print()
    print("=" * 70)
    print(" MASOWE DZIELENIE PDF")
    print("=" * 70)

    # ========================================================
    # USTALENIE FOLDERU
    # ========================================================

    # Najważniejsze:
    #
    # Skrypt bierze PDF-y z folderu,
    # w którym znajduje się plik .py.
    #
    # Dzięki temu nie trzeba wpisywać żadnych ścieżek.

    script_folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    print()
    print(
        "📁 Folder skryptu:"
    )

    print(
        f"   {script_folder}"
    )

    # ========================================================
    # JEŻELI PODANO FOLDER JAKO ARGUMENT
    # ========================================================

    if len(sys.argv) > 1:

        input_dir = os.path.abspath(
            sys.argv[1]
        )

        print()
        print(
            "📁 Używam folderu podanego jako argument:"
        )

        print(
            f"   {input_dir}"
        )

    else:

        input_dir = script_folder

    # ========================================================
    # SPRAWDZENIE FOLDERU
    # ========================================================

    if not os.path.isdir(
        input_dir
    ):

        print()
        print(
            "❌ FOLDER NIE ISTNIEJE:"
        )

        print(
            f"   {input_dir}"
        )

        input(
            "\nNaciśnij ENTER..."
        )

        return

    # ========================================================
    # SZUKANIE PDF
    # ========================================================

    print()
    print(
        "🔎 Szukanie plików PDF..."
    )

    pdf_files = find_pdf_files(
        input_dir
    )

    # ========================================================
    # BRAK PDF
    # ========================================================

    if not pdf_files:

        print()
        print(
            "❌ NIE ZNALEZIONO ŻADNEGO PDF-A!"
        )

        print()
        print(
            "W tym folderze:"
        )

        print(
            f"   {input_dir}"
        )

        print()
        print(
            "Umieść pliki PDF w tym samym folderze"
        )

        print(
            "co skrypt i uruchom go ponownie."
        )

        input(
            "\nNaciśnij ENTER..."
        )

        return

    # ========================================================
    # LISTA PDF
    # ========================================================

    print()
    print(
        f"✅ ZNALEZIONO PDF-ÓW: {len(pdf_files)}"
    )

    print()

    for i, pdf_file in enumerate(
        pdf_files,
        start=1
    ):

        print(
            f"   {i:>3}. "
            f"{os.path.basename(pdf_file)}"
        )

    # ========================================================
    # POTWIERDZENIE STARTU
    # ========================================================

    print()
    print(
        "=" * 70
    )

    print(
        " START PRZETWARZANIA"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # STATYSTYKI
    # ========================================================

    total_created = 0

    successful_files = 0

    failed_files = 0

    # ========================================================
    # PRZETWARZANIE KAŻDEGO PDF
    # ========================================================

    for index, pdf_file in enumerate(
        pdf_files,
        start=1
    ):

        print()
        print()
        print(
            "#" * 70
        )

        print(
            f"# PLIK {index}/{len(pdf_files)}"
        )

        print(
            f"# {os.path.basename(pdf_file)}"
        )

        print(
            "#" * 70
        )

        try:

            created = process_pdf(
                pdf_file
            )

            total_created += created

            if created > 0:

                successful_files += 1

            else:

                failed_files += 1

        except Exception as e:

            print()
            print(
                "❌ KRYTYCZNY BŁĄD DLA TEGO PLIKU:"
            )

            print(
                f"   {e}"
            )

            print()

            traceback.print_exc()

            failed_files += 1

            # WAŻNE:
            # Nie zatrzymujemy całego programu.
            # Przechodzimy do następnego PDF.

    # ========================================================
    # KOŃCOWE PODSUMOWANIE
    # ========================================================

    print()
    print()
    print("=" * 70)
    print(" GOTOWE")
    print("=" * 70)

    print()

    print(
        f"📄 Znalezionych PDF-ów: "
        f"{len(pdf_files)}"
    )

    print(
        f"✅ PDF-ów z utworzonymi wynikami: "
        f"{successful_files}"
    )

    print(
        f"❌ PDF-ów bez wyników / z błędem: "
        f"{failed_files}"
    )

    print(
        f"📑 Łącznie utworzonych plików: "
        f"{total_created}"
    )

    print()

    print(
        "📁 Folder, w którym znajdują się wyniki:"
    )

    print(
        f"   {input_dir}"
    )

    print()

    print(
        "Każdy PDF ma własny folder:"
    )

    print(
        f"   NAZWA_PLIKU{OUTPUT_SUFFIX}"
    )

    print()
    print("=" * 70)

    # ========================================================
    # NIE ZAMYKAJ OKNA OD RAZU
    # ========================================================

    input(
        "\nNaciśnij ENTER, aby zakończyć..."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
