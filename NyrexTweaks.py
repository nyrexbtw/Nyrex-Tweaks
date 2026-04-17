import customtkinter as ctk
import json
import threading
import subprocess
import os
import sys
import ctypes
import math
import tkinter as _tk
from tkinter import Canvas

# pil for icons, not required
try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

myappid = 'nyrex.tweaks.v2'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# colors lol
C_ROOT          = "#040000"   # window root bg
C_BG            = "#070000"   # main content background
C_SIDEBAR       = "#090101"   # sidebar bg — very slightly lighter than bg
C_SIDEBAR_SEP   = "#2E0808"   # sidebar right-border
C_TITLEBAR      = "#030000"   # title bar strip
C_TITLEBAR_SEP  = "#1E0505"   # title bar bottom line

C_NAV_HOVER     = "#160303"   # nav button hover
C_NAV_ACTIVE    = "#2E0808"   # nav active background
C_NAV_ACTIVE_BD = "#5A0E0E"   # nav active border
C_NAV_INDICATOR = "#CC1111"   # left active indicator bar

C_CARD          = "#0E0101"   # card background
C_CARD_BORDER   = "#220404"   # card default border — more visible
C_CARD_HOVER    = "#160202"   # card hover bg
C_CARD_HOVER_BD = "#5A0E0E"   # card hover border
C_CARD_RUNNING  = "#CC1111"   # running red

C_ACCENT        = "#CC1111"   # primary red accent
C_ACCENT_MID    = "#D42020"   # medium red
C_ACCENT_BRIGHT = "#FF4444"   # bright red / highlights
C_ACCENT_DIM    = "#200505"   # dark red fill — button bg

C_SUCCESS       = "#7A1010"   # border color on success/fail
C_FAIL          = "#7A1010"

C_TEXT_TITLE    = "#F8EEEE"   # near-white, warm
C_TEXT_BODY     = "#8A4444"   # description text — warm muted
C_TEXT_DIM      = "#6A2E2E"   # inactive nav labels
C_TEXT_MID      = "#7A3838"   # mid-tone

C_DIVIDER       = "#1C0404"   # divider lines
C_SCROLLBAR     = "#5A0E0E"   # scrollbar

# fonts
F_CARD_TITLE   = ("Segoe UI Semibold", 14)
F_CARD_DESC    = ("Segoe UI", 10)
F_CARD_STATUS  = ("Consolas", 9)
F_CARD_BTN     = ("Segoe UI", 9, "bold")
F_PAGE_TITLE   = ("Segoe UI", 14, "bold")
F_SECTION      = ("Consolas", 9, "bold")
F_NAV          = ("Segoe UI", 10, "bold")
F_BADGE_VAL    = ("Consolas", 14, "bold")
F_BADGE_LBL    = ("Segoe UI", 7, "bold")

CARD_H         = 92    # px
SIDEBAR_W      = 232
TITLEBAR_H     = 36

def resource_path(rel):
    """
    Resolve a resource path that works both:
    - When running as a .py script  -> uses the script's own directory
    - When compiled with PyInstaller -> uses _MEIPASS temp folder
    """
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def lerp(c1, c2, t):
    r1,g1,b1 = int(c1[1:3],16),int(c1[3:5],16),int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16),int(c2[3:5],16),int(c2[5:7],16)
    return f"#{int(r1+(r2-r1)*t):02X}{int(g1+(g2-g1)*t):02X}{int(b1+(b2-b1)*t):02X}"


class PulsingDot(Canvas):
    def __init__(self, master, color=C_ACCENT_MID, bg=C_CARD, size=8):
        super().__init__(master, width=size, height=size,
                         bg=bg, highlightthickness=0, bd=0)
        self._c = color; self._bg = bg
        self._s = size;  self._t = 0; self._on = False
        self._o = self.create_oval(1,1,size-1,size-1, fill=color, outline="")

    def start(self):
        self._on = True; self._tick()

    def stop(self):
        self._on = False

    def _tick(self):
        if not self._on: return
        self._t += 0.14
        a = (math.sin(self._t)+1)/2
        self.itemconfig(self._o, fill=lerp(self._bg, self._c, 0.25 + a*0.75))
        p = 1+(1-a)*2; s = self._s
        self.coords(self._o, p, p, s-p, s-p)
        try: self.after(40, self._tick)
        except Exception: pass


class Hr(ctk.CTkFrame):
    def __init__(self, master, color=C_DIVIDER, **kw):
        super().__init__(master, height=1, fg_color=color, **kw)


# row heights, tweak these if fonts change
_ROW_TITLE  = 22
_ROW_DESC   = 16
_ROW_GAP    = 5
_ROW_STATUS = 15
_ROW_SGAP   = 6

class TweakCard(ctk.CTkFrame):
    """
    Fixed-height card. All text rows are placed at mathematically computed
    Y positions — no pack(), no winfo_reqheight(), no timing races.
    Layout is recalculated any time the card resizes OR status visibility changes.
    States: idle -> running -> done (success) | failed (retryable)
    """
    def __init__(self, master, name, description, commands):
        super().__init__(master,
                         height=CARD_H,
                         fg_color=C_CARD,
                         border_color=C_CARD_BORDER,
                         border_width=1,
                         corner_radius=10)
        self.pack_propagate(False)
        self.commands = commands
        self._state   = "idle"
        self._status_visible = False

        self.btn = ctk.CTkButton(self,
                                 text="APPLY",
                                 width=78, height=32,
                                 corner_radius=8,
                                 fg_color=C_ACCENT_DIM,
                                 border_color=C_NAV_ACTIVE_BD,
                                 border_width=1,
                                 hover_color=C_NAV_ACTIVE,
                                 font=F_CARD_BTN,
                                 text_color=C_ACCENT_BRIGHT,
                                 command=self._apply)
        self.btn.place(relx=1.0, rely=0.5, x=-18, anchor="e")

        # plain tk frame because ctk doesnt allow width/height in place()
        self._wrap = _tk.Frame(self, bg=C_CARD, bd=0, highlightthickness=0)

        # title
        self._row_title = _tk.Frame(self._wrap, bg=C_CARD, bd=0, highlightthickness=0)
        self._title_lbl = ctk.CTkLabel(self._row_title,
                                        text=name,
                                        font=F_CARD_TITLE,
                                        text_color=C_TEXT_TITLE,
                                        anchor="w",
                                        fg_color="transparent")
        self._title_lbl.place(x=0, y=0, relwidth=1, relheight=1)

        # desc
        self._row_desc = _tk.Frame(self._wrap, bg=C_CARD, bd=0, highlightthickness=0)
        self._desc_lbl = ctk.CTkLabel(self._row_desc,
                                       text=description,
                                       font=F_CARD_DESC,
                                       text_color=C_TEXT_BODY,
                                       wraplength=560,
                                       justify="left",
                                       anchor="w",
                                       fg_color="transparent")
        self._desc_lbl.place(x=0, y=0, relwidth=1, relheight=1)

        # status, hidden until something runs
        self._row_status = _tk.Frame(self._wrap, bg=C_CARD, bd=0, highlightthickness=0)
        self._dot = PulsingDot(self._row_status, color=C_CARD_RUNNING, bg=C_CARD)
        self._dot.place(x=0, y=3, width=9, height=9)
        self._status_lbl = ctk.CTkLabel(self._row_status,
                                         text="",
                                         font=F_CARD_STATUS,
                                         text_color=C_TEXT_MID,
                                         anchor="w",
                                         fg_color="transparent")
        self._status_lbl.place(x=14, y=0, relwidth=1, relheight=1)

        self.bind("<Configure>", self._reposition)

        for w in (self, self.btn, self._wrap,
                  self._row_title, self._row_desc, self._row_status):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _reposition(self, e=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            self.after(20, self._reposition); return

        LEFT  = 16
        RIGHT = w - 78 - 24
        TW    = max(100, RIGHT - LEFT)

        self._desc_lbl.configure(wraplength=max(200, TW - 10))

        # taller when status is visible
        if self._status_visible:
            total = _ROW_TITLE + _ROW_GAP + _ROW_DESC + _ROW_SGAP + _ROW_STATUS
        else:
            total = _ROW_TITLE + _ROW_GAP + _ROW_DESC

        # center it
        top = (h - total) // 2

        
        self._wrap.place(x=LEFT, y=top, width=TW, height=total)

        
        y = 0
        self._row_title.place(x=0, y=y, width=TW, height=_ROW_TITLE)
        y += _ROW_TITLE + _ROW_GAP
        self._row_desc.place(x=0, y=y, width=TW, height=_ROW_DESC)
        if self._status_visible:
            y += _ROW_DESC + _ROW_SGAP
            self._row_status.place(x=0, y=y, width=TW, height=_ROW_STATUS)

    def _sync_bg(self, bg):
        for w in (self._wrap, self._row_title, self._row_desc, self._row_status):
            w.configure(bg=bg)
        self._dot.configure(bg=bg)

    def _on_enter(self, _=None):
        if self._state == "idle":
            self.configure(fg_color=C_CARD_HOVER, border_color=C_CARD_HOVER_BD)
            self._sync_bg(C_CARD_HOVER)
        elif self._state == "failed":
            self.configure(fg_color=C_CARD_HOVER, border_color=C_FAIL)
            self._sync_bg(C_CARD_HOVER)

    def _on_leave(self, _=None):
        if self._state == "idle":
            self.configure(fg_color=C_CARD, border_color=C_CARD_BORDER)
            self._sync_bg(C_CARD)
        elif self._state == "failed":
            self.configure(fg_color=C_CARD, border_color=C_FAIL)
            self._sync_bg(C_CARD)

    def _show_status(self, text, color):
        self._status_lbl.configure(text=text, text_color=color)
        self._status_visible = True
        self._reposition()


    def _apply(self):
        self._state = "running"
        self.configure(fg_color=C_CARD, border_color=C_ACCENT, border_width=1)
        self._sync_bg(C_CARD)
        self.btn.configure(state="disabled", text="...",
                           fg_color=C_ACCENT_DIM,
                           border_color=C_NAV_ACTIVE_BD, border_width=1,
                           text_color=C_TEXT_DIM)
        self._dot._c = C_CARD_RUNNING
        self._dot.itemconfig(self._dot._o, fill=C_CARD_RUNNING)
        self._show_status("RUNNING...", C_TEXT_MID)
        self._dot.start()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        ok, err = True, ""
        for cmd in self.commands:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True)
                if r.returncode != 0:
                    raw = r.stderr.strip()
                    decoded = ""
                    for enc in ("utf-8", "cp866", "cp1251", "latin-1"):
                        try:
                            decoded = raw.decode(enc); break
                        except Exception:
                            pass
                    if not decoded:
                        decoded = raw.decode("latin-1", errors="replace")
                    ok, err = False, decoded or f"Exit {r.returncode}"; break
            except Exception as ex:
                ok, err = False, str(ex); break
        self.after(0, lambda: self._finish(ok, err))

    def _finish(self, ok, err):
        self._dot.stop()
        if ok:
            self._state = "done"
            self._dot._c = C_ACCENT_BRIGHT
            self._sync_bg(C_CARD)
            self._dot.itemconfig(self._dot._o, fill=C_ACCENT_BRIGHT)
            self._show_status("APPLIED SUCCESSFULLY", C_ACCENT_BRIGHT)
            self.configure(fg_color=C_CARD, border_color=C_SUCCESS, border_width=1)
            self.btn.configure(text="DONE",
                               fg_color=C_ACCENT_DIM,
                               text_color=C_ACCENT_BRIGHT,
                               border_color=C_NAV_ACTIVE_BD,
                               border_width=1,
                               state="normal",
                               hover_color=C_ACCENT_DIM,
                               command=lambda: None)
        else:
            self._state = "failed"
            self._dot._c = C_ACCENT_BRIGHT
            self._sync_bg(C_CARD)
            self._dot.itemconfig(self._dot._o, fill=C_ACCENT_BRIGHT)
            self._show_status(f"FAILED: {err[:60]}", C_ACCENT_BRIGHT)
            self.configure(fg_color=C_CARD, border_color=C_FAIL, border_width=1)
            self.btn.configure(text="RETRY",
                               fg_color=C_ACCENT_DIM,
                               text_color=C_ACCENT_BRIGHT,
                               border_color=C_NAV_ACTIVE_BD,
                               border_width=1,
                               hover_color=C_NAV_ACTIVE,
                               state="normal")
_icon_cache = {}

def _make_white(im):
    """
    Convert any PNG/image to pure white with the original alpha channel.
    This means dark icons, coloured icons, anything — all become white
    silhouettes that look clean on the dark red sidebar.
    """
    im = im.convert("RGBA")
    r, g, b, a = im.split()
    # white silhouette, keep the alpha
    white_r = r.point(lambda _: 255)
    white_g = g.point(lambda _: 255)
    white_b = b.point(lambda _: 255)
    return Image.merge("RGBA", (white_r, white_g, white_b, a))


def load_icon(page_id, size=18):
    """
    Load icons/<page_id>.png (or jpg/jpeg/webp) from the same folder
    as the script, force them to white, cache, and return a CTkImage.
    Prints debug info so you can see exactly what path is tried.
    """
    if not _PIL:
            return None
    if page_id in _icon_cache:
        return _icon_cache[page_id]

    icons_dir = resource_path("icons")

    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(icons_dir, f"{page_id}.{ext}")
        if os.path.exists(p):
            try:
                im  = Image.open(p).resize((size, size), Image.LANCZOS)
                im  = _make_white(im)   # force white silhouette
                ci  = ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))
                _icon_cache[page_id] = ci
                return ci
            except Exception:
                pass

    _icon_cache[page_id] = None
    return None


class NavButton(ctk.CTkFrame):
    """
    Custom nav button: active indicator bar on left + text/icon.
    Using a Frame wrapper lets us draw the indicator without hacking CTkButton.
    """
    BTN_H = 38

    def __init__(self, master, label, icon_char, cmd, page_id=None):
        super().__init__(master, fg_color="transparent", height=self.BTN_H)
        self.pack_propagate(False)
        self._cmd     = cmd
        self._active  = False

        # the red bar on the left when active
        self._bar = ctk.CTkFrame(self, width=3, fg_color="transparent", corner_radius=2)
        self._bar.pack(side="left", fill="y", padx=(3, 0))

        # nav button
        img = load_icon(page_id) if page_id else None
        kw  = dict(
            text         = f" {label}" if img else f" {icon_char}  {label}",
            command      = cmd,
            height       = self.BTN_H,
            corner_radius= 8,
            fg_color     = "transparent",
            text_color   = C_TEXT_DIM,
            hover_color  = C_NAV_HOVER,
            font         = F_NAV,
            anchor       = "w",
            border_width = 0,
        )
        if img:
            kw["image"]    = img
            kw["compound"] = "left"
            kw["text"]     = f"  {label}"   # extra space after icon
        self._btn = ctk.CTkButton(self, **kw)
        self._btn.pack(side="left", fill="both", expand=True, padx=(4, 6))

        self.bind("<Enter>", lambda _: self._btn.configure(
            fg_color=C_NAV_HOVER if not self._active else C_NAV_ACTIVE))
        self.bind("<Leave>",  lambda _: self._btn.configure(
            fg_color=C_NAV_ACTIVE if self._active else "transparent"))

    def set_active(self, active):
        self._active = active
        if active:
            self._bar.configure(fg_color=C_NAV_INDICATOR)
            self._btn.configure(fg_color=C_NAV_ACTIVE, text_color=C_TEXT_TITLE,
                                hover_color=C_NAV_ACTIVE)
        else:
            self._bar.configure(fg_color="transparent")
            self._btn.configure(fg_color="transparent", text_color=C_TEXT_DIM,
                                hover_color=C_NAV_HOVER)


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, text):
        super().__init__(master, fg_color="transparent")
        # dot
        ctk.CTkLabel(self, text="・",
                     font=("Segoe UI", 14), text_color=C_ACCENT_MID).pack(side="left", padx=(0, 4))
        # text
        ctk.CTkLabel(self, text=text.upper(),
                     font=F_SECTION, text_color=C_ACCENT_BRIGHT).pack(side="left")
        # line that fills remaining space
        Hr(self, color=C_DIVIDER).pack(side="left", fill="x", expand=True, padx=(12, 0))


class StatBadge(ctk.CTkFrame):
    def __init__(self, master, label, value):
        super().__init__(master,
                         fg_color=C_NAV_ACTIVE,
                         border_color=C_NAV_ACTIVE_BD,
                         border_width=1,
                         corner_radius=10)
        ctk.CTkLabel(self, text=value,
                     font=F_BADGE_VAL, text_color=C_ACCENT_BRIGHT).pack(pady=(8,0))
        ctk.CTkLabel(self, text=label,
                     font=F_BADGE_LBL, text_color=C_TEXT_DIM).pack(pady=(0,8))



class TitleBar(ctk.CTkFrame):
    def __init__(self, master, on_close):
        super().__init__(master,
                         height=TITLEBAR_H,
                         fg_color=C_TITLEBAR,
                         corner_radius=0)
        self.pack_propagate(False)
        self._win = master
        self._dx = self._dy = 0

        self._exit = _tk.Label(self,
                               text="✕",
                               bg=C_TITLEBAR,
                               fg="#4A1A1A",
                               font=("Segoe UI", 10),
                               padx=12, pady=0,
                               cursor="hand2")
        self._exit.place(relx=1.0, rely=0.5, anchor="e", x=-2)
        self._exit.bind("<Button-1>", lambda e: on_close())
        self._exit.bind("<Enter>",    lambda e: self._exit.configure(fg="#CC3333"))
        self._exit.bind("<Leave>",    lambda e: self._exit.configure(fg="#4A1A1A"))

        self._lbl = ctk.CTkLabel(self,
                                  text="NYREX  TWEAKS",
                                  font=("Segoe UI", 9, "bold"),
                                  text_color=C_TEXT_MID)
        self._lbl.place(relx=0.5, rely=0.5, anchor="center")

        Hr(self, color=C_TITLEBAR_SEP).place(relx=0, rely=1.0, relwidth=1, y=-1)

        for w in (self, self._lbl):
            w.bind("<ButtonPress-1>", self._press)
            w.bind("<B1-Motion>",     self._drag)

    def _press(self, e):
        self._dx = e.x_root - self._win.winfo_x()
        self._dy = e.y_root - self._win.winfo_y()

    def _drag(self, e):
        self._win.geometry(f"+{e.x_root-self._dx}+{e.y_root-self._dy}")


class DotGrid(Canvas):
    SPACING = 32   # slightly wider spacing

    def __init__(self, master):
        super().__init__(master, bg=C_BG, highlightthickness=0, bd=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._draw)
        master.after(1, lambda: self.tk.call('lower', self._w))

    def _draw(self, e):
        self.delete("g")
        s = self.SPACING
        DOT_COLOR = "#250505"   # ・ style dot, subtle on near-black
        for x in range(s // 2, e.width, s):
            for y in range(s // 2, e.height, s):
                self.create_oval(x-1, y-1, x+2, y+2,
                                 fill=DOT_COLOR, outline="", tags="g")


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, title, count):
        super().__init__(master, height=58, fg_color=C_SIDEBAR, corner_radius=0)
        self.pack_propagate(False)

        # red bar on the left
        ctk.CTkFrame(self, width=3, fg_color=C_ACCENT, corner_radius=0).pack(
            side="left", fill="y")

        ctk.CTkLabel(self,
                     text=title.upper(),
                     font=F_PAGE_TITLE,
                     text_color=C_TEXT_TITLE).pack(side="left", padx=(20, 8))

        chip = ctk.CTkFrame(self,
                            fg_color=C_NAV_ACTIVE,
                            border_color=C_NAV_ACTIVE_BD,
                            border_width=1,
                            corner_radius=8)
        chip.pack(side="left")
        ctk.CTkLabel(chip, text=f"{count}  tweaks",
                     font=("Segoe UI", 8, "bold"),
                     text_color=C_ACCENT_BRIGHT).pack(padx=10, pady=4)


class NyrexTweaks(ctk.CTk):

    PAGE_ICONS = {
        # must match keys in tweaks.json exactly
        "dashboard": "⚡",
        "windows":   "▣",
        "debloat":   "⊘",
        "apps":      "◆",
        "gpu":       "▲",
        "registry":  "≡",
        "qol":       "✦",
        # fallbacks for longer key names
        "network":           "⬡",
        "gaming":            "◈",
        "privacy":           "◉",
        "power":             "◎",
        "visual":            "◇",
        "app_optimizations": "◆",
        "windows_tweaks":    "▣",
        "debloat_windows":   "⊘",
        "gpu_tweaks":        "▲",
        "registry_tweaks":   "≡",
        "quality_of_life":   "✦",
    }
    DEFAULT_ICON = "◆"

    def __init__(self):
        super().__init__()

        self.overrideredirect(True)
        self.title("Nyrex Tweaks")
        self.geometry("1120x756")
        self.minsize(900, 636)
        self.configure(fg_color=C_ROOT)
        self.attributes("-alpha", 0.0)

        self._restore_taskbar()

        icon_p = resource_path("icon.ico")
        if os.path.exists(icon_p):
            try: self.iconbitmap(icon_p)
            except: pass

        self.tweaks_data  = self._load()
        self.frames       = {}
        self.nav_btns     = {}
        self.total_tweaks = 0

        # titlebar on top, content below
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # title bar
        TitleBar(self, on_close=self._close).grid(row=0, column=0, sticky="ew")

        # main content area
        self._body = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self._body.grid(row=1, column=0, sticky="nsew")
        self._body.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_W)
        self._body.grid_columnconfigure(1, weight=1)
        self._body.grid_rowconfigure(0, weight=1)

        DotGrid(self._body)
        self._build_sidebar()
        self._build_content()
        self._fade_in()

    def _restore_taskbar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ex   = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ex  &= ~0x80; ex |= 0x40000
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex)
        except: pass

    def _load(self):
        p = resource_path("tweaks.json")
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"[FAIL] Could not load tweaks.json from: {p}  Error: {e}")
            return None

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self._body, width=SIDEBAR_W,
                          fg_color=C_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(0, weight=1)

        # thin line between sidebar and content
        ctk.CTkFrame(sb, width=1, fg_color=C_SIDEBAR_SEP).place(
            relx=1.0, rely=0, relheight=1, x=-1)

        # nav buttons
        nav = ctk.CTkFrame(sb, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="nsew", padx=6, pady=(10, 0))

        if self.tweaks_data:
            ctk.CTkLabel(nav, text="NAVIGATION",
                         font=("Segoe UI", 7, "bold"),
                         text_color=C_TEXT_DIM).pack(anchor="w", padx=10, pady=(4,8))

            for pid, data in self.tweaks_data["PAGES"].items():
                raw  = data["title"].upper()
                disp = "PREPARE SYSTEM" if raw == "DASHBOARD" else raw
                icon = self.PAGE_ICONS.get(pid.lower(), self.DEFAULT_ICON)
                self.total_tweaks += sum(len(v) for v in data["sections"].values())

                btn = NavButton(nav, disp, icon,
                                cmd=lambda p=pid: self._show(p),
                                page_id=pid.lower())
                btn.pack(fill="x", pady=2)
                self.nav_btns[pid] = btn

        Hr(sb, color=C_DIVIDER).grid(row=1, column=0,
                                     sticky="ew", padx=14, pady=14)

        # tweaks count + version at the bottom
        foot = ctk.CTkFrame(sb, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 22))
        row = ctk.CTkFrame(foot, fg_color="transparent")
        row.pack(fill="x")
        StatBadge(row, "TWEAKS",  str(self.total_tweaks)).pack(
            side="left", expand=True, fill="x", padx=(0,4))
        StatBadge(row, "VERSION", "2.0"                 ).pack(
            side="left", expand=True, fill="x", padx=(4,0))

    def _build_content(self):
        self._container = ctk.CTkFrame(self._body, fg_color=C_BG, border_width=0)
        self._container.grid(row=0, column=1, sticky="nsew")

        if not self.tweaks_data:
            self._no_data(); return

        cmd_map = self.tweaks_data.get("TWEAK_COMMANDS", {})

        # these pages have few enough tweaks that scrolling feels weird
        NO_SCROLL_PAGES = {"dashboard", "gpu", "registry", "qol",
                           "gpu_tweaks", "registry_tweaks", "quality_of_life"}

        for pid, pdata in self.tweaks_data["PAGES"].items():
            raw_title = pdata["title"]
            # dashboard is called prepare system in the ui
            title = "Prepare System" if raw_title.upper() == "DASHBOARD" else raw_title
            count = sum(len(v) for v in pdata["sections"].values())

            wrap = ctk.CTkFrame(self._container, fg_color=C_BG, border_width=0)
            self.frames[pid] = wrap

            # page title
            PageHeader(wrap, title, count).pack(fill="x")
            # red line under the header
            ctk.CTkFrame(wrap, height=2, fg_color=C_ACCENT, corner_radius=0).pack(fill="x")

            # scroll or no scroll depending on page
            if pid.lower() in NO_SCROLL_PAGES:
                scroll = ctk.CTkFrame(wrap, fg_color=C_BG, corner_radius=0)
            else:
                scroll = ctk.CTkScrollableFrame(wrap,
                                                fg_color=C_BG,
                                                scrollbar_button_color=C_SCROLLBAR,
                                                scrollbar_button_hover_color=C_ACCENT_MID,
                                                corner_radius=0)
            scroll.pack(fill="both", expand=True)

            for sec, tweaks in pdata["sections"].items():
                SectionHeader(scroll, sec).pack(fill="x", padx=20, pady=(18,8))
                for tname, tdesc in tweaks:
                    card = TweakCard(scroll, tname, tdesc,
                                     cmd_map.get(tname, []))
                    card.pack(fill="x", padx=20, pady=3)

            ctk.CTkFrame(scroll, height=24, fg_color="transparent").pack()

        if self.frames:
            self._show(next(iter(self.frames)))

    def _no_data(self):
        p = resource_path("tweaks.json")
        f = ctk.CTkFrame(self._container, fg_color=C_BG)
        f.pack(fill="both", expand=True)
        ctk.CTkLabel(f, text="⚠", font=("Segoe UI", 52),
                     text_color=C_FAIL).place(relx=.5, rely=.35, anchor="center")
        ctk.CTkLabel(f, text="tweaks.json not found",
                     font=("Segoe UI", 16, "bold"),
                     text_color=C_TEXT_TITLE).place(relx=.5, rely=.46, anchor="center")
        ctk.CTkLabel(f, text="Expected location:",
                     font=("Segoe UI", 9),
                     text_color=C_TEXT_MID).place(relx=.5, rely=.53, anchor="center")
        ctk.CTkLabel(f, text=p,
                     font=("Consolas", 9),
                     text_color=C_ACCENT_BRIGHT,
                     wraplength=700).place(relx=.5, rely=.59, anchor="center")

    def _show(self, pid):
        for k, b in self.nav_btns.items():  b.set_active(k == pid)
        for k, f in self.frames.items():    f.pack_forget()
        self.frames[pid].pack(fill="both", expand=True)

    def _fade_in(self):
        a = self.attributes("-alpha")
        if a < 1.0:
            self.attributes("-alpha", min(a+0.09, 1.0)); self.after(14, self._fade_in)

    def _close(self):
        a = self.attributes("-alpha")
        if a > 0:
            self.attributes("-alpha", max(a-0.09, 0.0)); self.after(14, self._close)
        else:
            self.destroy()


def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def _relaunch_as_admin():
    """Re-launch this script with UAC elevation and exit the current process."""
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas",
            sys.executable,
            f'"{script}" {params}',
            None, 1
        )
    except Exception:
        pass
    sys.exit(0)

if __name__ == "__main__":
    if not _is_admin():
        _relaunch_as_admin()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = NyrexTweaks()
    app.protocol("WM_DELETE_WINDOW", app._close)
    app.mainloop()
