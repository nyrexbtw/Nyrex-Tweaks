"""
Nyrex Tweaks - Performance Optimization Utility
A modern CustomTkinter-based GUI for applying Windows registry and system tweaks.
Optimized for high performance and clean aesthetics.
"""

import customtkinter as ctk
import json
import threading
import subprocess
import os
import sys
import ctypes

# ---------------------------------------------------------
# WINDOWS TASKBAR INTEGRATION
# ---------------------------------------------------------
# This ensures Windows treats the app as a unique process, 
# preventing it from grouping with the default Python/Tkinter icon.
myappid = 'nyrex.tweaks.v1' 
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# ---------------------------------------------------------
# GLOBAL UI THEMING
# ---------------------------------------------------------
COLOR_BG          = "#000000"  # Main background color
COLOR_SIDEBAR     = "#050505"  # Sidebar background
COLOR_NAV_HOVER   = "#121212"  # Navigation button hover state
COLOR_NAV_ACTIVE  = "#1A1A1A"  # Navigation button selected state
COLOR_CARD        = "#080808"  # Background for tweak cards
COLOR_TEXT_MAIN   = "#FFFFFF"  # Primary white text
COLOR_TEXT_DIM    = "#666666"  # Secondary grey text
COLOR_TEXT_V1     = "#888888"  # Version number color

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def resource_path(relative_path):
    """
    Finds the absolute path to a resource.
    Necessary for PyInstaller compatibility where files are bundled in a temp folder (_MEIPASS).
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------
# UI COMPONENT CLASSES
# ---------------------------------------------------------
class TweakCard(ctk.CTkFrame):
    """
    A reusable UI component representing a single system tweak.
    Includes a title, description, and an APPLY button.
    """
    def __init__(self, master, name, description, commands):
        super().__init__(master, fg_color=COLOR_CARD, border_color="#181818", border_width=1, corner_radius=10)
        self.commands = commands
        self.grid_columnconfigure(0, weight=1)
        
        # Title of the Tweak
        ctk.CTkLabel(self, text=name, font=("Segoe UI", 13, "bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, padx=15, pady=(12, 2), sticky="w")
        
        # Short description of what the tweak does
        ctk.CTkLabel(self, text=description, font=("Inter", 11), text_color=COLOR_TEXT_DIM, 
                     wraplength=480, justify="left").grid(row=1, column=0, padx=15, pady=(0, 12), sticky="w")

        # Action Button
        self.btn = ctk.CTkButton(self, text="APPLY", width=75, height=28, fg_color="transparent", 
                                 border_color="#333333", border_width=1, hover_color="#222222",
                                 font=("Segoe UI", 10, "bold"), text_color=COLOR_TEXT_MAIN,
                                 command=self.start_tweak)
        self.btn.grid(row=0, column=1, rowspan=2, padx=15, pady=10)

        # Status output label (hidden by default)
        self.status = ctk.CTkLabel(self, text="", font=("Consolas", 9))
        self.status.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 8), sticky="w")
        self.status.grid_remove()

    def start_tweak(self):
        """Disables the button and launches the command execution in a separate thread."""
        self.btn.configure(state="disabled", text="BUSY")
        threading.Thread(target=self.execute, daemon=True).start()

    def execute(self):
        """Runs the associated shell commands and captures any errors."""
        success, err = True, ""
        for cmd in self.commands:
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode != 0:
                    success, err = False, res.stderr.strip() or f"Error {res.returncode}"
                    break
            except Exception as e:
                success, err = False, str(e); break
        self.after(0, lambda: self.show_result(success, err))

    def show_result(self, success, err):
        """Updates the UI status based on the execution result."""
        self.status.grid()
        if success:
            self.status.configure(text="> STATUS: SUCCESS", text_color="#00FF00")
            self.btn.configure(text="DONE")
        else:
            self.status.configure(text=f"> STATUS: FAIL ({err[:40]})", text_color="#FF4444")
            self.btn.configure(text="RETRY", state="normal")

class NavButton(ctk.CTkButton):
    """
    Custom navigation button for the sidebar.
    Maintains a pill/capsule shape and handles active/inactive styling.
    """
    def __init__(self, master, text, command):
        super().__init__(master, 
                         text=text,
                         command=command,
                         height=42,
                         corner_radius=21, # Pill shape
                         fg_color="transparent",
                         text_color=COLOR_TEXT_DIM,
                         hover_color=COLOR_NAV_HOVER,
                         font=("Segoe UI", 11, "bold"),
                         anchor="center",
                         border_width=0)

    def set_active(self, active):
        """Updates the visual state when the user selects a page."""
        if active:
            self.configure(fg_color=COLOR_NAV_ACTIVE, text_color=COLOR_TEXT_MAIN, hover_color=COLOR_NAV_ACTIVE)
        else:
            self.configure(fg_color="transparent", text_color=COLOR_TEXT_DIM, hover_color=COLOR_NAV_HOVER)

# ---------------------------------------------------------
# MAIN APPLICATION ENGINE
# ---------------------------------------------------------
class NyrexTweaks(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window Setup
        self.title("Nyrex Tweaks")
        self.geometry("1000x700")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.attributes("-alpha", 0.0) # Used for the fade-in effect

        # Handle Icon Loading
        icon_p = resource_path("icon.ico")
        if os.path.exists(icon_p):
            try:
                self.iconbitmap(icon_p)
                self.after(200, lambda: self.iconbitmap(icon_p)) # Redundancy fix
            except Exception as e:
                print(f"Icon failed to load: {e}")

        # Data and State Initialization
        self.tweaks_data = self.load_data()
        self.frames = {}
        self.nav_items = {}
        
        # Main Layout Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        self.setup_content_area()
        self.fade_in()

    def load_data(self):
        """Loads tweak configurations from the external JSON file."""
        path = resource_path("tweaks.json")
        try:
            with open(path, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except: 
            return None

    def setup_sidebar(self):
        """Constructs the left-hand sidebar and branding."""
        self.sidebar = ctk.CTkFrame(self, width=240, fg_color=COLOR_SIDEBAR, corner_radius=0, border_width=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Sidebar Header (Logo/Version)
        header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header.pack(pady=(50, 40), padx=20, fill="x")
        ctk.CTkLabel(header, text="Nyrex Tweaks", font=("Segoe UI", 22, "bold"), text_color=COLOR_TEXT_MAIN).pack()
        ctk.CTkLabel(header, text="V1.0", font=("Consolas", 11, "bold"), text_color=COLOR_TEXT_V1).pack(pady=(2, 0))

        # Dynamic Page Navigation Generation
        self.nav_list = ctk.CTkFrame(self.sidebar, fg_color="transparent", border_width=0)
        self.nav_list.pack(fill="both", expand=True, padx=25)

        if self.tweaks_data:
            for page_id, data in self.tweaks_data["PAGES"].items():
                display_name = data["title"].upper()
                if display_name == "DASHBOARD": display_name = "PREPARE SYSTEM"
                
                item = NavButton(self.nav_list, text=display_name, 
                                 command=lambda p=page_id: self.show_page(p))
                item.pack(fill="x", pady=6) 
                self.nav_items[page_id] = item

    def setup_content_area(self):
        """Generates frames for each page and fills them with tweak cards."""
        self.container = ctk.CTkFrame(self, fg_color=COLOR_BG, border_width=0)
        self.container.grid(row=0, column=1, sticky="nsew", padx=40, pady=(20, 40))
        
        if not self.tweaks_data: return
        cmd_map = self.tweaks_data.get("TWEAK_COMMANDS", {})
        
        for page_id, page_data in self.tweaks_data["PAGES"].items():
            # Create a standard or scrollable frame depending on page length
            if page_data["title"].upper() in ["DASHBOARD", "QUALITY OF LIFE"]:
                frame = ctk.CTkFrame(self.container, fg_color=COLOR_BG, border_width=0)
            else:
                frame = ctk.CTkScrollableFrame(self.container, fg_color=COLOR_BG, 
                                               label_text="", scrollbar_button_color="#1A1A1A")
            self.frames[page_id] = frame

            # Populate with Section Headers and Cards
            for sec_name, tweaks in page_data["sections"].items():
                ctk.CTkLabel(frame, text=f"// {sec_name.upper()}", font=("Consolas", 11, "bold"), 
                             text_color="#BBBBBB").pack(pady=(25, 12), anchor="w", padx=5)
                
                for t_name, t_desc in tweaks:
                    card = TweakCard(frame, t_name, t_desc, cmd_map.get(t_name, []))
                    card.pack(fill="x", pady=5)
        
        # Set default initial page
        if self.frames:
            self.show_page(list(self.frames.keys())[0])

    def show_page(self, page_id):
        """Switches the visible frame and updates navigation button states."""
        for pid, item in self.nav_items.items():
            item.set_active(pid == page_id)
            self.frames[pid].pack_forget()
        self.frames[page_id].pack(fill="both", expand=True)

    def fade_in(self):
        """Smooth transition when the application launches."""
        alpha = self.attributes("-alpha")
        if alpha < 1.0:
            self.attributes("-alpha", alpha + 0.1)
            self.after(10, self.fade_in)

    def fade_out(self):
        """Smooth transition when the application closes."""
        alpha = self.attributes("-alpha")
        if alpha > 0:
            self.attributes("-alpha", alpha - 0.1)
            self.after(10, self.fade_out)
        else:
            self.destroy()

# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------
if __name__ == "__main__":
    app = NyrexTweaks()
    app.protocol("WM_DELETE_WINDOW", app.fade_out) # Link close button to fade_out
    app.mainloop()
