
import pymupdf as fitz
import re
import os
import sys
import traceback
import pytesseract
from PIL import Image
import io


# ============================================================
# USTAWIENIA
# ============================================================

OUTPUT_SUFFIX = "_podzielone"
A4_HEIGHT = 841.89  # wysokość A4 w punktach PDF


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
    r"^\s*ZADANIE\s+([AB]?\s*\d+\s*[AB]?)\b",
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
    r"^\s*ROZWIĄZANI[AE]\s+ZADANIA\s+([AB]?\s*\d+\s*[AB]?)\b",
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

    value = re.sub(r"\s+", "", value.strip().upper())

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

    # ============================================================
    # 1. NORMALNE NAGŁÓWKI
    # ============================================================

    try:
        data = page.get_text("dict")
    except Exception as e:
        print(
            f"      ⚠ Błąd odczytu strony: {e}"
        )
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

            rect = fitz.Rect(line["bbox"])

            # ====================================================
            # TEMATYKA
            # ====================================================

            match = TOPICS_RE.match(line_text)

            if match:
                headings.append({
                    "type": "topics",
                    "number": None,
                    "rect": rect,
                    "text": line_text
                })
                continue

            # ====================================================
            # ROZWIĄZANIE
            # ====================================================

            match = SOLUTION_RE.match(line_text)

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

            # ====================================================
            # ZADANIE
            # ====================================================

            match = TASK_RE.match(line_text)

            if match:
                headings.append({
                    "type": "task",
                    "number": normalize_task_number(
                        match.group(1)
                    ),
                    "rect": rect,
                    "text": line_text
                })

    # ============================================================
    # 2. SZUKANIE USZKODZONYCH NAGŁÓWKÓW
    #
    # Przykład z 54i.pdf:
    #
    # ROZWIĄZ   ZANIE   ZADAN   NIA   5
    #
    # Każdy fragment może być osobnym "wordem".
    # ============================================================

    try:
        words = page.get_text("words")
    except Exception:
        words = []

    if words:

        # --------------------------------------------------------
        # Grupujemy słowa w linie.
        #
        # Nie sortujemy globalnie po Y.
        # Najpierw tworzymy grupy o podobnym położeniu pionowym,
        # a potem każdą grupę sortujemy po X.
        # --------------------------------------------------------

        unused = list(words)
        lines = []

        while unused:

            word = unused.pop(0)

            x0, y0, x1, y1, text = word[:5]

            line = [word]

            remaining = []

            for candidate in unused:

                cx0, cy0, cx1, cy1, ctext = candidate[:5]

                # Środek wysokości słowa
                word_mid_y = (y0 + y1) / 2
                candidate_mid_y = (cy0 + cy1) / 2

                # Jeżeli są mniej więcej na tej samej wysokości,
                # traktujemy je jako jedną linię.
                if abs(
                    candidate_mid_y - word_mid_y
                ) <= 7:

                    line.append(candidate)

                else:
                    remaining.append(candidate)

            unused = remaining

            # Sortowanie fragmentów w linii od lewej do prawej
            line.sort(
                key=lambda w: w[0]
            )

            lines.append(line)

        # --------------------------------------------------------
        # Sprawdzamy każdą zrekonstruowaną linię
        # --------------------------------------------------------

        for line in lines:

            if not line:
                continue

            joined = "".join(
                word[4].strip().upper()
                for word in line
            )

            # ----------------------------------------------------
            # Przykładowe:
            #
            # ROZWIĄZZANIEZADANNIA5
            #
            # albo:
            #
            # ROZWIĄZ ZANIE ZADAN NIA 5
            # ----------------------------------------------------

            solution_match = re.search(
                r"ROZWIĄZ.*?ZANIE.*?ZADAN.*?NIA.*?(\d+[AB]?)\b",
                joined, re.IGNORECASE
            )
            task_match = re.search(
                r"(?:ZADANI[EA]|ADANI[EA])\s*(\d+[AB]?)\b",
                joined, re.IGNORECASE
            )
            if not solution_match and not task_match:
                continue
            if solution_match:
                heading_type = "solution"
                number = normalize_task_number(solution_match.group(1))
            else:
                heading_type = "task"
                number = normalize_task_number(task_match.group(1))

            # ----------------------------------------------------
            # Prostokąt obejmujący cały nagłówek
            # ----------------------------------------------------

            rect = fitz.Rect(
                min(word[0] for word in line),
                min(word[1] for word in line),
                max(word[2] for word in line),
                max(word[3] for word in line)
            )

            # ----------------------------------------------------
            # Nie dodajemy duplikatu, jeżeli normalny parser
            # już znalazł ten nagłówek.
            # ----------------------------------------------------

            duplicate = False

            for existing in headings:

                if existing["type"] != heading_type:
                    continue

                if existing["number"] != number:
                    continue

                # Ten sam fragment strony
                if (
                    abs(
                        existing["rect"].y0 - rect.y0
                    ) < 15
                    and
                    abs(
                        existing["rect"].x0 - rect.x0
                    ) < 30
                ):
                    duplicate = True
                    break

            if not duplicate:

                headings.append({
                    "type": heading_type,
                    "number": number,
                    "rect": rect,
                    "text": (
                        f"ZADANIE {number}" if heading_type == "task"
                        else f"ROZWIĄZANIE ZADANIA {number}"
                    )
                })

    # ============================================================
    # 3. SORTOWANIE
    # ============================================================

    headings.sort(
        key=lambda x: (
            x["rect"].y0,
            x["rect"].x0
        )
    )

    return headings

# ============================================================
# SZUKANIE WSZYSTKICH NAGŁÓWKÓW W PDF
# ============================================================

def find_all_headings(doc):
    """
    Szuka nagłówków we wszystkich stronach.

    Ważne dla PDF-ów 53wst/54wst:
    po nagłówku „Rozwiązania zadań etapu wstępnego”
    rozwiązania są oznaczone ponownie jako „Zadanie 1A”,
    „Zadanie 2A” itd., zamiast „ROZWIĄZANIE ZADANIA 1A”.
    Dlatego po wejściu w sekcję rozwiązań kolejne nagłówki
    „Zadanie ...” klasyfikujemy jako rozwiązania.
    """

    headings = []
    solution_mode = False

    for page_number in range(len(doc)):
        page = doc[page_number]
        page_headings = find_heading_on_page(page)

        for heading in page_headings:
            # Ten nagłówek rozpoczyna sekcję rozwiązań.
            if heading["type"] == "topics":
                text = clean_line(heading["text"])
                if re.search(
                    r"ROZWIĄZANIA\s+ZADAŃ\s+ETAPU\s+WSTĘPNEGO",
                    text,
                    re.IGNORECASE
                ):
                    solution_mode = True
                heading["page"] = page_number
                headings.append(heading)
                continue

            # Niektóre PDF-y mają prawidłowy nagłówek
            # „ROZWIĄZANIE ZADANIA ...” — zachowujemy go.
            if heading["type"] == "solution":
                solution_mode = True

            # W PDF-ach 53wst/54wst rozwiązania mają postać
            # „Zadanie ...” po wejściu w sekcję rozwiązań.
            elif heading["type"] == "task" and solution_mode:
                heading["type"] = "solution"

            heading["page"] = page_number
            headings.append(heading)

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

A4_HEIGHT = 841.89  # wysokość strony A4 w punktach PDF


def add_section_to_pdf(
    source,
    output,
    section,
    skip_last_page=False,
    skip_content_check=False,
    expand_single_page_to_a4=False
):
    start_page = section["start_page"]
    end_page = section["end_page"]

    start_y = section["start_y"]
    end_y = section["end_y"]

    pages = list(range(start_page, end_page + 1))

    if skip_last_page and len(pages) >= 2:
        pages = pages[:-1]

    if not pages:
        return

    for index, page_number in enumerate(pages):
        source_page = source[page_number]

        width = source_page.rect.width
        height = source_page.rect.height

        if page_number == start_page:
            if start_page == end_page:
                crop = fitz.Rect(0, start_y, width, end_y)
            else:
                crop = fitz.Rect(0, start_y, width, height)

        elif page_number == end_page:
            crop = fitz.Rect(0, 0, width, end_y)

        else:
            crop = fitz.Rect(0, 0, width, height)

        if not skip_content_check:
            if not has_content(source_page, crop):
                continue

        # Rozszerzamy wyłącznie jedno-stronicowe zadania.
        # Treść pozostaje w oryginalnym rozmiarze i na górze strony.
        if (
            expand_single_page_to_a4
            and len(pages) == 1
            and crop.height < A4_HEIGHT
        ):
            new_page = output.new_page(
                width=crop.width,
                height=A4_HEIGHT
            )

            new_page.show_pdf_page(
                fitz.Rect(0, 0, crop.width, crop.height),
                source,
                page_number,
                clip=crop
            )

        else:
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
# DODAWANIE FRAGMENTU PDF DO NOWEGO PDF
# ============================================================

def add_section_to_pdf(
    source,
    output,
    section,
    skip_last_page=False,
    skip_content_check=False,
    expand_single_page_to_a4=False 
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
        single_page = len(crop) == 1

    for page_number, crop in valid_crops:
        source_page = source[page_number]

        if (
            expand_single_page_to_a4
            and single_page
            and crop.height < A4_HEIGHT
        ):
            new_page = output.new_page(
                width=crop.width,
                height=A4_HEIGHT
            )

            # Treść pozostaje u góry i zachowuje oryginalny rozmiar.
            new_page.show_pdf_page(
                fitz.Rect(0, 0, crop.width, crop.height),
                source,
                page_number,
                clip=crop
            )

            print(
                f"      📄 Rozszerzono stronę do A4 "
                f"(wysokość {A4_HEIGHT:.2f} pkt)"
            )

        else:
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
# SPECJALNY TRYB DLA 52WST - SKAN DWÓCH STRON NA JEDNEJ STRONIE
# ============================================================

SCANNED_52_EXPECTED = [
    *(f"A{i}" for i in range(1, 10)),
    *(f"B{i}" for i in range(1, 11)),
]

# W 52wst nagłówki rozwiązań są podkreślone. Po obrocie skanu o 90°
# w lewo i rozcięciu na dwie strony ich położenia są stabilne. Używamy
# tych podkreśleń jako granic, zamiast OCR całej strony.
# Wartości są w punktach na logicznej stronie 421 x 595.
SCANNED_52_HEADINGS = {
    # fizyczna strona PDF: [(połówka, numer, początek nagłówka)]
    # Początek jest kilka punktów nad podkreśleniem, aby zachować cały nagłówek.
    10: [("L", "A1", 67), ("L", "A2", 333), ("L", "A3", 448)],
    11: [("L", "A4", 446), ("R", "A5", 376), ("R", "A6", 527)],
    12: [("L", "A7", 498), ("R", "A8", 306)],
    13: [("R", "A9", 374)],
    14: [("L", "B1", 475), ("R", "B2", 221)],
    15: [("L", "B3", 31), ("L", "B4", 471)],
    16: [("L", "B5", 294), ("R", "B6", 502)],
    17: [("L", "B7", 485), ("R", "B8", 257)],
    18: [("L", "B9", 341), ("R", "B10", 537)],
}


def build_scanned_52_document(source):
    """Tworzy logiczne strony z obróconego i rozciętego skanu 52wst."""
    logical = fitz.open()
    headings = []

    # Mapa: (fizyczna strona, połówka) -> logiczna strona.
    logical_map = {}

    for physical_page in range(9, len(source)):
        page = source[physical_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        image = image.rotate(90, expand=True)  # 90° w lewo
        w, h = image.size
        half = w // 2

        for side, x0 in (("L", 0), ("R", half)):
            crop = image.crop((x0, 0, x0 + half, h))
            lpno = len(logical)
            logical_map[(physical_page + 1, side)] = lpno
            lp = logical.new_page(width=421, height=595)
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=95, subsampling=0)
            lp.insert_image(lp.rect, stream=buf.getvalue())

    # Zamieniamy podane położenia podkreślonych nagłówków na sekcje.
    for physical_page, entries in SCANNED_52_HEADINGS.items():
        for side, number, y in entries:
            lpno = logical_map[(physical_page, side)]
            headings.append({
                "type": "solution",
                "number": number,
                "page": lpno,
                "rect": fitz.Rect(0, y, 421, y + 12),
                "text": f"ZADANIE {number}",
            })

    headings.sort(key=lambda x: (x["page"], x["rect"].y0))
    return logical, headings


def add_scanned_section_to_pdf(source, output, section):
    """Dodaje wycinek logicznej strony skanu 52wst."""
    sp = section["start_page"]
    ep = section["end_page"]
    sy = section["start_y"]
    ey = section["end_y"]
    for pno in range(sp, ep + 1):
        page = source[pno]
        if pno == sp and pno == ep:
            crop = fitz.Rect(0, sy, page.rect.width, ey)
        elif pno == sp:
            crop = fitz.Rect(0, sy, page.rect.width, page.rect.height)
        elif pno == ep:
            crop = fitz.Rect(0, 0, page.rect.width, ey)
        else:
            crop = page.rect
        if crop.height <= 2:
            continue
        np = output.new_page(width=crop.width, height=crop.height)
        np.show_pdf_page(np.rect, source, pno, clip=crop)


def process_scanned_52(input_pdf):
    """Przetwarza 52wst: zwykłe zadania + skanowane rozwiązania."""
    print("\n" + "=" * 70)
    print(" TRYB SKANOWANY 52WST")
    print("=" * 70)
    source = fitz.open(input_pdf)
    print(f"📄 Stron: {len(source)}")

    # Zadania z pierwszych 9 stron obsługujemy istniejącym parserem.
    normal_headings = []
    for pno in range(9):
        for h in find_heading_on_page(source[pno]):
            h["page"] = pno
            normal_headings.append(h)
    normal_headings.sort(key=lambda x: (x["page"], x["rect"].y0, x["rect"].x0))
    normal_sections = create_sections(source, normal_headings)
    tasks = {s["number"]: s for s in normal_sections if s["type"] == "task"}

    # W 52wst zadanie 10B kończy się na stronie 9; strona 10 zaczyna
    # już skan rozwiązań i nie należy do treści zadania.
    if "B10" in tasks:
        tasks["B10"]["end_page"] = 8
        tasks["B10"]["end_y"] = source[8].rect.height

    scanned, sol_headings = build_scanned_52_document(source)
    # Sekcje rozwiązań tworzymy tylko między nagłówkami rozwiązań.
    sol_sections = create_sections(scanned, sol_headings)
    solutions = {s["number"]: s for s in sol_sections if s["type"] == "solution"}

    print(f"📝 Zadań: {len(tasks)}")
    print(f"📖 Rozwiązań: {len(solutions)}")
    for s in sol_sections:
        print(f"   rozwiązanie {s['number']}: str. logiczna {s['start_page']+1} → {s['end_page']+1}, Y {s['start_y']:.1f} → {s['end_y']:.1f}")

    base_name = os.path.splitext(os.path.basename(input_pdf))[0]
    output_dir = os.path.join(os.path.dirname(input_pdf), base_name + OUTPUT_SUFFIX)
    os.makedirs(output_dir, exist_ok=True)

    created = 0
    for number in SCANNED_52_EXPECTED:
        if number not in tasks or number not in solutions:
            print(f"⚠ Brak zadania lub rozwiązania: {number}")
            continue
        outpath = os.path.join(output_dir, f"{base_name}-{number}.pdf")
        out = fitz.open()
        add_section_to_pdf(source, out, tasks[number], skip_content_check=True)
        add_scanned_section_to_pdf(scanned, out, solutions[number])
        if len(out):
            if os.path.exists(outpath):
                os.remove(outpath)
            out.save(outpath, garbage=4, deflate=True)
            created += 1
            print(f"✅ {os.path.basename(outpath)} ({len(out)} stron)")
        out.close()

    scanned.close()
    source.close()
    print(f"\nUtworzono: {created}")
    return created


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
        
            task_page_count = task["end_page"] - task["start_page"] + 1
            add_section_to_pdf(
                 source,
                 output,
                 task,
                 skip_last_page=skip_task_last_page,
                 skip_content_check=skip_content_check,
                  expand_single_page_to_a4=(task_page_count == 1)
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

            if os.path.basename(pdf_file).lower().startswith("52wst"):
                created = process_scanned_52(pdf_file)
            else:
                created = process_pdf(pdf_file)

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
