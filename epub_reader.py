import zipfile
import sys
import os
import json
import warnings
import termios
import tty
import shutil
import threading
import time
from bs4 import BeautifulSoup
import pyttsx3


# ---------------------------------------------------------
# SAVE FILE
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

def save_position(book, chapter, paragraph):
    data = load_positions()
    data[book] = {"chapter": chapter, "paragraph": paragraph}
    save_positions(data)

def load_position(book):
    data = load_positions()
    if book in data:
        return data[book].get("chapter", 0), data[book].get("paragraph", 0)
    return 0, 0


# ---------------------------------------------------------
# TTS READER
# ---------------------------------------------------------
class TTSReader:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.reading = False
        self.stop_flag = False
        self.thread = None

    def _speak_interruptible(self, text):
        """Speak text but allow interruption mid‑sentence."""
        self.engine.stop()  # clear queue
        self.engine.say(text)

        # Run engine in small chunks so we can interrupt
        while not self.stop_flag:
            running = self.engine.runAndWait()
            # runAndWait returns when queue is empty
            break

    def start_reading(self, paragraphs, start_index, on_block_advance=None):
        if self.reading:
            return

        self.reading = True
        self.stop_flag = False

        def run():
            index = start_index
            total = len(paragraphs)

            while index < total and not self.stop_flag:
                block = paragraphs[index].strip()
                if block:
                    self._speak_interruptible(block)

                if self.stop_flag:
                    break

                index += 1
                if on_block_advance:
                    on_block_advance(index)

            self.reading = False

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        self.engine.stop()  # force immediate stop
        self.reading = False


tts_reader = TTSReader()


# ---------------------------------------------------------
# EPUB READING (CORRECT ORDER)
# ---------------------------------------------------------
def extract_chapters(epub_file):
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

        chapters = []
        base_path = os.path.dirname(opf_path)

        for idref in spine_ids:
            if idref not in manifest:
                continue
            file_path = os.path.join(base_path, manifest[idref])
            data = z.read(file_path).decode("utf-8", errors="ignore")
            html = BeautifulSoup(data, "html.parser")
            title = html.find(["h1", "h2", "h3", "title"])
            title = title.get_text().strip() if title else file_path
            chapters.append((title, file_path))

        return chapters

# ---------------------------------------------------------
# EXTRACT TITLES + PARAGRAPHS
# ---------------------------------------------------------
def extract_chapter_text(epub_file, file):
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
# REAL KEY READING (ENTER, SPACE, ARROWS)
# ---------------------------------------------------------
def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == "\x1b":  # ESC sequence
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return f"ESC[{ch3}"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ---------------------------------------------------------
# PARAGRAPH READER WITH WRAPPING + MARGINS + TTS
# ---------------------------------------------------------
def show_chapter(paragraphs, book, chapter_index, total_chapters):

    LEFT_MARGIN = "  "
    RIGHT_MARGIN = "  "
    MARGIN_WIDTH = len(LEFT_MARGIN) + len(RIGHT_MARGIN)

    def wrap(text, width):
        words = text.split()
        lines = []
        current = ""

        for w in words:
            if len(current) + len(w) + 1 > width:
                lines.append(current)
                current = w
            else:
                current = w if current == "" else current + " " + w

        if current:
            lines.append(current)

        return "\n".join(LEFT_MARGIN + line + RIGHT_MARGIN for line in lines)

    total = len(paragraphs)
    saved_chapter, saved_paragraph = load_position(book)
    paragraph = saved_paragraph if saved_chapter == chapter_index else 0

    def on_block_advance(new_index):
        nonlocal paragraph
        if new_index < total:
            paragraph = new_index
            save_position(book, chapter_index, paragraph)

    while True:
        os.system("clear")

        cols = shutil.get_terminal_size().columns
        usable_width = max(10, cols - MARGIN_WIDTH)

        print(wrap(paragraphs[paragraph], usable_width))

        print(f"\n--- Chapter {chapter_index+1}/{total_chapters} | Block {paragraph+1}/{total} ---")
        print("[ENTER / SPACE / Vol-] next   [p / Vol+] previous   [r] read aloud   [s] stop TTS   [q] menu   [e] exit")

        key = read_key()

        if key in ["\r", "\n", " ", "ESC[B"]:
            key = "next"
        if key in ["ESC[A", "p"]:
            key = "prev"

        if key == "next":
            if paragraph < total - 1:
                paragraph += 1
                save_position(book, chapter_index, paragraph)
                continue
            save_position(book, chapter_index, paragraph)
            tts_reader.stop()
            return "next"

        if key == "prev":
            if paragraph > 0:
                paragraph -= 1
            save_position(book, chapter_index, paragraph)
            continue

        if key == "r":
            tts_reader.start_reading(paragraphs, paragraph, on_block_advance=on_block_advance)
            continue

        if key == "s":
            tts_reader.stop()
            continue

        if key == "q":
            save_position(book, chapter_index, paragraph)
            tts_reader.stop()
            return None

        if key == "e":
            save_position(book, chapter_index, paragraph)
            tts_reader.stop()
            print("Position saved. Exiting.")
            sys.exit(0)

# ---------------------------------------------------------
# MENUS
# ---------------------------------------------------------
def menu_summary(chapters):
    while True:
        os.system("clear")
        print("=== TABLE OF CONTENTS ===\n")
        for i, (title, _) in enumerate(chapters):
            print(f"{i+1}. {title}")
        print("\nq = back   e = exit")

        s = input("> ").strip().lower()
        if s == "e":
            sys.exit(0)
        if s == "q":
            return None
        if s.isdigit():
            n = int(s) - 1
            if 0 <= n < len(chapters):
                return n

def menu_reading(book, chapters):
    saved_chapter, saved_paragraph = load_position(book)

    while True:
        os.system("clear")
        print("=== READING MENU ===\n")

        if saved_chapter < len(chapters):
            print("1. Continue")
        else:
            print("1. Continue (not available)")

        print("2. Table of Contents")
        print("3. Change Book")
        print("4. Exit")

        s = input("> ").strip().lower()

        # NEW SHORTCUT: pressing ENTER = Continue
        if s == "" and saved_chapter < len(chapters):
            return ("continue", saved_chapter)

        if s == "4" or s == "e":
            sys.exit(0)
        if s == "3":
            return "change"
        if s == "2":
            return "summary"
        if s == "1" and saved_chapter < len(chapters):
            return ("continue", saved_chapter)

def menu_library(folder):
    folder = os.path.expanduser(folder)

    while True:
        os.system("clear")
        print("=== LIBRARY ===\n")

        files = [f for f in os.listdir(folder) if f.lower().endswith(".epub")]

        for i, f in enumerate(files):
            print(f"{i+1}. {f}")

        print("\ne = exit")

        s = input("> ").strip().lower()
        if s == "e":
            sys.exit(0)
        if s.isdigit():
            n = int(s) - 1
            if 0 <= n < len(files):
                return os.path.join(folder, files[n]), files[n]

def choose_folder():
    default = os.path.dirname(os.path.abspath(__file__))
    os.system("clear")
    print("Library folder (ENTER = default):")
    print(default)
    s = input("> ").strip()
    return default if s == "" else os.path.expanduser(s)

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    folder = choose_folder()

    while True:
        epub_path, book_name = menu_library(folder)
        chapters = extract_chapters(epub_path)

        while True:
            choice = menu_reading(book_name, chapters)

            if choice == "change":
                break

            if choice == "summary":
                chapter_index = menu_summary(chapters)
                if chapter_index is None:
                    continue

                title, file = chapters[chapter_index]
                paragraphs = extract_chapter_text(epub_path, file)

                while True:
                    result = show_chapter(paragraphs, book_name, chapter_index, len(chapters))
                    if result == "next" and chapter_index + 1 < len(chapters):
                        chapter_index += 1
                        title, file = chapters[chapter_index]
                        paragraphs = extract_chapter_text(epub_path, file)
                        continue
                    break

            if isinstance(choice, tuple):
                chapter_index = choice[1]
                title, file = chapters[chapter_index]
                paragraphs = extract_chapter_text(epub_path, file)

                while True:
                    result = show_chapter(paragraphs, book_name, chapter_index, len(chapters))
                    if result == "next" and chapter_index + 1 < len(chapters):
                        chapter_index += 1
                        title, file = chapters[chapter_index]
                        paragraphs = extract_chapter_text(epub_path, file)
                        continue
                    break
