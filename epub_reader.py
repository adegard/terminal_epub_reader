import zipfile
import sys
import os
import json
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# ---------------------------------------------------------
# DISATTIVA WARNING BS4
# ---------------------------------------------------------
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ---------------------------------------------------------
# FILE UNICO DI SALVATAGGIO
# ---------------------------------------------------------
SAVE_DIR = os.path.expanduser("~/.epub_reader_saves")
os.makedirs(SAVE_DIR, exist_ok=True)

SAVE_FILE = os.path.join(SAVE_DIR, "reading_positions.json")

def load_positions():
    if not os.path.exists(SAVE_FILE):
        return {}
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_positions(data):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def salva_posizione(book, chapter, paragraph):
    data = load_positions()
    data[book] = {"chapter": chapter, "paragraph": paragraph}
    save_positions(data)

def carica_posizione(book):
    data = load_positions()
    if book in data:
        chapter = data[book].get("chapter", 0)
        paragraph = data[book].get("paragraph", 0)
        return chapter, paragraph
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

            title = html.find(["h1", "h2", "h3", "title"])
            title = title.get_text().strip() if title else file_path

            capitoli.append((title, full_path))

        return capitoli

# ---------------------------------------------------------
# ESTRAZIONE TITOLI + PARAGRAFI (INTELLIGENTE)
# ---------------------------------------------------------
def estrai_testo_capitolo(epub_file, file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        data = z.read(file).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(data, "html.parser")

        blocks = []

        # 1. TITOLI (sempre pagina singola)
        for tag in soup.find_all(["h1", "h2", "h3", "title"]):
            text = tag.get_text().strip()
            if text:
                blocks.append(text)

        # 2. PARAGRAFI veri
        for p in soup.find_all("p"):
            text = p.get_text().strip()
            if text:
                blocks.append(text)

        # 3. Testo libero (fallback)
        raw_lines = soup.get_text(separator="\n").split("\n")
        for line in raw_lines:
            line = line.strip()
            if line and line not in blocks:
                blocks.append(line)

        # 4. Rimuovi duplicati mantenendo ordine
        seen = set()
        clean = []
        for b in blocks:
            if b not in seen:
                clean.append(b)
                seen.add(b)

        return clean

# ---------------------------------------------------------
# LETTORE A PARAGRAFI (ENTER → PARAGRAFO SUCCESSIVO)
# ---------------------------------------------------------
def mostra_capitolo(paragraphs, book, chapter_index, total_chapters):
    total_paragraphs = len(paragraphs)

    saved_chapter, saved_paragraph = carica_posizione(book)
    paragraph = saved_paragraph if saved_chapter == chapter_index else 0

    while True:
        os.system("clear")

        print(paragraphs[paragraph])
        print(f"\n--- Capitolo {chapter_index+1}/{total_chapters} | Blocco {paragraph+1}/{total_paragraphs} ---")
        print("[INVIO] avanti  [p] indietro  [q] menu  [e] esci app")

        cmd = input("> ")

        # ENTER → avanti
        if cmd == "":
            if paragraph < total_paragraphs - 1:
                paragraph += 1
                salva_posizione(book, chapter_index, paragraph)
                continue

            # ultimo blocco → capitolo successivo
            salva_posizione(book, chapter_index, paragraph)
            return "next"

        cmd = cmd.lower().strip()

        if cmd == "p":
            if paragraph > 0:
                paragraph -= 1

        elif cmd == "q":
            salva_posizione(book, chapter_index, paragraph)
            return None

        elif cmd == "e":
            salva_posizione(book, chapter_index, paragraph)
            print("Posizione salvata. Uscita.")
            sys.exit(0)

        salva_posizione(book, chapter_index, paragraph)

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
# MENU LETTURA
# ---------------------------------------------------------
def menu_lettura(book, capitoli):
    saved_chapter, saved_paragraph = carica_posizione(book)

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

        if not files:
            print("Nessun EPUB trovato.")
            sys.exit(0)

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
                paragraphs = estrai_testo_capitolo(epub_path, file)

                while True:
                    result = mostra_capitolo(paragraphs, book_name, chapter_index, len(capitoli))
                    if result == "next":
                        if chapter_index + 1 < len(capitoli):
                            chapter_index += 1
                            title, file = capitoli[chapter_index]
                            paragraphs = estrai_testo_capitolo(epub_path, file)
                            continue
                    break

            if isinstance(scelta, tuple) and scelta[0] == "continua":
                chapter_index = scelta[1]

                title, file = capitoli[chapter_index]
                paragraphs = estrai_testo_capitolo(epub_path, file)

                while True:
                    result = mostra_capitolo(paragraphs, book_name, chapter_index, len(capitoli))
                    if result == "next":
                        if chapter_index + 1 < len(capitoli):
                            chapter_index += 1
                            title, file = capitoli[chapter_index]
                            paragraphs = estrai_testo_capitolo(epub_path, file)
                            continue
                    break

