#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ustawia minimalną wysokość ostatniej strony samodzielnych plików PDF z zadaniami.

- Przeszukuje folder startowy i wszystkie podkatalogi.
- Zadania i rozwiązania powinny znajdować się w oddzielnych plikach.
- Pliki rozwiązań są pomijane.
- Jeśli całkowita wysokość sekcji zadania jest mniejsza niż 842 pt,
  ostatnia strona jest wydłużana o brakującą wysokość: 842 pt minus
  całkowita wysokość zadania (bez skalowania zawartości).
- Zmiany są zapisywane do pliku tymczasowego, a następnie zastępują oryginał.
- Nie pyta o potwierdzenie i nie tworzy kopii zapasowych.

Wymaganie: pip install pymupdf
Uruchomienie:
    python popraw_wysokosc_zadan.py
albo:
    python popraw_wysokosc_zadan.py "D:\\folder\\z PDF-ami"
"""

import os
import re
import sys
import tempfile
import traceback

import pymupdf as fitz


MIN_HEIGHT_PT = 1300

TASK_RE = re.compile(
    r"^\s*ZADANIE\s+([AB]?\s*\d+\s*[AB]?)\b",
    re.IGNORECASE,
)
SOLUTION_RE = re.compile(
    r"^\s*ROZWIĄZANI[AE]\s+ZADANIA\s+([AB]?\s*\d+\s*[AB]?)\b",
    re.IGNORECASE,
)
TOPICS_RE = re.compile(
    r"^\s*(?:ROZWIĄZANIA\s+ZADAŃ\s+ETAPU\s+WSTĘPNEGO)\b",
    re.IGNORECASE,
)


def clean_line(text):
    return text.replace("\xa0", " ").replace("\u200b", "").strip()


def normalize_task_number(value):
    value = re.sub(r"\s+", "", value.strip().upper())
    match = re.fullmatch(r"(\d+)([AB])", value)
    if match:
        return f"{match.group(2)}{match.group(1)}"
    return value


def find_headings(doc):
    """Rozpoznaje nagłówki tekstowe, korzystając z reguł modelowego skryptu."""
    headings = []
    solution_mode = False

    for page_no, page in enumerate(doc):
        try:
            data = page.get_text("dict")
        except Exception:
            continue

        for block in data.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = clean_line("".join(
                    span.get("text", "") for span in line.get("spans", [])
                ))
                if not text:
                    continue

                rect = fitz.Rect(line["bbox"])

                if TOPICS_RE.match(text):
                    solution_mode = True
                    headings.append({
                        "type": "topics", "number": None,
                        "page": page_no, "y": rect.y0, "text": text,
                    })
                    continue

                match = SOLUTION_RE.match(text)
                if match:
                    solution_mode = True
                    headings.append({
                        "type": "solution",
                        "number": normalize_task_number(match.group(1)),
                        "page": page_no, "y": rect.y0, "text": text,
                    })
                    continue

                match = TASK_RE.match(text)
                if match:
                    kind = "solution" if solution_mode else "task"
                    headings.append({
                        "type": kind,
                        "number": normalize_task_number(match.group(1)),
                        "page": page_no, "y": rect.y0, "text": text,
                    })

    headings.sort(key=lambda h: (h["page"], h["y"]))
    # Usuwanie prostych duplikatów na tej samej stronie i wysokości.
    unique = []
    seen = set()
    for h in headings:
        key = (h["type"], h["number"], h["page"], round(h["y"] / 5) * 5)
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique


def section_height(doc, heading, next_heading):
    """Łączna wysokość wycinka zadania, w punktach PDF."""
    start_page = heading["page"]
    start_y = max(0.0, heading["y"])

    if next_heading:
        end_page = next_heading["page"]
        end_y = max(0.0, next_heading["y"])
    else:
        end_page = len(doc) - 1
        end_y = doc[end_page].rect.height

    if end_page < start_page:
        return 0.0, end_page

    if start_page == end_page:
        return max(0.0, end_y - start_y), end_page

    total = max(0.0, doc[start_page].rect.height - start_y)
    for page_no in range(start_page + 1, end_page):
        total += doc[page_no].rect.height
    total += max(0.0, end_y)
    return total, end_page


def process_pdf(path):
    if os.path.basename(path).startswith("~"):
        return "pominięto"

    try:
        doc = fitz.open(path)
    except Exception as exc:
        print(f"[BŁĄD ODCZYTU] {path}: {exc}")
        return "błąd"

    try:
        if not doc or doc.is_encrypted:
            print(f"[POMINIĘTO] Pusty lub zaszyfrowany PDF: {path}")
            return "pominięto"

        headings = find_headings(doc)
        task_headings = [h for h in headings if h["type"] == "task"]
        solution_headings = [h for h in headings if h["type"] == "solution"]

        # Plik rozwiązania: pierwszy właściwy nagłówek to rozwiązanie.
        first_section_heading = next(
            (h for h in headings if h["type"] in ("task", "solution")),
            None,
        )
        if first_section_heading is None:
            print(f"[POMINIĘTO] Nie znaleziono nagłówka zadania/rozwiązania: {path}")
            return "pominięto"
        if first_section_heading["type"] == "solution":
            print(f"[POMINIĘTO] Plik rozwiązania: {path}")
            return "pominięto"

        # Pliki *_podzielone zawierają zwykle:
        # ZADANIE -> ROZWIĄZANIE.
        # Interesuje nas wyłącznie długość pierwszej sekcji zadania,
        # więc końcem jest pierwszy nagłówek rozwiązania.
        heading = task_headings[0]
        next_heading = solution_headings[0] if solution_headings else None
        total_height, end_page = section_height(doc, heading, next_heading)
        last_page = doc[end_page]
        old_height = last_page.rect.height

        if total_height >= MIN_HEIGHT_PT:
            print(
                f"[BEZ ZMIAN] {path} — długość zadania {total_height:.1f} pt "
                f"(minimum {MIN_HEIGHT_PT:.0f} pt)"
            )
            return "bez zmian"

        # Dodajemy brakującą wysokość do obecnej wysokości ostatniej strony,
        # tak aby całkowita długość sekcji zadania wyniosła 842 pt.
        missing_height = MIN_HEIGHT_PT - total_height
        new_height = old_height + missing_height

        width = last_page.rect.width
        # Powiększamy stronę, nie skalując ani nie przesuwając zawartości.
        last_page.set_mediabox(fitz.Rect(0, 0, width, new_height))

        folder = os.path.dirname(path) or "."
        fd, temp_path = tempfile.mkstemp(
            prefix=".pdf_height_fix_", suffix=".pdf", dir=folder
        )
        os.close(fd)
        try:
            doc.save(temp_path, garbage=4, deflate=True)
            doc.close()
            os.replace(temp_path, path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise

        print(
            f"[POPRAWIONO] {path} — długość zadania {total_height:.1f} pt; "
            f"ostatnia strona: {old_height:.1f} → {new_height:.1f} pt "
            f"(dodano {missing_height:.1f} pt)"
        )
        return "poprawiono"

    except Exception as exc:
        print(f"[BŁĄD] {path}: {exc}")
        traceback.print_exc()
        return "błąd"
    finally:
        try:
            doc.close()
        except Exception:
            pass


def main():
    root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(
        os.path.abspath(__file__)
    )
    if not os.path.isdir(root):
        print(f"Folder nie istnieje: {root}")
        sys.exit(1)

    pdf_paths = []
    for current, dirs, files in os.walk(root):
        # Pomijamy foldery systemowe/śmieciowe i foldery kopii zapasowych.
        dirs[:] = sorted(
            d for d in dirs
            if d not in {".git", "__pycache__"}
        )
        for name in files:
            if name.lower().endswith(".pdf") and not name.startswith("~"):
                pdf_paths.append(os.path.join(current, name))

    pdf_paths.sort(key=lambda p: p.lower())
    print(f"Folder: {root}")
    print(f"Znaleziono plików PDF: {len(pdf_paths)}")
    print("Rozpoczynam automatyczne sprawdzanie i nadpisywanie...\n")

    counts = {"poprawiono": 0, "bez zmian": 0, "pominięto": 0, "błąd": 0}
    for path in pdf_paths:
        result = process_pdf(path)
        counts[result] = counts.get(result, 0) + 1

    print("\n" + "=" * 60)
    print("KONIEC")
    print(f"Poprawiono: {counts['poprawiono']}")
    print(f"Bez zmian: {counts['bez zmian']}")
    print(f"Pominięto: {counts['pominięto']}")
    print(f"Błędy: {counts['błąd']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
