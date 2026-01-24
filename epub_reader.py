import zipfile
import sys
import os
from bs4 import BeautifulSoup

PAGE_LINES = 25  # righe per pagina
SAVE_FILE = "epub_reader_pos.txt"  # file per salvare la posizione

def estrai_testo(epub_file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        xhtml_files = [f for f in z.namelist() if f.endswith(('.xhtml', '.html'))]
        full_text = ""

        for f in xhtml_files:
            data = z.read(f).decode('utf-8', errors='ignore')
            soup = BeautifulSoup(data, "html.parser")
            text = soup.get_text(separator="\n")
            full_text += text + "\n\n"

    return full_text

def salva_posizione(page):
    with open(SAVE_FILE, "w") as f:
        f.write(str(page))

def carica_posizione():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0

def mostra_pagine(text):
    lines = text.split("\n")
    total_pages = len(lines) // PAGE_LINES + 1

    page = carica_posizione()

    while True:
        start = page * PAGE_LINES
        end = start + PAGE_LINES
        os.system("clear")
        print("\n".join(lines[start:end]))
        print(f"\n--- Pagina {page+1}/{total_pages} ---")
        print("[n] avanti  [p] indietro  [q] esci")

        cmd = input("> ").strip().lower()

        if cmd == "n":
            if page < total_pages - 1:
                page += 1
        elif cmd == "p":
            if page > 0:
                page -= 1
        elif cmd == "q":
            salva_posizione(page)
            print("Posizione salvata. Uscita.")
            break

        salva_posizione(page)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python epub_reader.py file.epub")
        sys.exit(1)

    epub_file = sys.argv[1]
    testo = estrai_testo(epub_file)
    mostra_pagine(testo)

