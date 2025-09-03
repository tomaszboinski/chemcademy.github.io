import os
from PIL import Image

def white_to_transparent(input_path):
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()

    new_data = []
    for item in datas:
        if item[0] > 240 and item[1] > 240 and item[2] > 240:  # Białe lub prawie białe
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)

    img.putdata(new_data)
    img.save(input_path, "PNG")  # nadpisujemy oryginalny plik
    print(f"Przetworzono: {input_path}")

def process_current_folder():
    folder_path = os.getcwd()  # bieżący katalog, w którym uruchomiono skrypt
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".png"):
            input_path = os.path.join(folder_path, filename)
            white_to_transparent(input_path)

# Uruchomienie
process_current_folder()