from bs4 import BeautifulSoup

# plik HTML do przerobienia
file_path = "artykuly.html"

# wczytanie pliku
with open(file_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

# znajdź wszystkie divy z klasą article-title
for div in soup.find_all("div", class_="article-title"):
    if div.string:
        div.string = div.string.lower()

# zapisz zmodyfikowany HTML
with open(file_path, "w", encoding="utf-8") as f:
    f.write(str(soup))

print(f"Wszystkie article-title w {file_path} zamienione na małe litery ✅")
# plik HTML do przerobienia

file_path = "zadania.html"

# wczytanie pliku
with open(file_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

# znajdź wszystkie divy z klasą article-title
for div in soup.find_all("div", class_="article-title"):
    if div.string:
        div.string = div.string.lower()

# zapisz zmodyfikowany HTML
with open(file_path, "w", encoding="utf-8") as f:
    f.write(str(soup))

print(f"Wszystkie article-title w {file_path} zamienione na małe litery ✅")