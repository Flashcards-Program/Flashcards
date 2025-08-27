# Copyright © Raoul van Zomeren. All rights reserved.

from __future__ import annotations

# ------ Imports ------
import json
import logging
import os
import platform
import random
import sys
import threading
import typing
import configparser

import pygame
import requests
import tkinter as tk
from packaging.version import Version
from pygame import mixer
from tkinter import ttk, messagebox, filedialog

# ------ Info & Initialization ------

# --- Constants ---
DEV_MODE: bool = False
PLAYTEST: int = 0  # 0 for release, 1 for first playtest, etc.
WIDTH, HEIGHT = 800, 600
VERSION, VERSION_NAME = "1.0.0", "The Launching Update"

# - Github Info -
OWNER, REPO, VAKKEN_REPO = "Flashcards-Program", "Flashcards", "Flashcards-Vakken"
LATEST_JSON_URL: str = (
    f"https://raw.githubusercontent.com/{OWNER}/{REPO}/refs/heads/main/versions.json"
)
SPLASH_JSON_URL: str = (
    f"https://raw.githubusercontent.com/{OWNER}/{REPO}/refs/heads/main/splash.json"
)

# --- Tkinter Initialization ---
root = tk.Tk()
root.title(
    f"Flashcards© v{VERSION}{f'-p{PLAYTEST}' if PLAYTEST else ''}: {VERSION_NAME}"
)
root.minsize(WIDTH, HEIGHT)
root.geometry(f"{WIDTH}x{HEIGHT}")

style = ttk.Style()

# ------ Logging Setup ------
logging.basicConfig(
    level=logging.DEBUG,
    format="[{levelname:<8}][{filename:>21}:{lineno:<4d} - {funcName:>18}()] {message}",
    style="{",
    handlers=[
        logging.FileHandler("latest.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# ------ Helper Functions ------

def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller .exe."""
    try:
        base_path: str = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def load_ini_file() -> str | None:
    config = configparser.ConfigParser()
    config.read(resource_path("config.ini"))
    return config.get("github", "token", fallback=None)


GITHUB_TOKEN: str | None = load_ini_file()


def fetch_versions_json() -> dict:
    """Load versions.json."""
    try:
        resp: requests.Response = requests.get(LATEST_JSON_URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.fatal(f"A fatal error occurred while fetching versions.json: {e}")
        messagebox.showerror("Fatal", f"A fatal error occurred:\n{e}")
        sys.exit(1)
    return resp.json()


VERSIONS_JSON: dict = fetch_versions_json()
LATEST_VERSION: str = VERSIONS_JSON.get("latest", VERSION)


def check_update_available(current: str, latest: str) -> tuple[bool, str]:
    """Return (is_update, latest_version) when latest > current."""
    try:
        current_version = Version(current)
        latest_version = Version(latest)
    except Exception:
        return False, current

    logging.debug(f"Current: {current_version} | Latest: {latest_version}")
    return (latest_version > current_version, latest if latest_version > current_version else current)


def get_splashtext() -> list[str]:
    try:
        response: requests.Response = requests.get(SPLASH_JSON_URL, timeout=15)
        response.raise_for_status()
        return typing.cast(list[str], response.json())
    except requests.RequestException as e:
        logging.error(f"Error getting splash text: {e}")
        return ["ERROR: Server returned an error."]


def setdefault_advanced(collection: dict | list, key, default_value):
    def _merge(current, default) -> dict | list:
        if isinstance(default, dict):
            if not isinstance(current, dict):
                return default
            for k, v in default.items():
                current[k] = _merge(current.get(k), v) if k in current else v
            return current
        elif isinstance(default, list):
            if not isinstance(current, list):
                return default
            return current
        else:
            return current if isinstance(current, type(default)) else default

    if key not in collection:
        collection[key] = default_value
    else:
        collection[key] = _merge(collection[key], default_value)
    return collection[key]


def serialize_settings(data: dict | list | tk.Variable) -> dict | list:
    if isinstance(data, tk.Variable):
        return data.get()
    elif isinstance(data, dict):
        return {k: serialize_settings(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_settings(i) for i in data]
    else:
        return typing.cast(dict | list, data)


class TkinterLogHandler(logging.Handler):
    def __init__(self, log_var: tk.StringVar, max_lines: int = 10):
        super().__init__()
        self.log_var = log_var
        self.max_lines = max_lines
        self.logs: list[str] = []

    def emit(self, record):
        log_entry = self.format(record)
        self.logs.append(log_entry)
        if len(self.logs) > self.max_lines:
            self.logs.pop(0)
        self.log_var.set("\n".join(self.logs))


class Menu:
    def __init__(self) -> None:
        logging.info("Running...")

        self.log_output_var = tk.StringVar()
        self.log_handler = TkinterLogHandler(self.log_output_var)
        self.log_handler.setLevel(logging.INFO)
        self.log_handler.setFormatter(
            logging.Formatter("[{asctime}][{levelname}] {message}", style="{")
        )
        logging.getLogger().addHandler(self.log_handler)

        style.configure("TButton", padding=2, font=("Helvetica", 12))

        self.current_music: str | None = None

        self.change(self.loading)
        root.after(500, threading.Thread(target=self.finish_init, daemon=True).start)

    def finish_init(self) -> None:
        # --- Get Latest Update and Generate Splashtext ---
        # Correct order: current=VERSION, latest=LATEST_VERSION
        self.update_available: tuple[bool, str] = check_update_available(
            VERSION, LATEST_VERSION
        )
        self.splashtext_array = get_splashtext()

        # --- Setup Settings ---
        self.settings_var: dict = self.settings_exists()

        # --- Set settings defaults ---
        # - booleans -
        setdefault_advanced(self.settings_var, "auto_update", tk.BooleanVar(root, True))
        setdefault_advanced(self.settings_var, "infinite", tk.BooleanVar(root, False))
        setdefault_advanced(
            self.settings_var, "advanced_setup", tk.BooleanVar(root, False)
        )

        # - strings -
        setdefault_advanced(
            self.settings_var, "language", tk.StringVar(root, "English (United States)")
        )
        setdefault_advanced(self.settings_var, "theme", tk.StringVar(root, "light"))

        # - dicts -
        setdefault_advanced(
            self.settings_var,
            "music",
            {
                "volume": tk.IntVar(root, 30),
                "cards": tk.StringVar(root, "silence.mp3"),
                "title": tk.StringVar(root, "silence.mp3"),
            },
        )
        setdefault_advanced(
            self.settings_var,
            "last_session",
            {
                "jaar": tk.StringVar(root, "Selecteer leerjaar"),
                "niveau": tk.StringVar(root, "Selecteer onderwijsniveau"),
                "vak": tk.StringVar(root, "Selecteer schoolvak"),
            },
        )

        # --- Setup GUI & Music ---
        self.load_languages()
        lang_code = self.settings_var["language"].get()
        self.current_language = lang_code
        self.translations = self.language_data.get(lang_code, {})

        self.apply_theme()
        self.rebuild_theme_map()
        self.setup_music()

        # --- Setup File Structure ---
        self.fetch_structure()

        # --- Auto-update Functionality ---
        if (
            self.settings_var["auto_update"].get()
            and self.update_available[0]
            and self.update_available[1]
        ):
            logging.info(
                f"Auto update: new version available, {self.update_available[1]}."
            )
            self.download_version(self.update_available[1])
        else:
            logging.info("Auto update: this is the latest version.")

        logging.info("Done!")
        self.change(self.main)

    def rebuild_theme_map(self) -> None:
        logging.info("Running...")
        self.theme_map: dict[str, str] = {"light": self.tr("light"), "dark": self.tr("dark")}
        self.inverse_theme_map: dict[str, str] = {v: k for k, v in self.theme_map.items()}
        logging.info("Done!")

    def download_version(self, target_version: str) -> None:
        """Authenticated download via GitHub Releases API."""
        logging.info("Running...")

        logging.debug(f"tag set to: {target_version}")

        filename: str = f"flashcards.v{target_version}.exe"
        api_headers: dict[str, str] = {
            "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
            "Accept": "application/vnd.github.v3+json",
        }

        # 1) Fetch release by tag
        rel_url: str = (
            f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{target_version}"
        )
        try:
            resp: requests.Response = requests.get(rel_url, headers=api_headers, timeout=30)
            if resp.status_code == 404:
                messagebox.showerror("Error", f"No release found for tag '{target_version}'.")
                logging.error(f"No release for tag '{target_version}' → 404")
                return
            resp.raise_for_status()
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Failed to query GitHub releases: {e}")
            logging.error(f"Releases API error: {e}")
            return
        release = resp.json()

        # 2) Find the asset whose name matches
        asset = next((a for a in release.get("assets", []) if a.get("name") == filename), None)
        if not asset:
            messagebox.showerror(
                "Error", f"Release '{target_version}' has no asset named:\n{filename}"
            )
            logging.error(f"Asset '{filename}' missing in release '{target_version}'")
            return

        # 3) Download the asset via its API endpoint
        download_url: str = (
            f"https://api.github.com/repos/{OWNER}/{REPO}/releases/assets/{asset['id']}"
        )
        dl_headers: dict[str, str] = {
            "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
            "Accept": "application/octet-stream",
        }
        try:
            r2: requests.Response = requests.get(download_url, headers=dl_headers, stream=True, timeout=60)
            r2.raise_for_status()
        except requests.RequestException as e:
            messagebox.showerror("Download Failed", str(e))
            logging.error(f"Download error: {e}")
            return

        # 4) Write to disk and notify
        local_path: str = os.path.join(os.getcwd(), filename)
        with open(local_path, "wb") as f:
            for chunk in r2.iter_content(8192):
                if chunk:
                    f.write(chunk)

        messagebox.showinfo(
            "Update Complete",
            f"Version {target_version} downloaded as:\n{local_path}\nPlease restart the program.",
        )
        logging.info(f"downloaded version {target_version} to {local_path}")
        logging.info("Done!")
        sys.exit(0)

    def load_languages(self) -> None:
        logging.info("Running...")

        self.language_data: dict[str, dict[str, str]] = {}
        self.code_to_display: dict[str, str] = {}
        self.display_to_code: dict[str, str] = {}
        self.available_languages: list[str] = []

        lang_dir: str = resource_path("languages")
        if os.path.isdir(lang_dir):
            for file in os.listdir(lang_dir):
                if file.endswith(".json"):
                    lang_code: str = file[:-5]
                    with open(os.path.join(lang_dir, file), encoding="utf-8") as f:
                        lang_data = json.load(f)
                        display_name = lang_data.get("language_name", lang_code)
                        self.language_data[lang_code] = lang_data
                        self.code_to_display[lang_code] = display_name
                        self.display_to_code[display_name] = lang_code
                        self.available_languages.append(display_name)

        if "language" not in self.settings_var:
            default_code = list(self.code_to_display.keys())[0] if self.code_to_display else "en"
            self.settings_var["language"] = tk.StringVar(root, default_code)
        elif isinstance(self.settings_var["language"], str):
            self.settings_var["language"] = tk.StringVar(root, self.settings_var["language"])  # type: ignore[arg-type]

        lang_code = self.settings_var["language"].get()
        if lang_code not in self.code_to_display and self.code_to_display:
            self.settings_var["language"].set(list(self.code_to_display.keys())[0])

        logging.info("Done!")

    def apply_theme(self) -> None:
        """Apply light or dark theme to all Ttk widgets."""
        logging.info("Running...")

        style.theme_use("clam")

        if self.settings_var["theme"].get() == "dark":
            self.bg = "#2e2e2e"
            self.fg = "#ffffff"
            self.field_bg = "#3e3e3e"
            self.btn_bg = "#444444"
            self.hover_bg = "#555555"
            self.highlight = "#666666"
            self.border = "#777777"
        else:
            self.bg = "#f0f0f0"
            self.fg = "#000000"
            self.field_bg = "#ffffff"
            self.btn_bg = "#e0e0e0"
            self.hover_bg = "#d0d0d0"
            self.highlight = "#0078d7"
            self.border = "#7a7a7a"

        root.configure(bg=self.bg)
        style.configure(".", background=self.bg, foreground=self.fg)
        style.configure("TButton", background=self.btn_bg, foreground=self.fg, relief=tk.SOLID)
        style.map("TButton", background=[("active", self.hover_bg)])
        style.configure("TLabel", background=self.bg, foreground=self.fg)
        style.configure(
            "TCombobox",
            fieldbackground=self.field_bg,
            background=self.field_bg,
            foreground=self.fg,
            relief=tk.FLAT,
        )
        style.map("TCombobox", fieldbackground=[("readonly", self.field_bg)], background=[("active", self.hover_bg)], foreground=[("readonly", self.fg)])
        style.configure("TCheckbutton", background=self.bg, foreground=self.fg)
        style.map("TCheckbutton", background=[("active", self.hover_bg)])
        style.configure("TFrame", background=self.bg)
        style.configure("Horizontal.TProgressbar", background=self.highlight)

        logging.info("Done!")

    def settings_exists(self) -> dict[str, tk.Variable | dict[str, tk.Variable]]:
        logging.info("Running...")
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                contents: str = f.read().strip()
                settings = json.loads(contents) if contents else {}
        except FileNotFoundError as e:
            logging.warning("file settings.json not found.")
            if messagebox.askyesno(
                title=str(e),
                message=(
                    "No settings file was found. A new one must be made to continue.\n"
                    "Make a new file?"
                ),
            ):
                with open("settings.json", "x", encoding="utf-8") as f:
                    json.dump({}, f, indent=4)
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
            else:
                self.on_closing(True)
                sys.exit(0)

        settings = typing.cast(dict, self.convert_settings(settings))
        logging.info("Done!")
        return settings

    def convert_settings(self, settings: dict | list) -> dict | list:
        logging.info("Running...")
        if isinstance(settings, dict):
            for key, value in list(settings.items()):
                if isinstance(value, (dict, list)):
                    settings[key] = self.convert_settings(value)
                elif isinstance(value, bool):
                    settings[key] = tk.BooleanVar(root, value)
                elif isinstance(value, int):
                    settings[key] = tk.IntVar(root, value)
                elif isinstance(value, str):
                    settings[key] = tk.StringVar(root, value)
        elif isinstance(settings, list):
            for i, value in enumerate(list(settings)):
                if isinstance(value, (dict, list)):
                    settings[i] = self.convert_settings(value)
                elif isinstance(value, bool):
                    settings[i] = tk.BooleanVar(root, value)
                elif isinstance(value, int):
                    settings[i] = tk.IntVar(root, value)
                elif isinstance(value, str):
                    settings[i] = tk.StringVar(root, value)
        logging.info("Done!")
        return settings

    def fetch_structure(self) -> None:
        """Fetch the entire Vakken folder structure from GitHub into a nested dict."""
        logging.info("Running...")

        API_BASE: str = f"https://api.github.com/repos/{OWNER}/{VAKKEN_REPO}/contents/Vakken"
        headers: dict[str, str] = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

        def get_contents(path: str = "") -> list:
            url: str = f"{API_BASE}/{path}" if path else API_BASE
            try:
                r: requests.Response = requests.get(url, headers=headers, timeout=30)
                r.raise_for_status()
                return r.json() if r.status_code == 200 else []
            except requests.RequestException as e:
                logging.error(f"Failed to fetch {url}: {e}")
                return []

        skip_list: list[tuple[str, str, str, Exception]] = []

        # Load raw structure
        self.structure: dict = {}
        for jaar in get_contents():
            if jaar.get("type") == "dir" and str(jaar.get("name", "")).startswith("Jaar"):
                jn: str = jaar["name"]
                self.structure[jn] = {}
                for lvl in get_contents(jn):
                    if lvl.get("type") == "dir":
                        ln: str = lvl["name"]
                        self.structure[jn][ln] = {}
                        for js in get_contents(f"{jn}/{ln}"):
                            if js.get("type") == "file" and str(js.get("name", "")).endswith(".json"):
                                try:
                                    contents: dict[str, dict[str, dict[str, str]]] = requests.get(js["download_url"], timeout=30).json()  # type: ignore[assignment]
                                    vak_name: str = js["name"][:-5]  # removes ".json"
                                    self.structure[jn][ln][vak_name] = contents
                                except (json.JSONDecodeError, requests.RequestException) as e:
                                    skip_list.append((jn, ln, js.get("name", "unknown"), e))

        if skip_list:
            for skip in skip_list:
                logging.warning(
                    f"Skipped invalid JSON file '{skip[0]}/{skip[1]}/{skip[2]}':\n\t{skip[3]}"
                )

        # Filter out paragraphs lacking a proper _meta dict
        for jaar, jaren in list(self.structure.items()):
            for niveau, vakken in list(jaren.items()):
                for vak, chapters in list(vakken.items()):
                    for chapter, paras in list(chapters.items()):
                        filtered: dict[str, dict] = {
                            p: data for p, data in paras.items() if isinstance(data.get("_meta"), dict)
                        }
                        self.structure[jaar][niveau][vak][chapter] = filtered

        logging.info("Done!")

    def setup_music(self) -> None:
        """Initialize Pygame's mixer and start playing silence."""
        logging.info("Running...")
        mixer.init()
        mixer.music.load(resource_path("silence.mp3"))
        mixer.music.set_volume(self.settings_var["music"]["volume"].get() / 100)
        mixer.music.play(loops=-1)
        logging.info("Done!")

    def switch_music(self, type_: str) -> None:
        """Switch to a specific music track ("title" or "cards")."""
        logging.info("Running...")
        if self.current_music == type_:
            return
        mixer.music.stop()

        try:
            music_path = self.settings_var["music"][type_].get()
        except Exception:
            music_path = "silence.mp3"
        full_path: str = resource_path(music_path)

        try:
            mixer.music.load(full_path)
            mixer.music.set_volume(self.settings_var["music"]["volume"].get() / 100)
            mixer.music.play(loops=-1)
            logging.info(f"Now playing '{music_path}'")
        except (FileNotFoundError, pygame.error) as e:
            logging.warning(f"Failed to load '{music_path}': {e}")
            try:
                mixer.music.load(resource_path("silence.mp3"))
                mixer.music.set_volume(self.settings_var["music"]["volume"].get() / 100)
                mixer.music.play(loops=-1)
                logging.info("Fallback to silence.mp3")
            except Exception as fallback_error:
                logging.error(f"Even fallback failed: {fallback_error}")

        self.current_music = type_
        logging.info("Done!")

    def tr(self, key: str) -> str:
        """Translate a UI key into the current language."""
        return self.translations.get(key, key)

    def change(self, menu: typing.Callable[[], None]) -> None:
        """Remove all widgets, adjust music, and call the new menu."""
        logging.info("Running...")
        for widget in root.winfo_children():
            widget.destroy()

        if menu != self.loading:
            if menu not in [self.cards, self.finish]:
                logging.debug("Switching to title music")
                self.switch_music("title")
            else:
                logging.debug("Switching to cards music")
                self.switch_music("cards")

        logging.info(f"Done! (switch to: {menu.__name__})")
        menu()

    # ------ Views ------
    def loading(self) -> None:
        ttk.Label(root, text="Loading...", font=("Impact", 36)).pack(pady=(20, 0))
        ttk.Label(root, text="Please Wait", font=("Arial", 12, "italic")).pack()
        pb = ttk.Progressbar(root, length=600, mode="indeterminate", maximum=100)
        pb.pack(pady=(10, 10))
        pb.start(10)
        ttk.Label(
            root,
            textvariable=self.log_output_var,
            font=("Courier New", 10),
            anchor="w",
            justify="left",
        ).pack(pady=10)
        ttk.Label(
            root,
            text="Copyright © Raoul van Zomeren. All rights reserved.",
            font=("Arial", 10, "italic"),
        ).pack(pady=(10, 0))

    def main(self) -> None:
        ttk.Label(
            root,
            text=f"Flashcards© v{VERSION}{f'-p{PLAYTEST}' if PLAYTEST else ''}",
            font=("Impact", 36),
        ).pack(pady=(20, 0))

        if self.update_available[0]:
            subtitle = ttk.Label(
                root,
                text=f"{self.tr('update_available')} ({VERSION} → {self.update_available[1]})",
                font=("Helvetica", 20, "bold"),
            )
        else:
            subtitle = ttk.Label(root, text=f"{VERSION_NAME}", font=("Helvetica", 24, "bold"))
        subtitle.pack(pady=(0, 5))

        splash = random.choice(self.splashtext_array)
        ttk.Label(root, text=splash, font=("Arial", 12, "italic")).pack(pady=(0, 25))

        ttk.Button(root, text=self.tr("start_game"), command=lambda: self.change(self.setup)).pack()
        ttk.Button(root, text=self.tr("settings"), command=lambda: self.change(self.settings)).pack()
        ttk.Button(root, text=self.tr("quit"), command=self.on_closing).pack(pady=(25, 0))

        ttk.Label(
            root,
            text="Copyright © Raoul van Zomeren. All rights reserved.",
            font=("Arial", 10, "italic"),
        ).pack(pady=(10, 0))

    def settings(self) -> None:
        ttk.Label(root, text=self.tr("settings"), font=("Impact", 36)).pack(pady=(20, 25))

        ttk.Checkbutton(root, text=self.tr("infinite"), variable=self.settings_var["infinite"]).pack()
        ttk.Checkbutton(root, text=self.tr("auto_update"), variable=self.settings_var["auto_update"]).pack()
        ttk.Checkbutton(root, text=self.tr("advanced_setup"), variable=self.settings_var["advanced_setup"]).pack()

        ttk.Frame(root).pack(pady=8)

        ttk.Button(root, text=self.tr("music_settings"), command=lambda: self.change(self.music_config)).pack()
        ttk.Button(root, text=self.tr("download_version"), command=self.select_version).pack()

        ttk.Frame(root).pack(pady=8)

        setup_frame = ttk.Frame(root)

        if self.settings_var["theme"].get() not in ["light", "dark"]:
            self.settings_var["theme"].set("light")
        ttk.Label(setup_frame, text=f"{self.tr('theme')}").grid(row=0, column=0)

        theme_values = list(self.theme_map.values())
        current_internal_theme = self.settings_var["theme"].get()
        current_display_theme = self.theme_map.get(current_internal_theme, theme_values[0])

        self.theme_setting = ttk.Combobox(setup_frame, values=theme_values, state="readonly")
        self.theme_setting.set(current_display_theme)
        self.theme_setting.bind("<<ComboboxSelected>>", self.on_theme)
        self.theme_setting.grid(row=0, column=1)

        ttk.Label(setup_frame, text=f"{self.tr('language')}").grid(row=1, column=0)

        current_code = self.settings_var["language"].get()
        current_display = self.code_to_display.get(current_code, self.available_languages[0] if self.available_languages else current_code)

        self.language_setting = ttk.Combobox(
            setup_frame, values=self.available_languages, state="readonly"
        )
        self.language_setting.set(current_display)
        self.language_setting.bind("<<ComboboxSelected>>", self.on_language)
        self.language_setting.grid(row=1, column=1)

        setup_frame.pack()

        exit_frame = ttk.Frame(root)

        def back():
            logging.debug(f"Settings saved snapshot: {self.settings_var}")
            self.change(self.main)

        ttk.Button(exit_frame, text=self.tr("back"), command=back).grid(row=0, column=1)
        exit_frame.pack(pady=(25, 0))

        ttk.Label(
            root,
            text="Copyright © Raoul van Zomeren. All rights reserved.",
            font=("Arial", 10, "italic"),
        ).pack(pady=(10, 0))

    def select_version(self) -> None:
        popup = tk.Toplevel(root)
        popup.title(self.tr("select_version"))
        popup.geometry("300x400")

        tk.Label(popup, text=self.tr("available_versions"), font=("Helvetica", 12, "bold")).pack(pady=(10, 5))

        versions_list: list[str] = self.get_available_versions()
        logging.info(f"{versions_list}")
        listbox = tk.Listbox(popup, height=15)
        for v in versions_list:
            listbox.insert(tk.END, v)
        listbox.pack(pady=(0, 10))

        def confirm() -> None:
            sel = listbox.curselection()
            if not sel:
                return
            selection = listbox.get(sel[0])
            popup.destroy()
            self.download_version(selection)

        tk.Button(popup, text=self.tr("download"), command=confirm).pack()
        tk.Button(popup, text=self.tr("cancel"), command=popup.destroy).pack()

    def get_available_versions(self) -> list[str]:
        """Return either the 'releases' or 'playtest' list, depending on PLAYTEST flag."""
        logging.info("[get_available_versions] Running...")
        try:
            data: dict = fetch_versions_json()
            key = "playtest" if PLAYTEST else "releases"
            logging.info("[get_available_versions] Done!")
            return data.get("older", {}).get(key, [])
        except Exception as e:
            logging.error(f"[get_available_versions] {e}")
            logging.info("[get_available_versions] Done!")
            return []

    def on_language(self, _event=None) -> None:
        logging.info("Running...")
        selected_display: str = self.language_setting.get()
        selected_code: str = self.display_to_code.get(selected_display, selected_display)
        self.settings_var["language"].set(selected_code)
        self.current_language = selected_code
        self.translations = self.language_data.get(self.current_language, {})
        self.rebuild_theme_map()
        logging.info("Done!")
        self.change(self.settings)

    def on_theme(self, _event=None) -> None:
        logging.info("Running...")
        selected_display: str = self.theme_setting.get()
        selected_internal: str = self.inverse_theme_map.get(selected_display, "light")
        self.settings_var["theme"].set(selected_internal)
        self.apply_theme()
        logging.info("Done!")

    def music_config(self) -> None:
        logging.info("Running...")

        def on_volume(_e=None) -> None:
            vol: float = float(self.volume_scale.get()) / 100
            self.settings_var["music"]["volume"].set(int(vol * 100))
            self.volume_setting_label.config(text=f"{int(vol * 100)}/100")
            mixer.music.set_volume(vol)

        def on_music_select(music_type: typing.Literal["title", "cards"]) -> None:
            filetypes: list[tuple[str, str]] = [(self.tr("music_select_dialogue.files"), "*.mp3 *.wav *.ogg")]
            path: str = filedialog.askopenfilename(title=self.tr("music_select_dialogue"), filetypes=filetypes)
            if not path:
                return
            self.settings_var["music"][music_type].set(path)
            short = os.path.basename(path)
            if music_type == "title":
                self.title_music_label.config(text=f"{self.tr('title_music')} ({short})")
                try:
                    mixer.music.load(path)
                    mixer.music.play(loops=-1)
                except Exception as e:
                    logging.error(f"Error loading title music: {e}")
            else:
                self.cards_music_label.config(text=f"{self.tr('cards_music')} ({short})")

        def on_music_reset(music_type: typing.Literal["title", "cards"]) -> None:
            self.settings_var["music"][music_type].set(resource_path("silence.mp3"))
            if music_type == "title":
                mixer.music.load(self.settings_var["music"][music_type].get())
            self.change(self.music_config)

        ttk.Label(root, text=self.tr("music_settings"), font=("Impact", 36)).pack(pady=(20, 25))

        vol_frame = ttk.Frame(root)
        ttk.Label(vol_frame, text=f"{self.tr('volume')}").grid(row=0, column=0)
        initial: int = int(self.settings_var["music"]["volume"].get())
        self.volume_scale = ttk.Scale(vol_frame, from_=0, to=100, length=500, command=on_volume)
        self.volume_scale.set(initial)
        self.volume_scale.grid(row=0, column=1)
        self.volume_setting_label = ttk.Label(vol_frame, text=f"{initial}/100")
        self.volume_setting_label.grid(row=0, column=2)
        vol_frame.pack(pady=(0, 10))

        select_frame = ttk.Frame(root)
        title_fname = (
            os.path.basename(self.settings_var["music"]["title"].get())
            if not str(self.settings_var["music"]["title"].get()).endswith("silence.mp3")
            else self.tr("none")
        )
        self.title_music_label = ttk.Label(
            select_frame, text=f"{self.tr('title_music')} ({title_fname})"
        )
        self.title_music_label.grid(row=0, column=0, sticky="w")
        ttk.Button(select_frame, text=self.tr("select_file"), command=lambda: on_music_select("title")).grid(row=0, column=1)
        ttk.Button(select_frame, text=self.tr("reset_file"), command=lambda: on_music_reset("title")).grid(row=0, column=2)

        cards_fname = (
            os.path.basename(self.settings_var["music"]["cards"].get())
            if not str(self.settings_var["music"]["cards"].get()).endswith("silence.mp3")
            else self.tr("none")
        )
        self.cards_music_label = ttk.Label(
            select_frame, text=f"{self.tr('cards_music')} ({cards_fname})"
        )
        self.cards_music_label.grid(row=1, column=0, sticky="w")
        ttk.Button(select_frame, text=self.tr("select_file"), command=lambda: on_music_select("cards")).grid(row=1, column=1)
        ttk.Button(select_frame, text=self.tr("reset_file"), command=lambda: on_music_reset("cards")).grid(row=1, column=2)

        select_frame.pack(pady=(0, 0))

        ttk.Button(root, text=self.tr("back"), command=lambda: self.change(self.settings)).pack(pady=(25, 0))
        logging.info("Done!")

    def setup(self) -> None:
        ttk.Label(root, text=self.tr("setup"), font=("Impact", 36)).pack(pady=(20, 25))
        self.resync_setup_values(True)

        select_frame = ttk.Frame(root)
        ttk.Label(select_frame, text=f"{self.tr('grade')}").grid(row=0, column=0)
        self.jaar_select = ttk.Combobox(
            select_frame, values=self.jaar_values, state="readonly" if self.jaar_values else "disabled"
        )
        self.jaar_select.set(self.last_jaar)
        self.jaar_select.bind("<<ComboboxSelected>>", self.on_jaar_select)
        self.jaar_select.grid(row=0, column=1)

        ttk.Label(select_frame, text=f"{self.tr('educational-level')}").grid(row=1, column=0)
        self.niveau_select = ttk.Combobox(
            select_frame, values=self.niveau_values, state="readonly" if self.niveau_values else "disabled"
        )
        self.niveau_select.set(self.last_niveau)
        self.niveau_select.bind("<<ComboboxSelected>>", self.on_niveau_select)
        self.niveau_select.grid(row=1, column=1)

        ttk.Label(select_frame, text=f"{self.tr('subject')}").grid(row=2, column=0)
        self.vak_select = ttk.Combobox(
            select_frame, values=self.vak_values, state="readonly" if self.vak_values else "disabled"
        )
        self.vak_select.set(self.last_vak)
        self.vak_select.bind("<<ComboboxSelected>>", self.on_vak_select)
        self.vak_select.grid(row=2, column=1)

        ttk.Frame(select_frame).grid(row=3, column=0, columnspan=2, pady=8)

        ttk.Label(select_frame, text=self.tr("chapter")).grid(row=4, column=0)
        self.chapter_select = tk.Listbox(
            select_frame,
            state="normal" if self.chapter_values else "disabled",
            selectmode="single",
            exportselection=False,
            bg=self.bg,
            fg=self.fg,
            highlightbackground=self.highlight,
            selectbackground=self.highlight,
        )
        if self.chapter_values:
            for value in self.chapter_values:
                self.chapter_select.insert(tk.END, value)
        self.chapter_select.bind("<<ListboxSelect>>", self.on_chapter_select)
        self.chapter_select.grid(row=5, column=0)

        ttk.Label(select_frame, text=self.tr("paragraph")).grid(row=4, column=1)
        self.paragraph_select = tk.Listbox(
            select_frame,
            state="disabled",
            selectmode="multiple",
            exportselection=False,
            bg=self.bg,
            fg=self.fg,
            highlightbackground=self.highlight,
            selectbackground=self.highlight,
        )
        self.paragraph_select.bind("<<ListboxSelect>>", self.on_paragraph_select)
        self.paragraph_select.grid(row=5, column=1)

        select_frame.pack(pady=(15, 0))

        navigation_frame = ttk.Frame(root)
        ttk.Button(navigation_frame, text=self.tr("back"), command=lambda: self.change(self.main)).grid(row=0, column=0)
        self.continue_button = ttk.Button(
            navigation_frame, text=self.tr("continue"), state="disabled", command=self.on_continue_setup
        )
        self.continue_button.grid(row=0, column=1)
        navigation_frame.pack(pady=(25, 0))

        ttk.Label(
            root,
            text="Copyright © Raoul van Zomeren. All rights reserved.",
            font=("Arial", 10, "italic"),
        ).pack(pady=(10, 0))

    def resync_setup_values(self, initial: bool = False) -> None:
        logging.info("Running...")
        if initial:
            self.last_jaar: str = self.settings_var["last_session"]["jaar"].get()
            self.last_niveau: str = self.settings_var["last_session"]["niveau"].get()
            self.last_vak: str = self.settings_var["last_session"]["vak"].get()

        self.jaar_values = list(self.structure.keys())
        self.niveau_values: list[str] = []
        self.vak_values: list[str] = []
        self.chapter_values: list[str] = []
        if self.last_jaar in self.structure:
            self.niveau_values = list(self.structure[self.last_jaar].keys())
            self.settings_var["last_session"]["jaar"].set(self.last_jaar)
            if self.last_niveau in self.structure[self.last_jaar]:
                self.vak_values = list(self.structure[self.last_jaar][self.last_niveau].keys())
                self.settings_var["last_session"]["niveau"].set(self.last_niveau)
                if self.last_vak in self.structure[self.last_jaar][self.last_niveau]:
                    self.chapter_values = list(
                        self.structure[self.last_jaar][self.last_niveau][self.last_vak].keys()
                    )
                    self.settings_var["last_session"]["vak"].set(self.last_vak)
                elif self.last_vak != "Selecteer schoolvak":
                    self.last_vak = "Selecteer schoolvak"
                    self.settings_var["last_session"]["vak"].set(self.last_vak)
                    logging.debug(
                        f"'{self.last_vak}' not in '{list(self.structure[self.last_jaar][self.last_niveau].keys())}'"
                    )
            elif self.last_niveau != "Selecteer onderwijsniveau":
                self.last_niveau = "Selecteer onderwijsniveau"
                self.settings_var["last_session"]["niveau"].set(self.last_niveau)
                self.last_vak = "Selecteer leerjaar"
                self.settings_var["last_session"]["vak"].set(self.last_vak)
                logging.debug(
                    f"'{self.last_niveau}' not in '{list(self.structure[self.last_jaar].keys())}'"
                )
        elif self.last_jaar != "Selecteer leerjaar":
            self.last_jaar = "Selecteer leerjaar"
            self.settings_var["last_session"]["jaar"].set(self.last_jaar)
            self.last_niveau = "Selecteer onderwijsniveau"
            self.settings_var["last_session"]["niveau"].set(self.last_niveau)
            self.last_vak = "Selecteer schoolvak"
            self.settings_var["last_session"]["vak"].set(self.last_vak)
            logging.debug(f"'{self.last_jaar}' not in '{list(self.structure.keys())}'")
        logging.info("Done!")

    def on_jaar_select(self, _event: tk.Event) -> None:
        logging.info("Running...")
        self.last_jaar = self.jaar_select.get()
        self.niveau_select.config(state="readonly")
        self.niveau_select.set("Selecteer onderwijsniveau")
        self.niveau_select["values"] = list(self.structure[self.last_jaar].keys())
        self.vak_select["values"] = []
        self.vak_select.set("Selecteer schoolvak")
        self.vak_select.config(state="disabled")
        self.chapter_select.delete(0, tk.END)
        self.chapter_select.config(state="disabled")
        self.paragraph_select.delete(0, tk.END)
        self.paragraph_select.config(state="disabled")
        logging.debug(f"jaar_select.get() = {self.jaar_select.get()}")
        self.resync_setup_values()
        logging.info("Done!")

    def on_niveau_select(self, _event: tk.Event) -> None:
        logging.info("Running...")
        self.last_niveau = self.niveau_select.get()
        self.vak_select.config(state="readonly")
        self.vak_select.set("Selecteer schoolvak")
        self.vak_select["values"] = list(self.structure[self.last_jaar][self.last_niveau].keys())
        self.chapter_select.delete(0, tk.END)
        self.chapter_select.config(state="disabled")
        self.paragraph_select.delete(0, tk.END)
        self.paragraph_select.config(state="disabled")
        self.resync_setup_values()
        logging.info("Done!")

    def on_vak_select(self, _event: tk.Event) -> None:
        logging.info("Running...")
        self.last_vak = self.vak_select.get()
        self.chapter_select.config(state="normal")
        self.chapter_select.delete(0, tk.END)
        for value in list(self.structure[self.last_jaar][self.last_niveau][self.last_vak].keys()):
            self.chapter_select.insert(tk.END, value)
        self.paragraph_select.delete(0, tk.END)
        self.paragraph_select.config(state="disabled")
        self.resync_setup_values()
        logging.info("Done!")

    def on_chapter_select(self, event: tk.Event) -> None:
        logging.info("Running...")
        sel = event.widget.curselection() # type: ignore
        if not sel:
            return
        self.selected_chapter = self.chapter_select.get(sel[0])
        self.paragraph_select.config(state="normal")
        self.paragraph_select.delete(0, tk.END)
        self.selected_paragraphs: list[str] = []
        for value in list(
            self.structure[self.last_jaar][self.last_niveau][self.last_vak][self.selected_chapter].keys()
        ):
            self.paragraph_select.insert(tk.END, value)
        self.resync_setup_values()
        logging.info("Done!")

    def on_paragraph_select(self, _event: tk.Event) -> None:
        logging.info("Running...")
        self.selected_paragraphs = [self.paragraph_select.get(i) for i in self.paragraph_select.curselection()]
        self.continue_button.config(state="normal" if self.selected_paragraphs else "disabled")
        self.resync_setup_values()
        logging.info("Done!")

    def on_continue_setup(self):
        if self.settings_var["advanced_setup"].get():
            self.change(self.advanced_setup)
        else:
            self.cards_setup()

    # ------ Advanced Setup Menu ------
    def advanced_setup(self) -> None:
        ttk.Label(root, text=self.tr("advanced_setup"), font=("Impact", 36)).pack(pady=(20, 10))
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=50, pady=10)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        meta_paras = [
            p
            for p in self.selected_paragraphs
            if isinstance(
                self.structure[self.last_jaar][self.last_niveau][self.last_vak][self.selected_chapter][p].get("_meta"),
                dict,
            )
        ]
        self.meta_list = tk.Listbox(main, exportselection=False, height=10)
        for p in meta_paras:
            self.meta_list.insert(tk.END, p)
        self.meta_list.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        edit_frame = ttk.Frame(main)
        edit_frame.grid(row=0, column=1, sticky="nsew")

        self.temp_flip_override: dict[str, tk.BooleanVar] = {}
        for p in meta_paras:
            dd = (
                self.structure[self.last_jaar][self.last_niveau][self.last_vak][self.selected_chapter][p]
            )
            self.temp_flip_override[p] = tk.BooleanVar(
                root, bool(dd["_meta"].get("flip", False))
            )

        def on_meta_select(_evt=None):
            for child in edit_frame.winfo_children():
                child.destroy()
            sel = self.meta_list.curselection()
            if not sel:
                return
            name = self.meta_list.get(sel[0])
            ttk.Label(edit_frame, text=name, font=("Helvetica", 14, "bold")).pack(anchor="center", pady=(0, 5))
            ttk.Checkbutton(edit_frame, text=self.tr("both_ways"), variable=self.temp_flip_override[name]).pack()

        self.meta_list.bind("<<ListboxSelect>>", on_meta_select)

        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=(10, 20))
        ttk.Button(btn_frame, text=self.tr("back"), command=lambda: self.change(self.setup)).grid(row=0, column=0, padx=10)
        ttk.Button(btn_frame, text=self.tr("continue"), command=self.cards_setup).grid(row=0, column=1, padx=10)

    # ------ Cards Logic & Gameplay ------
    def cards_setup(self) -> None:
        logging.info("Running...")
        self.build_deck()
        if len(self.deck) > 100:
            logging.info("Deck contains over 100 cards.")
            if not messagebox.askokcancel(
                "Large deck", "Your chosen deck contains over 100 cards.\nDo you wish to continue anyways?"
            ):
                logging.info("Cancelled large deck")
                self.change(self.setup)
                return
        logging.info("Done!")
        self.change(self.cards)

    def build_deck(self) -> None:
        logging.info("Running...")
        paragraphs = self.structure[self.last_jaar][self.last_niveau][self.last_vak][self.selected_chapter]
        deck_one: list[tuple[str, str]] = []
        deck_two: list[tuple[str, str]] = []

        for key, data in paragraphs.items():
            if key not in self.selected_paragraphs:
                continue

            flip_var = getattr(self, "temp_flip_override", {}).get(key)
            if flip_var is not None:
                flip = bool(flip_var.get())
            else:
                flip = bool(data.get("_meta", {}).get("flip", True))

            for q, a in data.items():
                if q == "_meta":
                    continue
                deck_one.append((q, a))
                deck_two.append((a, q) if flip else (q, a))

        random.shuffle(deck_one)
        random.shuffle(deck_two)

        self.deck: list[tuple[str, str]] = deck_one + deck_two
        self.total_cards = len(self.deck)
        self.log_correct: list[tuple[str, str]] = []
        self.log: list[tuple[str, str]] = []
        self.side = 0
        self.flipped = False
        logging.info("Done!")

    def cards(self) -> None:
        ttk.Label(root, text=self.tr("flashcards"), font=("Impact", 36)).pack(pady=(20, 25))
        self.progress_bar = ttk.Progressbar(root, length=WIDTH - 200, mode="determinate", maximum=len(self.deck))
        self.progress_bar.pack()

        card_label_frame = ttk.Frame(root, height=200)
        self.card_label = ttk.Label(
            card_label_frame, text=self.deck[0][0], font=("Arial", 20), wraplength=WIDTH - 100
        )
        self.card_label.pack(anchor="n", padx=(20, 20), pady=(20, 20))
        card_label_frame.pack()

        self.flip_button = ttk.Button(root, text=self.tr("flip"), command=self.on_flip)
        self.flip_button.pack()

        judgement_frame = ttk.Frame(root)
        self.correct_button = ttk.Button(judgement_frame, text=self.tr("correct"), command=self.on_correct)
        self.wrong_button = ttk.Button(judgement_frame, text=self.tr("incorrect"), command=self.on_wrong)
        if DEV_MODE:
            self.correct_button.grid(row=0, column=0)
            self.wrong_button.grid(row=0, column=1)
        judgement_frame.pack()

        ttk.Button(root, text=self.tr("exit"), command=self.on_cards_exit).pack(pady=(25, 0))
        ttk.Label(
            root,
            text="Copyright © Raoul van Zomeren. All rights reserved.",
            font=("Arial", 10, "italic"),
        ).pack(pady=(10, 0))

    def on_flip(self) -> None:
        logging.info("Running...")
        self.flipped = True
        self.side = 1 if self.side == 0 else 0
        logging.debug(f"self.side = {self.side}")
        self.card_label.config(text=self.deck[0][self.side])
        self.correct_button.grid(row=0, column=0)
        self.wrong_button.grid(row=0, column=1)
        logging.info("Done!")

    def on_correct(self) -> None:
        logging.info("Running...")
        if self.deck[0] in self.log or (self.deck[0][1], self.deck[0][0]) in self.log:
            self.log_correct.append(self.deck[0])
            logging.debug(f"Card {self.deck[0]} added to log_correct.")
        else:
            self.log.append(self.deck[0])
            logging.debug(f"Card {self.deck[0]} added to log.")
        self.deck.pop(0)

        self.side = 0
        self.flipped = False
        self.progress_bar["value"] = int(self.progress_bar["value"]) + 1
        logging.info(
            f"progress: {self.progress_bar['value']}/{self.progress_bar['maximum']}"
        )

        if len(self.deck) > 0:
            self.card_label.config(text=self.deck[0][0])
            if not DEV_MODE:
                self.correct_button.grid_remove()
                self.wrong_button.grid_remove()
        else:
            self.change(self.finish)
        logging.info("Done!")

    def on_wrong(self) -> None:
        logging.info("Running...")
        if not self.settings_var["infinite"].get():
            self.deck.pop(0)
            self.progress_bar["value"] = int(self.progress_bar["value"]) + 1
        else:
            self.deck.append(self.deck.pop(0))
        self.side = 0
        self.flipped = False
        if len(self.deck) > 0:
            self.card_label.config(text=self.deck[0][0])
            if not DEV_MODE:
                self.correct_button.grid_remove()
                self.wrong_button.grid_remove()
        else:
            self.change(self.finish)
        logging.info("Done!")

    def on_cards_exit(self) -> None:
        logging.info("Running...")
        if messagebox.askyesno("Confirm exit", "Are you sure you want to exit?\nYour progess won't be saved."):
            logging.info("Confirmed exit")
            self.change(self.main)
        else:
            logging.info("Cancelled exit")
        logging.info("Done!")

    def finish(self) -> None:
        ttk.Label(root, text=self.tr("finish"), font=("Impact", 36)).pack(pady=(20, 25))
        # total_cards is doubled because of flips; divide by 2 for score denominator
        denom = max(1, self.total_cards // 2)
        pct = int((len(self.log_correct) / denom) * 1000) / 10
        ttk.Label(
            root,
            text=f"{self.tr('score')} {len(self.log_correct)}/{denom} ({pct}%)",
            font=("Arial", 20),
        ).pack()

        navigation_frame = ttk.Frame(root)
        ttk.Button(navigation_frame, text=self.tr("exit"), command=lambda: self.change(self.main)).grid(row=0, column=0)
        ttk.Button(navigation_frame, text=self.tr("retry"), command=lambda: self.change(self.setup)).grid(row=0, column=1)
        navigation_frame.pack(pady=(25, 0))

        ttk.Label(
            root,
            text="Copyright © Raoul van Zomeren. All rights reserved.",
            font=("Arial", 10, "italic"),
        ).pack(pady=(10, 0))

    def on_closing(self, force: bool = False) -> None:
        logging.info("Running...")
        if not force:
            try:
                with open("settings.json", "w", encoding="utf-8") as f:
                    json.dump(serialize_settings(self.settings_var), f, indent=4, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Failed to save settings: {e}")
        root.destroy()
        logging.info("Done!")


# ------ Program Start ------
if __name__ == "__main__":
        program = Menu()
        root.protocol("WM_DELETE_WINDOW", program.on_closing)
        tk.mainloop()