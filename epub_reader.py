import zipfile
import sys
import os
import json
import warnings
import termios
import tty
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

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
        return data[book].get("chapter", 0), data[book].get("paragraph", 0)
    return 0, 0

def estrai_capitoli(epub_file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        opf_path = None
        for f in z.namelist():
            if f.endswith(".opf"):
                opf_path = f
                break

        opf_data = z.read(opf_path).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(opf_data, "html.parser")

        manifest = {item.get("id"): item.get("href") for item in soup.find_all("item")}
        spine_ids = [item.get("idref") for item in soup.find_all("itemref")]

        capitoli = []
        base_path = os.path.dirname(opf_path)

        for idref in spine_ids:
            if idref not in manifest:
                continue
            file_path = os.path.join(base_path, manifest[idref])
            data = z.read(file_path).decode("utf-8", errors="ignore")
            html = BeautifulSoup(data, "html.parser")
            title = html.find(["h1", "h2", "h3", "title"])
            title = title.get_text().strip() if title else file_path
            capitoli.append((title, file_path))

        return capitoli

def estrai_testo_capitolo(epub_file, file):
    with zipfile.ZipFile(epub_file, 'r') as z:
        data = z.read(file).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(data, "html.parser")

        blocks = []

        for tag in soup.find_all(["h1", "h2", "h3", "title"]):
            t = tag.get_text().strip()
            if t:
                blocks.append(t)

        for p in soup.find_all("p"):
            t = p.get_text().strip()
            if t:
                blocks.append(t)

        raw = soup.get_text(separator="\n").split("\n")
        for line in raw:
            line = line.strip()
            if line and line not in blocks:
                blocks.append(line)

        seen = set()
        clean = []
        for b in blocks:
            if b not in seen:
                clean.append(b)
                seen.add(b)

        return clean

# ---------------------------------------------------------
# LETTURA TASTI REALI (ENTER, SPACE, FRECCE)
# ---------------------------------------------------------
def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == "\x1b":  # sequenza ESC
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return f"ESC[{ch3}"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ---------------------------------------------------------
# LETTORE A PARAGRAFI
# ---------------------------------------------------------
def mostra_capitolo(paragraphs, book, chapter_index, total_chapters):
    total = len(paragraphs)
    saved_chapter, saved_paragraph = carica_posizione(book)
    paragraph = saved_paragraph if saved_chapter == chapter_index else 0

    while True:
        os.system("clear")
        print(paragraphs[paragraph])
        print(f"\n--- Capitolo {chapter_index+1}/{total_chapters} | Blocco {paragraph+1}/{total} ---")
        print("[ENTER / SPACE / Vol-] avanti   [p / Vol+] indietro   [q] menu   [e] esci")

        key = read_key()

        # ENTER
        if key == "\r" or key == "\n":
            key = "next"

        # SPACE
        if key == " ":
            key = "next"

        # FRECCIA GIÙ (Volume GIÙ)
        if key == "ESC[B":
            key = "next"

        # FRECCIA SU (Volume SU)
        if key == "ESC[A":
            key = "prev"

        if key == "next":
            if paragraph < total - 1:
                paragraph += 1
                salva_posizione(book, chapter_index, paragraph)
                continue
            salva_posizione(book, chapter_index, paragraph)
            return "next"

        if key == "prev" or key == "p":
            if paragraph > 0:
                paragraph -= 1
            salva_posizione(book, chapter_index, paragraph)
            continue

        if key == "q":
            salva_posizione(book, chapter_index, paragraph)
            return None

        if key == "e":
            salva_posizione(book, chapter_index, paragraph)
            print("Posizione salvata. Uscita.")
            sys.exit(0)

# ---------------------------------------------------------
# MENU
# ---------------------------------------------------------
def menu_sommario(capitoli):
    while True:
        os.system("clear")
        print("=== SOMMARIO ===\n")
        for i, (title, _) in enumerate(capitoli):
            print(f"{i+1}. {title}")
        print("\nq = menu   e = esci")

        s = input("> ").strip().lower()
        if s == "e":
            sys.exit(0)
        if s == "q":
            return None
        if s.isdigit():
            n = int(s) - 1
            if 0 <= n < len(capitoli):
                return n

def menu_lettura(book, capitoli):
    saved_chapter, saved_paragraph = carica_posizione(book)

    while True:
        os.system("clear")
        print("=== MENU LETTURA ===\n")
        if saved_chapter < len(capitoli):
            print("1. Continua")
        else:
            print("1. Continua (non disponibile)")
        print("2. Sommario")
        print("3. Cambia libro")
        print("4. Esci")

        s = input("> ").strip().lower()

        if s == "4" or s == "e":
            sys.exit(0)
        if s == "3":
            return "cambia"
        if s == "2":
            return "sommario"
        if s == "1" and saved_chapter < len(capitoli):
            return ("continua", saved_chapter)

def menu_libreria(cartella):
    cartella = os.path.expanduser(cartella)

    while True:
        os.system("clear")
        print("=== LIBRERIA ===\n")

        files = [f for f in os.listdir(cartella) if f.lower().endswith(".epub")]

        for i, f in enumerate(files):
            print(f"{i+1}. {f}")

        print("\ne = esci")

        s = input("> ").strip().lower()
        if s == "e":
            sys.exit(0)
        if s.isdigit():
            n = int(s) - 1
            if 0 <= n < len(files):
                return os.path.join(cartella, files[n]), files[n]

def scegli_cartella():
    default = os.path.dirname(os.path.abspath(__file__))
    os.system("clear")
    print("Cartella libreria (INVIO = default):")
    print(default)
    s = input("> ").strip()
    return default if s == "" else os.path.expanduser(s)

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
                    if result == "next" and chapter_index + 1 < len(capitoli):
                        chapter_index += 1
                        title, file = capitoli[chapter_index]
                        paragraphs = estrai_testo_capitolo(epub_path, file)
                        continue
                    break

            if isinstance(scelta, tuple):
                chapter_index = scelta[1]
                title, file = capitoli[chapter_index]
                paragraphs = estrai_testo_capitolo(epub_path, file)

                while True:
                    result = mostra_capitolo(paragraphs, book_name, chapter_index, len(capitoli))
                    if result == "next" and chapter_index + 1 < len(capitoli):
                        chapter_index += 1
                        title, file = capitoli[chapter_index]
                        paragraphs = estrai_testo_capitolo(epub_path, file)
                        continue
                    break

