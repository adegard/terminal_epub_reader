import zipfile
import sys
import os
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# CALCOLO AUTOMATICO DELLE RIGHE PER PAGINA
# ---------------------------------------------------------
def get_page_lines():
    try:
        rows, cols = os.get_terminal_size()
        return max(5, rows - 5)
    except:
        return 10  # fallback
        

SAVE_DIR = os.path.expanduser("~/.epub_reader_saves")
os.makedirs(SAVE_DIR, exist_ok=True)

# ---------------------------------------------------------
# SALVATAGGIO POSIZIONE
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# LETTURA EPUB (ORDINE CORRETTO)
# ---------------------------------------------------------
def estrai_capitoli(epub_file):
    with zipfile.ZipFile(epub_file, 'r') as z:

        opf_path = None
        for f in z.namelist():
            if f.endswith(".opf"):
                opf_path = f
                break

        if not opf_path:
            raise Exception("File OPF non trovato")

        opf_data = z.read(opf_path).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(opf_data, "html.parser")

        manifest = {}
        for item in soup.find_all("item"):
            if item.get("id") and item.get("href"):
                manifest[item.get("id")] = item.get("href")

        spine_ids = [item.get("idref") for item in soup.find_all("itemref")]

        capitoli = []
        base_path = os.path.dirname(opf_path)

        for idref in spine_ids:
            if idref not in manifest:
                continue

            file_path = manifest[idref]
            full_path = os.path.join(base_path, file_path)

            data = z.read(full_path).decode("utf-8", errors="ignore")
            html = BeautifulSoup(data, "html.parser")

            title = html.find(["h1", "h2", "title"])
            title = title.get_text().strip() if title else file_path

            capitoli.append((title, full_path))

        return capitoli

def estrai_testo_capitolo(epub_file, file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        data = z.read(file).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(data, "html.parser")
        return soup.get_text(separator="\n")

# ---------------------------------------------------------
# LETTORE A PAGINE
# ---------------------------------------------------------
def mostra_capitolo(text, book, chapter_index, total_chapters):
    PAGE_LINES = get_page_lines()

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
        print("[INVIO] avanti  [p] indietro  [q] menu  [e] esci app")

        cmd = input("> ").strip().lower()

        if cmd == "":
            if page < total_pages - 1:
                page += 1

        elif cmd == "p":
            if page > 0:
                page -= 1

        elif cmd == "q":
            salva_posizione(book, chapter_index, page)
            return

        elif cmd == "e":
            salva_posizione(book, chapter_index, page)
            print("Posizione salvata. Uscita.")
            sys.exit(0)

        salva_posizione(book, chapter_index, page)

# ---------------------------------------------------------
# MENU SOMMARIO
# ---------------------------------------------------------
def menu_sommario(capitoli):
    while True:
        os.system("clear")
        print("=== SOMMARIO ===\n")
        for i, (title, _) in enumerate(capitoli):
            print(f"{i+1}. {title}")
        print("\nSeleziona un capitolo, oppure:")
        print("q = torna al menu")
        print("e = esci app")

        scelta = input("> ").strip().lower()

        if scelta == "e":
            sys.exit(0)

        if scelta == "q":
            return None

        if scelta.isdigit():
            scelta = int(scelta) - 1
            if 0 <= scelta < len(capitoli):
                return scelta

# ---------------------------------------------------------
# MENU LETTURA (CONTINUA)
# ---------------------------------------------------------
def menu_lettura(book, capitoli):
    saved_chapter, saved_page = carica_posizione(book)

    while True:
        os.system("clear")
        print("=== MENU LETTURA ===\n")

        if saved_chapter < len(capitoli):
            print("1. Continua da dove eri rimasto")
        else:
            print("1. Continua (non disponibile)")

        print("2. Vai al sommario")
        print("3. Cambia libro")
        print("4. Esci")

        scelta = input("> ").strip().lower()

        if scelta == "4" or scelta == "e":
            sys.exit(0)

        if scelta == "3":
            return "cambia"

        if scelta == "2":
            return "sommario"

        if scelta == "1" and saved_chapter < len(capitoli):
            return ("continua", saved_chapter)

# ---------------------------------------------------------
# MENU LIBRERIA
# ---------------------------------------------------------
def menu_libreria(cartella):
    cartella = os.path.expanduser(cartella)

    while True:
        os.system("clear")
        print("=== LIBRERIA ===\n")

        try:
            files = [f for f in os.listdir(cartella) if f.lower().endswith(".epub")]
        except:
            print("Cartella non trovata.")
            sys.exit(1)

        for i, f in enumerate(files):
            print(f"{i+1}. {f}")

        print("\nSeleziona un libro oppure 'e' per uscire")

        scelta = input("> ").strip().lower()

        if scelta == "e":
            sys.exit(0)

        if scelta.isdigit():
            scelta = int(scelta) - 1
            if 0 <= scelta < len(files):
                return os.path.join(cartella, files[scelta]), files[scelta]

# ---------------------------------------------------------
# SCELTA CARTELLA
# ---------------------------------------------------------
def scegli_cartella():
    default = os.path.dirname(os.path.abspath(__file__))
    os.system("clear")
    print("Inserisci la cartella libreria")
    print(f"Premi INVIO per usare quella predefinita:\n{default}\n")
    scelta = input("> ").strip()

    if scelta == "":
        return default

    return os.path.expanduser(scelta)

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    cartella = scegli_cartella()

    while True:
        epub_path, book_name = menu_libreria(cartella)
        capitoli = estrai_capitoli(epub_path)

        while True:
            scelta = menu_lettura(book_name, capitoli)

            if scelta == "cambia":
                break

            if scelta == "sommario":
                chapter_index = menu_sommario(capitoli)
                if chapter_index is None:
                    continue
                title, file = capitoli[chapter_index]
                text = estrai_testo_capitolo(epub_path, file)
                mostra_capitolo(text, book_name, chapter_index, len(capitoli))

            if isinstance(scelta, tuple) and scelta[0] == "continua":
                chapter_index = scelta[1]
                title, file = capitoli[chapter_index]
                text = estrai_testo_capitolo(epub_path, file)
                mostra_capitolo(text, book_name, chapter_index, len(capitoli))

