import zipfile
import sys
import os
from bs4 import BeautifulSoup

PAGE_LINES = 25
SAVE_DIR = os.path.expanduser("~/.epub_reader_saves")

os.makedirs(SAVE_DIR, exist_ok=True)

# -------------------------------
# SALVATAGGIO POSIZIONE
# -------------------------------
def salva_posizione(book, chapter, page):
    path = os.path.join(SAVE_DIR, f"{book}.pos")
    with open(path, "w") as f:
        f.write(f"{chapter}|{page}")

def carica_posizione(book):
    path = os.path.join(SAVE_DIR, f"{book}.pos")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                chapter, page = f.read().strip().split("|")
                return int(chapter), int(page)
        except:
            return 0, 0
    return 0, 0

# -------------------------------
# LETTURA EPUB
# -------------------------------
def estrai_capitoli(epub_file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        files = z.namelist()
        xhtml_files = [f for f in files if f.endswith(('.xhtml', '.html'))]

        capitoli = []
        for f in xhtml_files:
            data = z.read(f).decode('utf-8', errors='ignore')
            soup = BeautifulSoup(data, "html.parser")

            title = soup.find(['h1', 'h2', 'title'])
            title = title.get_text().strip() if title else f"Capitolo: {f}"

            capitoli.append((title, f))

        return capitoli

def estrai_testo_capitolo(epub_file, file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        data = z.read(file).decode('utf-8', errors='ignore')
        soup = BeautifulSoup(data, "html.parser")
        return soup.get_text(separator="\n")

# -------------------------------
# VISUALIZZAZIONE CAPITOLO
# -------------------------------
def mostra_capitolo(text, book, chapter_index, total_chapters):
    lines = text.split("\n")
    total_pages = len(lines) // PAGE_LINES + 1

    saved_chapter, saved_page = carica_posizione(book)
    page = saved_page if saved_chapter == chapter_index else 0

    while True:
        os.system("clear")
        start = page * PAGE_LINES
        end = start + PAGE_LINES
        print("\n".join(lines[start:end]))

        print(f"\n--- Capitolo {chapter_index+1}/{total_chapters} | Pagina {page+1}/{total_pages} ---")
        print("[n] avanti  [p] indietro  [q] esci capitolo")

        cmd = input("> ").strip().lower()

        if cmd == "n" and page < total_pages - 1:
            page += 1
        elif cmd == "p" and page > 0:
            page -= 1
        elif cmd == "q":
            salva_posizione(book, chapter_index, page)
            break

        salva_posizione(book, chapter_index, page)

# -------------------------------
# MENU SOMMARIO
# -------------------------------
def menu_sommario(capitoli):
    while True:
        os.system("clear")
        print("=== SOMMARIO ===\n")
        for i, (title, _) in enumerate(capitoli):
            print(f"{i+1}. {title}")
        print("\nSeleziona un capitolo (numero) oppure 'q' per tornare alla libreria")

        scelta = input("> ").strip().lower()
        if scelta == "q":
            return None
        if scelta.isdigit():
            scelta = int(scelta) - 1
            if 0 <= scelta < len(capitoli):
                return scelta

# -------------------------------
# MENU LIBRERIA
# -------------------------------
def menu_libreria(cartella):
    cartella = os.path.expanduser(cartella)

    while True:
        os.system("clear")
        print("=== LIBRERIA ===\n")

        try:
            files = [f for f in os.listdir(cartella) if f.lower().endswith(".epub")]
        except FileNotFoundError:
            print(f"Cartella non trovata: {cartella}")
            input("Premi INVIO per uscire")
            sys.exit(1)

        if not files:
            print("Nessun file EPUB trovato nella cartella.")
            input("Premi INVIO per uscire")
            sys.exit(0)

        for i, f in enumerate(files):
            print(f"{i+1}. {f}")

        print("\nSeleziona un libro (numero):")

        scelta = input("> ").strip()
        if scelta.isdigit():
            scelta = int(scelta) - 1
            if 0 <= scelta < len(files):
                return os.path.join(cartella, files[scelta]), files[scelta]

# -------------------------------
# SCELTA CARTELLA
# -------------------------------
def scegli_cartella():
    os.system("clear")
    print("Inserisci il percorso della cartella libreria (es: ~/storage/downloads):")
    return input("> ").strip()

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    cartella = scegli_cartella()
    epub_path, book_name = menu_libreria(cartella)

    while True:
        capitoli = estrai_capitoli(epub_path)
        total_chapters = len(capitoli)

        chapter_index = menu_sommario(capitoli)
        if chapter_index is None:
            epub_path, book_name = menu_libreria(cartella)
            continue

        title, file = capitoli[chapter_index]
        text = estrai_testo_capitolo(epub_path, file)
        mostra_capitolo(text, book_name, chapter_index, total_chapters)

