import tkinter as tk
import random
import math
import json
import os

# -------------------------------------------------
# GLOBAL CONFIGURATION & PALETTE CONSTANTS
# -------------------------------------------------
BASE_WIDTH, BASE_HEIGHT = 960, 640
MAX_ARROWS = 5
MAX_HITS = 5
LEADERBOARD_FILE = "leaderboard.json"

COLORS = {
    "bg_dark": "#070D0C",
    "card_bg": "#0F1C18",
    "card_inner": "#162823",
    "accent_gold": "#FFC857",
    "accent_gold_hover": "#FFE08B",
    "accent_gold_glow": "#8F6B12",
    "accent_green": "#2EC4B6",
    "accent_red": "#E71D36",
    "text_light": "#F4F1DE",
    "text_dim": "#7A8C85",
    "panel_border": "#213A33",
    "panel_glow": "#2D5046",
    "hud_bg": "#091411"
}


class ModernButton(tk.Canvas):
    """Custom Canvas Flat Rounded Button with Glow Borders and Smooth Hover Animations."""
    def __init__(self, parent, text, command, width=180, height=42, bg_color=COLORS["accent_gold"], fg_color="#070D0C", radius=10, font_size=11):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.text = text
        self.bg_color = bg_color
        self.hover_color = COLORS["accent_gold_hover"]
        self.fg_color = fg_color
        self.radius = radius
        self.width = width
        self.height = height

        self.rect_id = self._draw_rounded_rect(0, 0, width, height, radius, fill=self.bg_color)
        self.text_id = self.create_text(width // 2, height // 2, text=text, fill=self.fg_color, font=("Segoe UI", font_size, "bold"))

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_enter(self, event):
        self.itemconfig(self.rect_id, fill=self.hover_color)

    def _on_leave(self, event):
        self.itemconfig(self.rect_id, fill=self.bg_color)

    def _on_click(self, event):
        if self.command:
            self.command()


class ArcheryGame:

    def __init__(self, root):
        self.root = root
        self.root.title("Archer's Aim: Pro Edition")
        
        # Base Dimensions & Maximized Window
        self.width = BASE_WIDTH
        self.height = BASE_HEIGHT
        self.root.geometry(f"{BASE_WIDTH}x{BASE_HEIGHT}")
        self.root.minsize(800, 500)
        self.root.resizable(True, True)

        try:
            self.root.state("zoomed")  # Auto Maximize Window
        except tk.TclError:
            pass

        self.root.configure(bg=COLORS["bg_dark"])
        self.root.protocol("WM_DELETE_WINDOW", self.exit_game)

        # Dynamic Scaling Factors
        self.sx = 1.0
        self.sy = 1.0

        # Game Attributes
        self.player_name_var = tk.StringVar(value="")
        self.level = 1
        self.level_name = "SLOW"
        self.score = 0
        self.hits = 0
        self.shots = 0

        # Target Config
        self.base_target_r = 75
        self.target_r = 75
        self.target_x = 720
        self.target_y = 360
        self.target_dir = 1
        self.target_speed = 0

        self.canvas = None
        self.animation_job = None
        self.stretch_job = None
        self.movement_job = None

        self.game_running = False
        self.score_saved = False
        self.is_aiming = False
        self.is_paused = False

        self.current_screen = "home"
        self.leaderboard = self.load_leaderboard()

        self.root.bind("<Configure>", self.on_window_resize)
        self.show_home()

    # =====================================================
    # IN-SCREEN POPUP NOTIFICATIONS (OBS FRIENDLY)
    # =====================================================

    def show_in_screen_error(self, message):
        """Draws an in-canvas popup modal visible to OBS window capture."""
        c = self.canvas
        W, H = self.width, self.height

        # Dark overlay mask
        c.create_rectangle(0, 0, W, H, fill="#000000", stipple="gray75", tags="error_modal")

        # Modal Card
        card_w, card_h = int(360 * self.sx), int(180 * self.sy)
        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["accent_red"], highlightthickness=2)
        c.create_window(W // 2, H // 2, window=card, width=card_w, height=card_h, tags="error_modal")

        # Red Header Banner
        tk.Frame(card, bg=COLORS["accent_red"], height=int(5 * self.sy)).pack(fill="x")

        tk.Label(card, text="⚠️ ATTENTION", font=("Segoe UI", int(12 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["accent_red"]).pack(pady=(12, 4))
        tk.Label(card, text=message, font=("Segoe UI", int(10 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_light"], wraplength=int(320 * self.sx)).pack(pady=(0, 14))

        def close_modal():
            c.delete("error_modal")

        ModernButton(card, "OK", close_modal, width=int(100 * self.sx), height=int(30 * self.sy), bg_color=COLORS["accent_red"], font_size=max(7, int(8 * self.sy))).pack()

    def show_in_screen_confirm(self, title, message, on_confirm):
        """In-screen modal replacement for OS confirmation dialogs."""
        c = self.canvas
        W, H = self.width, self.height

        c.create_rectangle(0, 0, W, H, fill="#000000", stipple="gray75", tags="confirm_modal")

        card_w, card_h = int(380 * self.sx), int(180 * self.sy)
        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["accent_gold"], highlightthickness=2)
        c.create_window(W // 2, H // 2, window=card, width=card_w, height=card_h, tags="confirm_modal")

        tk.Frame(card, bg=COLORS["accent_gold"], height=int(5 * self.sy)).pack(fill="x")

        tk.Label(card, text=title.upper(), font=("Segoe UI", int(12 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["accent_gold"]).pack(pady=(12, 4))
        tk.Label(card, text=message, font=("Segoe UI", int(9 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_light"]).pack(pady=(0, 14))

        btn_box = tk.Frame(card, bg=COLORS["card_bg"])
        btn_box.pack()

        def confirm_action():
            c.delete("confirm_modal")
            on_confirm()

        def cancel_action():
            c.delete("confirm_modal")

        f_sz = max(7, int(8 * self.sy))
        ModernButton(btn_box, "YES", confirm_action, width=int(90 * self.sx), height=int(28 * self.sy), bg_color=COLORS["accent_red"], font_size=f_sz).pack(side="left", padx=5)
        ModernButton(btn_box, "NO", cancel_action, width=int(90 * self.sx), height=int(28 * self.sy), bg_color=COLORS["accent_gold"], font_size=f_sz).pack(side="left", padx=5)

    # =====================================================
    # RESIZING ENGINE & SYSTEM HELPERS
    # =====================================================

    def on_window_resize(self, event):
        """Dynamically scales graphics and layout whenever window size changes."""
        if event.widget == self.root:
            new_w = event.width
            new_h = event.height
            if new_w > 100 and new_h > 100 and (new_w != self.width or new_h != self.height):
                self.width = new_w
                self.height = new_h
                self.sx = self.width / BASE_WIDTH
                self.sy = self.height / BASE_HEIGHT

                # Redraw active view automatically
                if self.canvas and not self.is_aiming and not self.is_paused:
                    if self.current_screen == "home":
                        self.show_home()
                    elif self.current_screen == "level_select":
                        self.show_level_select()
                    elif self.current_screen == "instructions":
                        self.show_instructions()
                    elif self.current_screen == "leaderboard":
                        self.show_leaderboard()

    def cancel_jobs(self):
        for job_name in ("animation_job", "stretch_job", "movement_job"):
            job = getattr(self, job_name, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, job_name, None)

    def clear_window(self):
        self.cancel_jobs()
        self.game_running = False
        self.is_paused = False
        for widget in self.root.winfo_children():
            try:
                widget.destroy()
            except tk.TclError:
                pass

    def create_main_canvas(self):
        canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg=COLORS["bg_dark"], highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        return canvas

    def exit_game(self):
        self.game_running = False
        self.cancel_jobs()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # =====================================================
    # LUXURY ATMOSPHERIC SCENE GRAPHICS
    # =====================================================

    def draw_enhanced_background(self, c):
        W, H = self.width, self.height
        
        # 1. Sky Gradient Banding
        sky_colors = ["#050B0E", "#0B151C", "#13222B", "#1C313D", "#274250"]
        band_h = (H * 0.70) / len(sky_colors)

        for i, color in enumerate(sky_colors):
            c.create_rectangle(0, i * band_h, W, (i + 1) * band_h, fill=color, outline="")

        # 2. Twinkling Background Stars
        random.seed(42)
        for _ in range(75):
            star_x = random.randint(0, int(W))
            star_y = random.randint(0, int(H * 0.48))
            size = random.choice([1.2, 2, 2.8]) * self.sy
            color = random.choice(["#FFFFFF", "#FFF4D2", "#CDEEFF", "#FFF9E6"])
            c.create_oval(star_x, star_y, star_x + size, star_y + size, fill=color, outline="")

        # 3. Glowing Moon
        for r, alpha_col in [(75 * self.sy, "#2D4954"), (52 * self.sy, "#6F97A8"), (32 * self.sy, "#E5F4FC")]:
            c.create_oval(W * 0.83 - r, H * 0.17 - r, W * 0.83 + r, H * 0.17 + r, fill=alpha_col, outline="")

        # 4. Multi-Layer Mountain Range
        ground_line = H * 0.72

        # Far Back Mountains
        c.create_polygon(0, ground_line, W * 0.14, H * 0.48, W * 0.30, ground_line, fill="#0F1B21", outline="")
        c.create_polygon(W * 0.22, ground_line, W * 0.44, H * 0.42, W * 0.62, ground_line, fill="#13232C", outline="")
        c.create_polygon(W * 0.54, ground_line, W * 0.74, H * 0.45, W * 0.92, ground_line, fill="#0F1B21", outline="")

        # Main Majestic Peaks
        p1_x, p1_y = W * 0.18, H * 0.38
        c.create_polygon(0, ground_line, p1_x, p1_y, W * 0.38, ground_line, fill="#192C36", outline="")
        c.create_polygon(p1_x, p1_y, p1_x - (22 * self.sx), p1_y + (40 * self.sy), p1_x + (8 * self.sx), p1_y + (32 * self.sy), p1_x + (25 * self.sx), p1_y + (45 * self.sy), fill="#E6EDE7", outline="")
        c.create_polygon(p1_x, p1_y, p1_x + (8 * self.sx), p1_y + (32 * self.sy), W * 0.38, ground_line, fill="#132128", outline="")

        p2_x, p2_y = W * 0.48, H * 0.30
        c.create_polygon(W * 0.24, ground_line, p2_x, p2_y, W * 0.68, ground_line, fill="#1E323D", outline="")
        c.create_polygon(p2_x, p2_y, p2_x - (32 * self.sx), p2_y + (55 * self.sy), p2_x + (10 * self.sx), p2_y + (42 * self.sy), p2_x + (30 * self.sx), p2_y + (60 * self.sy), fill="#EEF4F7", outline="")
        c.create_polygon(p2_x, p2_y, p2_x + (10 * self.sx), p2_y + (42 * self.sy), W * 0.68, ground_line, fill="#15242D", outline="")

        p3_x, p3_y = W * 0.78, H * 0.36
        c.create_polygon(W * 0.54, ground_line, p3_x, p3_y, W * 0.98, ground_line, fill="#192C36", outline="")
        c.create_polygon(p3_x, p3_y, p3_x - (25 * self.sx), p3_y + (45 * self.sy), p3_x + (8 * self.sx), p3_y + (35 * self.sy), p3_x + (25 * self.sx), p3_y + (50 * self.sy), fill="#E6EDE7", outline="")
        c.create_polygon(p3_x, p3_y, p3_x + (8 * self.sx), p3_y + (35 * self.sy), W * 0.98, ground_line, fill="#132128", outline="")

        # 5. Pine Tree Layer
        for x in range(-10, int(W) + 20, int(22 * self.sx)):
            h = random.randint(int(40 * self.sy), int(75 * self.sy))
            y = ground_line + 5
            c.create_polygon(x, y - h, x - (15 * self.sx), y, x + (15 * self.sx), y, fill="#081412", outline="")

        # 6. Meadow Base Ground
        c.create_rectangle(0, ground_line, W, H * 0.84, fill="#10241D", outline="")
        c.create_rectangle(0, H * 0.84, W, H, fill="#0A1813", outline="")
        c.create_line(0, ground_line, W, ground_line, fill="#2EC4B6", width=2)

        # 7. Short Grass Layer
        random.seed(23)
        for _ in range(180):
            gx = random.randint(0, int(W))
            gy = random.randint(int(H * 0.84), int(H))
            gh = random.randint(int(3 * self.sy), int(10 * self.sy))
            c.create_line(gx, gy, gx + random.randint(-2, 2), gy - gh, fill="#19382E", width=1)

    # =====================================================
    # HOME SCREEN & LEVEL SELECT
    # =====================================================

    def show_home(self):
        self.current_screen = "home"
        self.clear_window()
        self.canvas = self.create_main_canvas()
        c = self.canvas

        self.draw_enhanced_background(c)

        title_y = int(85 * self.sy)
        c.create_text(self.width // 2 + 2, title_y + 2, text="ARCHER'S AIM", font=("Segoe UI", int(38 * self.sy), "bold"), fill=COLORS["accent_gold_glow"])
        c.create_text(self.width // 2, title_y, text="ARCHER'S AIM", font=("Segoe UI", int(38 * self.sy), "bold"), fill=COLORS["accent_gold"])
        c.create_text(self.width // 2, int(130 * self.sy), text="PRECISION ARCHERY SIMULATOR", font=("Segoe UI", int(11 * self.sy), "bold"), fill=COLORS["text_dim"])

        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["panel_glow"], highlightthickness=2)
        c.create_window(self.width // 2, int(380 * self.sy), window=card, width=int(340 * self.sx), height=int(380 * self.sy))

        tk.Label(card, text="WELCOME ARCHER", font=("Segoe UI", int(13 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_light"]).pack(pady=(15, 8))
        tk.Label(card, text="ENTER PLAYER NAME", font=("Segoe UI", int(8 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(pady=(2, 2))

        name_entry = tk.Entry(card, textvariable=self.player_name_var, font=("Segoe UI", int(11 * self.sy)), justify="center", bg=COLORS["bg_dark"], fg=COLORS["accent_gold"], insertbackground="white", relief="flat")
        name_entry.pack(padx=20, fill="x", ipady=4, pady=(0, 10))
        name_entry.focus_set()

        btn_w, btn_h = int(240 * self.sx), int(38 * self.sy)
        f_sz = max(9, int(10 * self.sy))
        ModernButton(card, "PLAY GAME", self.show_level_select, width=btn_w, height=btn_h, font_size=f_sz).pack(pady=4)
        ModernButton(card, "HOW TO PLAY", self.show_instructions, width=btn_w, height=btn_h, font_size=f_sz).pack(pady=4)
        ModernButton(card, "LEADERBOARD", self.show_leaderboard, width=btn_w, height=btn_h, font_size=f_sz).pack(pady=4)
        ModernButton(card, "EXIT", self.exit_game, width=btn_w, height=btn_h, font_size=f_sz).pack(pady=4)

    def show_level_select(self):
        name = self.player_name_var.get().strip()
        if not name:
            self.show_in_screen_error("PLEASE ENTER THE NAME")
            return

        self.current_screen = "level_select"
        self.clear_window()
        self.canvas = self.create_main_canvas()
        c = self.canvas

        self.draw_enhanced_background(c)

        title_y = int(95 * self.sy)
        c.create_text(self.width // 2 + 2, title_y + 2, text="SELECT DIFFICULTY", font=("Segoe UI", int(32 * self.sy), "bold"), fill=COLORS["accent_gold_glow"])
        c.create_text(self.width // 2, title_y, text="SELECT DIFFICULTY", font=("Segoe UI", int(32 * self.sy), "bold"), fill=COLORS["accent_gold"])

        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["panel_glow"], highlightthickness=2)
        c.create_window(self.width // 2, int(380 * self.sy), window=card, width=int(380 * self.sx), height=int(360 * self.sy))

        tk.Label(card, text="CHOOSE TARGET SPEED", font=("Segoe UI", int(13 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_light"]).pack(pady=(20, 10))

        btn_w, btn_h = int(280 * self.sx), int(42 * self.sy)
        f_sz = max(9, int(10 * self.sy))
        
        ModernButton(card, "SLOW LEVEL", lambda: self.select_level(1, "SLOW"), width=btn_w, height=btn_h, font_size=f_sz).pack(pady=6)
        ModernButton(card, "MEDIUM LEVEL", lambda: self.select_level(2, "MEDIUM"), width=btn_w, height=btn_h, font_size=f_sz).pack(pady=6)
        ModernButton(card, "FAST LEVEL", lambda: self.select_level(3, "FAST"), width=btn_w, height=btn_h, font_size=f_sz).pack(pady=6)
        
        ModernButton(card, "BACK", self.show_home, width=int(140 * self.sx), height=int(34 * self.sy), font_size=f_sz).pack(pady=10)

    def select_level(self, lvl, name):
        self.level = lvl
        self.level_name = name
        if self.level == 1:
            self.target_speed = 2 * self.sx
        elif self.level == 2:
            self.target_speed = 5 * self.sx
        elif self.level == 3:
            self.target_speed = 9 * self.sx

        self.create_new_game()

    # =====================================================
    # HOW TO PLAY UI
    # =====================================================

    def show_instructions(self):
        self.current_screen = "instructions"
        self.clear_window()
        self.canvas = self.create_main_canvas()
        c = self.canvas
        self.draw_enhanced_background(c)

        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["panel_glow"], highlightthickness=2)
        c.create_window(self.width // 2, self.height // 2, window=card, width=int(640 * self.sx), height=int(500 * self.sy))

        tk.Label(card, text="HOW TO PLAY", font=("Segoe UI", int(22 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["accent_gold"]).pack(pady=(18, 2))
        tk.Label(card, text="MASTER THE BOW & TARGET", font=("Segoe UI", int(9 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(pady=(0, 12))

        rules = [
            ("①", "AIM & SHOOT", "Click anywhere in front of the archer to aim and release."),
            ("②", "GRAVITY ARC", "Arrows curve downward—aim slightly higher for distance."),
            ("③", "MOVING TARGETS", "Targets glide horizontally across SLOW, MEDIUM & FAST levels."),
            ("④", "SCORING RINGS", "Bullseye = 10 pts | Blue Ring = 7 pts | Outer Rings = 5 pts."),
            ("⑤", "WIN CONDITION", "You have 5 arrows per round. Land 5 hits to claim victory!")
        ]

        rules_container = tk.Frame(card, bg=COLORS["card_bg"])
        rules_container.pack(fill="both", expand=True, padx=20)

        f_title = max(8, int(10 * self.sy))
        f_desc = max(7, int(9 * self.sy))

        for num, heading, desc in rules:
            row = tk.Frame(rules_container, bg=COLORS["card_inner"], bd=1, relief="flat")
            row.pack(fill="x", pady=4, ipady=3)

            badge = tk.Label(row, text=num, font=("Segoe UI", f_title, "bold"), bg=COLORS["accent_gold"], fg="#070D0C", width=3)
            badge.pack(side="left", padx=(6, 10), pady=4)

            txt_box = tk.Frame(row, bg=COLORS["card_inner"])
            txt_box.pack(side="left", fill="both", expand=True)

            tk.Label(txt_box, text=heading, font=("Segoe UI", f_title, "bold"), bg=COLORS["card_inner"], fg=COLORS["accent_green"], anchor="w").pack(fill="x")
            tk.Label(txt_box, text=desc, font=("Segoe UI", f_desc), bg=COLORS["card_inner"], fg=COLORS["text_light"], anchor="w").pack(fill="x")

        tip_box = tk.Frame(card, bg=COLORS["hud_bg"], bd=1, highlightbackground=COLORS["accent_gold"], highlightthickness=1)
        tip_box.pack(fill="x", padx=20, pady=(8, 12))
        tk.Label(tip_box, text="💡 PRO TIP: Time your release ahead of moving targets to score Bullseyes!", font=("Segoe UI", f_desc, "italic"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold_hover"]).pack(pady=4)

        ModernButton(card, "BACK TO MENU", self.show_home, width=int(180 * self.sx), height=int(36 * self.sy), font_size=max(8, int(9 * self.sy))).pack(pady=(0, 15))

    # =====================================================
    # COMPACT LEADERBOARD VIEW
    # =====================================================

    def load_leaderboard(self):
        if not os.path.exists(LEADERBOARD_FILE):
            return []
        try:
            with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_leaderboard(self):
        try:
            with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
                json.dump(self.leaderboard, f, indent=4)
        except Exception:
            pass

    def clear_leaderboard_records(self):
        def do_clear():
            self.leaderboard = []
            self.save_leaderboard()
            self.show_leaderboard()

        self.show_in_screen_confirm("Clear Records", "Are you sure you want to reset the Leaderboard?", do_clear)

    def add_score_to_leaderboard(self):
        if self.score_saved:
            return
        player_name = self.player_name_var.get().strip() or "Archer"
        self.leaderboard.append({"name": player_name[:16], "score": self.score, "hits": self.hits, "level": self.level_name})
        self.leaderboard.sort(key=lambda x: x.get("score", 0), reverse=True)
        self.leaderboard = self.leaderboard[:10]
        self.save_leaderboard()
        self.score_saved = True

    def show_leaderboard(self):
        self.current_screen = "leaderboard"
        self.clear_window()
        self.canvas = self.create_main_canvas()
        c = self.canvas
        self.draw_enhanced_background(c)

        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["accent_gold"], highlightthickness=2)
        c.create_window(self.width // 2, self.height // 2, window=card, width=int(540 * self.sx), height=int(410 * self.sy))

        tk.Frame(card, bg=COLORS["accent_gold"], height=int(5 * self.sy)).pack(fill="x")

        tk.Label(card, text="🏆 HALL OF FAME 🏆", font=("Segoe UI", int(16 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["accent_gold"]).pack(pady=(10, 1))
        tk.Label(card, text="TOP ARCHERS OF ALL TIME", font=("Segoe UI", int(7 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(pady=(0, 6))

        header = tk.Frame(card, bg=COLORS["hud_bg"], bd=1, highlightbackground=COLORS["panel_border"], highlightthickness=1)
        header.pack(fill="x", padx=12, pady=2)
        f_sz = max(7, int(8 * self.sy))

        tk.Label(header, text="RANK", font=("Segoe UI", f_sz, "bold"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold"], width=5).grid(row=0, column=0, pady=3)
        tk.Label(header, text="ARCHER NAME", font=("Segoe UI", f_sz, "bold"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold"], width=15, anchor="w").grid(row=0, column=1, pady=3)
        tk.Label(header, text="LEVEL", font=("Segoe UI", f_sz, "bold"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold"], width=8).grid(row=0, column=2, pady=3)
        tk.Label(header, text="HITS", font=("Segoe UI", f_sz, "bold"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold"], width=6).grid(row=0, column=3, pady=3)
        tk.Label(header, text="SCORE", font=("Segoe UI", f_sz, "bold"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold"], width=6).grid(row=0, column=4, pady=3)

        records_box = tk.Frame(card, bg=COLORS["card_bg"])
        records_box.pack(fill="both", expand=True, padx=12)

        if not self.leaderboard:
            tk.Label(records_box, text="🏹 No Archer Records Found Yet!", font=("Segoe UI", int(10 * self.sy), "italic"), bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(pady=30)
        else:
            for idx, entry in enumerate(self.leaderboard[:5], start=1):
                if idx == 1:
                    row_bg, border_col, rank_icon = "#2A2210", COLORS["accent_gold"], "🥇 1ST"
                elif idx == 2:
                    row_bg, border_col, rank_icon = "#1B2424", "#C0C0C0", "🥈 2ND"
                elif idx == 3:
                    row_bg, border_col, rank_icon = "#241B18", "#CD7F32", "🥉 3RD"
                else:
                    row_bg, border_col, rank_icon = COLORS["card_inner"], COLORS["card_bg"], f"   {idx}TH"

                row = tk.Frame(records_box, bg=row_bg, highlightbackground=border_col, highlightthickness=1)
                row.pack(fill="x", pady=1)

                tk.Label(row, text=rank_icon, font=("Segoe UI", f_sz, "bold"), bg=row_bg, fg=COLORS["accent_gold"], width=5).grid(row=0, column=0, pady=2)
                tk.Label(row, text=str(entry.get("name", "Unknown"))[:12].upper(), font=("Segoe UI", f_sz, "bold"), bg=row_bg, fg=COLORS["text_light"], width=15, anchor="w").grid(row=0, column=1, pady=2)
                
                lvl_str = str(entry.get("level", "SLOW"))
                lvl_bg = COLORS["accent_green"] if lvl_str == "FAST" else COLORS["hud_bg"]
                tk.Label(row, text=lvl_str, font=("Segoe UI", max(6, int(7 * self.sy)), "bold"), bg=lvl_bg, fg=COLORS["text_light"], width=7).grid(row=0, column=2, pady=2)

                tk.Label(row, text=f"{entry.get('hits', 0)}/{MAX_HITS}", font=("Segoe UI", f_sz), bg=row_bg, fg=COLORS["text_dim"], width=6).grid(row=0, column=3, pady=2)
                tk.Label(row, text=str(entry.get("score", 0)), font=("Segoe UI", f_sz, "bold"), bg=row_bg, fg=COLORS["accent_gold"], width=6).grid(row=0, column=4, pady=2)

        btn_box = tk.Frame(card, bg=COLORS["card_bg"])
        btn_box.pack(pady=(6, 10))
        f_btn_sz = max(7, int(8 * self.sy))

        ModernButton(btn_box, "MAIN MENU", self.show_home, width=int(130 * self.sx), height=int(30 * self.sy), font_size=11).pack(side="left", padx=5)
        ModernButton(btn_box, "CLEAR RECORDS", self.clear_leaderboard_records, width=int(130 * self.sx), height=int(30 * self.sy), bg_color=COLORS["accent_red"], font_size=11).pack(side="left", padx=5)

    # =====================================================
    # GAMEPLAY LOOP & HUD
    # =====================================================

    def create_new_game(self):
        self.current_screen = "gameplay"
        self.cancel_jobs()
        self.score = 0
        self.hits = 0
        self.shots = 0
        self.score_saved = False
        self.is_aiming = False
        self.is_paused = False

        self.clear_window()
        self.game_running = True

        self.canvas = self.create_main_canvas()
        self.canvas.bind("<Button-1>", self.aim_and_shoot)

        self.draw_enhanced_background(self.canvas)
        self.create_hud()

        self.target_r = self.base_target_r * self.sy
        self.target_x = random.randint(int(650 * self.sx), int(820 * self.sx))
        self.target_y = random.randint(int(360 * self.sy), int(420 * self.sy))

        self.draw_target(self.canvas, self.target_x, self.target_y, self.target_r)
        self.draw_archer(self.canvas, 130 * self.sx, 430 * self.sy, stretch_level=0, has_arrow=True)

        if self.target_speed > 0:
            self.animate_target_movement()

    def create_hud(self):
        c = self.canvas
        W, H = self.width, self.height
        player_name = self.player_name_var.get().strip() or "ARCHER"
        f_sz = max(9, int(11 * self.sy))

        c.create_rectangle(0, 0, W, H * 0.10, fill=COLORS["hud_bg"], outline=COLORS["panel_border"], width=1)
        c.create_text(W * 0.03, H * 0.05, anchor="w", text=f"ARCHER: {player_name.upper()[:12]}", font=("Segoe UI", f_sz, "bold"), fill=COLORS["text_light"])

        self.score_text = c.create_text(W * 0.28, H * 0.05, text="SCORE: 0", font=("Segoe UI", f_sz, "bold"), fill=COLORS["accent_gold"])
        self.hits_text = c.create_text(W * 0.45, H * 0.05, text=f"HITS: 0/{MAX_HITS}", font=("Segoe UI", f_sz, "bold"), fill=COLORS["accent_green"])
        self.arrows_text = c.create_text(W * 0.62, H * 0.05, text=f"ARROWS: {MAX_ARROWS}", font=("Segoe UI", f_sz, "bold"), fill=COLORS["text_light"])
        c.create_text(W * 0.78, H * 0.05, text=f"LEVEL: {self.level_name}", font=("Segoe UI", f_sz, "bold"), fill=COLORS["accent_gold"])

        btn_frame = tk.Frame(self.root, bg=COLORS["hud_bg"])
        c.create_window(W - int(50 * self.sx), H * 0.05, window=btn_frame)

        tk.Button(btn_frame, text="MENU", command=self.open_pause_modal, font=("Segoe UI", max(8, int(9 * self.sy)), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_light"], relief="flat", bd=0, padx=8, pady=3).pack(side="right")

    def update_hud(self):
        if not self.canvas:
            return
        self.canvas.itemconfig(self.score_text, text=f"SCORE: {self.score}")
        self.canvas.itemconfig(self.hits_text, text=f"HITS: {self.hits}/{MAX_HITS}")
        self.canvas.itemconfig(self.arrows_text, text=f"ARROWS: {MAX_ARROWS - self.shots}")

    # =====================================================
    # ENHANCED TARGET RENDERING
    # =====================================================

    def draw_target(self, c, x, y, r):
        c.delete("target")

        c.create_line(x - (28 * self.sx), y + r, x - (48 * self.sx), y + r + (110 * self.sy), fill="#1E120A", width=int(10 * self.sx), tags="target")
        c.create_line(x + (28 * self.sx), y + r, x + (48 * self.sx), y + r + (110 * self.sy), fill="#1E120A", width=int(10 * self.sx), tags="target")
        c.create_oval(x - (29 * self.sx), y + r + (20 * self.sy), x - (25 * self.sx), y + r + (24 * self.sy), fill="#8F8F8F", outline="", tags="target")
        c.create_oval(x + (25 * self.sx), y + r + (20 * self.sy), x + (29 * self.sx), y + r + (24 * self.sy), fill="#8F8F8F", outline="", tags="target")

        rings = [
            (r, "#E74C3C"),
            (r * 0.75, "#FFFFFF"),
            (r * 0.50, "#3498DB"),
            (r * 0.28, "#F1C40F"),
            (r * 0.12, "#E67E22")
        ]
        for radius, color in rings:
            c.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="#111111", width=2, tags="target")

    def animate_target_movement(self):
        if not self.game_running or self.is_paused:
            return

        if not self.is_aiming:
            min_x = 550 * self.sx
            max_x = 860 * self.sx
            self.target_x += self.target_speed * self.target_dir

            if self.target_x >= max_x:
                self.target_x = max_x
                self.target_dir = -1
            elif self.target_x <= min_x:
                self.target_x = min_x
                self.target_dir = 1

            self.draw_target(self.canvas, self.target_x, self.target_y, self.target_r)

        self.movement_job = self.root.after(20, self.animate_target_movement)

    # =====================================================
    # CHARACTER GRAPHICS & SHOOTING
    # =====================================================

    def draw_archer(self, c, x, y, stretch_level=0.0, has_arrow=True):
        c.delete("archer")

        s = 1.6 * self.sy

        c.create_oval(x - (12 * s), y - (40 * s), x + (12 * s), y - (16 * s), fill="#FFCC99", outline="", tags="archer")
        c.create_polygon(x - (16 * s), y - (32 * s), x + (16 * s), y - (32 * s), x, y - (52 * s), fill=COLORS["accent_green"], tags="archer")

        c.create_rectangle(x - (10 * s), y - (16 * s), x + (10 * s), y + (20 * s), fill="#103024", outline="", tags="archer")

        c.create_line(x - (6 * s), y + (20 * s), x - (10 * s), y + (55 * s), fill="#070D0C", width=max(2, int(6 * s)), tags="archer")
        c.create_line(x + (6 * s), y + (20 * s), x + (10 * s), y + (55 * s), fill="#070D0C", width=max(2, int(6 * s)), tags="archer")

        c.create_line(x, y - (8 * s), x + (25 * s), y - (8 * s), fill="#FFCC99", width=max(2, int(5 * s)), tags="archer")

        pull_x = (x + (25 * s)) - ((30 * s) * stretch_level)
        c.create_line(x - (5 * s), y - (8 * s), pull_x, y - (4 * s), fill="#FFCC99", width=max(2, int(5 * s)), tags="archer")

        bow_x = x + (25 * s)
        c.create_arc(bow_x - (20 * s), y - (45 * s), bow_x + (20 * s), y + (30 * s), start=270, extent=180, style="arc", outline="#8B5A2B", width=max(2, int(4 * s)), tags="archer")
        c.create_line(bow_x, y - (45 * s), pull_x, y - (8 * s), fill="#FFFFFF", width=2, tags="archer")
        c.create_line(pull_x, y - (8 * s), bow_x, y + (30 * s), fill="#FFFFFF", width=2, tags="archer")

        if has_arrow:
            c.create_line(pull_x, y - (8 * s), bow_x + (35 * s), y - (8 * s), fill=COLORS["accent_gold"], width=4, tags="archer")

    def aim_and_shoot(self, event):
        if not self.game_running or self.is_aiming or self.is_paused:
            return
        if self.shots >= MAX_ARROWS or self.hits >= MAX_HITS:
            return

        aim_x, aim_y = event.x, event.y
        if aim_x <= 200 * self.sx or aim_y < 80 * self.sy or aim_y > 550 * self.sy:
            return

        self.is_aiming = True

        def animate_draw(step=0):
            if step <= 8:
                progress = step / 8.0
                self.draw_archer(self.canvas, 130 * self.sx, 430 * self.sy, stretch_level=progress, has_arrow=True)
                self.stretch_job = self.root.after(20, lambda: animate_draw(step + 1))
            else:
                self.draw_archer(self.canvas, 130 * self.sx, 430 * self.sy, stretch_level=0, has_arrow=False)
                self.launch_arrow_physics(aim_x, aim_y)

        animate_draw()

    # =====================================================
    # ARROW PHYSICS & FLIGHT
    # =====================================================

    def launch_arrow_physics(self, target_aim_x, target_aim_y):
        start_x, start_y = 170 * self.sx, 415 * self.sy
        steps = 30
        gravity = 35.0 * self.sy

        trajectory = []
        for i in range(steps + 1):
            t = i / steps
            curr_x = start_x + (target_aim_x - start_x) * t
            curr_y = start_y + (target_aim_y - start_y) * t - (gravity * math.sin(math.pi * t))
            trajectory.append((curr_x, curr_y))

        def animate_flight(step=0):
            if step < len(trajectory):
                self.canvas.delete("flying_arrow")
                cx, cy = trajectory[step]
                prev_x, prev_y = trajectory[max(0, step - 1)]

                angle = math.atan2(cy - prev_y, cx - prev_x)
                arrow_len = 40 * self.sx
                tx = cx - arrow_len * math.cos(angle)
                ty = cy - arrow_len * math.sin(angle)

                self.canvas.create_line(tx, ty, cx, cy, fill=COLORS["accent_gold"], width=3, tags="flying_arrow")
                self.canvas.create_polygon(cx, cy, cx - (6 * self.sx), cy - (3 * self.sy), cx - (6 * self.sx), cy + (3 * self.sy), fill="white", tags="flying_arrow")

                self.animation_job = self.root.after(16, lambda: animate_flight(step + 1))
            else:
                self.canvas.delete("flying_arrow")
                impact_x, impact_y = trajectory[-1]
                self.process_shot_impact(impact_x, impact_y)

        animate_flight()

    def process_shot_impact(self, ix, iy):
        dist = math.hypot(ix - self.target_x, iy - self.target_y)

        if dist <= self.target_r * 0.12:
            points, msg = 10, "BULLSEYE!"
        elif dist <= self.target_r * 0.50:
            points, msg = 7, "GREAT SHOT!"
        elif dist <= self.target_r:
            points, msg = 5, "HIT!"
        else:
            points, msg = 0, "MISS!"

        self.shots += 1
        self.score += points
        if points > 0:
            self.hits += 1

        self.update_hud()
        self.show_floating_text(ix, iy - (25 * self.sy), msg)

        self.canvas.create_line(ix - (35 * self.sx), iy - (5 * self.sy), ix, iy, fill=COLORS["accent_gold"], width=3, tags="target")
        self.root.after(1000, self.check_next_turn)

    def show_floating_text(self, x, y, text):
        txt_id = self.canvas.create_text(x, y, text=text, font=("Segoe UI", int(14 * self.sy), "bold"), fill=COLORS["accent_gold"])
        
        def fade(step=0):
            if step < 10:
                self.canvas.move(txt_id, 0, -1.5 * self.sy)
                self.root.after(30, lambda: fade(step + 1))
            else:
                self.canvas.delete(txt_id)
        fade()

    def check_next_turn(self):
        self.is_aiming = False
        if self.hits >= MAX_HITS:
            self.trigger_game_over(win=True)
        elif self.shots >= MAX_ARROWS:
            self.trigger_game_over(win=False)
        else:
            self.draw_archer(self.canvas, 130 * self.sx, 430 * self.sy, stretch_level=0, has_arrow=True)

    # =====================================================
    # COMPACT GAME OVER MODAL
    # =====================================================

    def open_pause_modal(self):
        """Displays stylish overlay pause menu during gameplay."""
        if not self.game_running or self.is_paused:
            return
        self.is_paused = True

        c = self.canvas
        W, H = self.width, self.height

        c.create_rectangle(0, 0, W, H, fill="#050B0E", stipple="gray75", tags="pause_modal")

        modal_w, modal_h = int(320 * self.sx), int(240 * self.sy)
        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["accent_gold"], highlightthickness=2)
        c.create_window(W // 2, H // 2, window=card, width=modal_w, height=modal_h, tags="pause_modal")

        tk.Frame(card, bg=COLORS["accent_gold"], height=int(4 * self.sy)).pack(fill="x")

        tk.Label(card, text="GAME PAUSED", font=("Segoe UI", int(14 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["accent_gold"]).pack(pady=(12, 2))
        tk.Label(card, text="WHAT WOULD YOU LIKE TO DO?", font=("Segoe UI", int(7 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(pady=(0, 12))

        btn_w, btn_h = int(180 * self.sx), int(32 * self.sy)
        f_sz = max(7, int(8 * self.sy))

        def resume():
            c.delete("pause_modal")
            self.is_paused = False
            if self.target_speed > 0:
                self.animate_target_movement()

        ModernButton(card, "RESUME GAME", resume, width=btn_w, height=btn_h, font_size=f_sz).pack(pady=4)
        ModernButton(card, "MAIN MENU", self.show_home, width=btn_w, height=btn_h, font_size=f_sz).pack(pady=4)

    def trigger_game_over(self, win=False):
        """Displays compact Victory or Game Over modal popup board."""
        self.game_running = False
        self.cancel_jobs()
        self.add_score_to_leaderboard()

        c = self.canvas
        W, H = self.width, self.height

        c.create_rectangle(0, 0, W, H, fill="#050B0E", stipple="gray75")

        modal_w, modal_h = int(420 * self.sx), int(310 * self.sy)
        card = tk.Frame(c, bg=COLORS["card_bg"], bd=0, highlightbackground=COLORS["accent_gold"], highlightthickness=2)
        c.create_window(W // 2, H // 2, window=card, width=modal_w, height=modal_h)

        banner_color = COLORS["accent_gold"] if win else COLORS["accent_red"]
        banner = tk.Frame(card, bg=banner_color, height=int(5 * self.sy))
        banner.pack(fill="x")

        title_txt = "🎉 VICTORY! 🎉" if win else "🏹 GAME OVER 🏹"
        subtitle_txt = "CONGRATULATIONS ARCHER!" if win else "BETTER LUCK NEXT TIME!"
        
        tk.Label(card, text=title_txt, font=("Segoe UI", int(18 * self.sy), "bold"), bg=COLORS["card_bg"], fg=banner_color).pack(pady=(10, 1))
        tk.Label(card, text=subtitle_txt, font=("Segoe UI", int(7 * self.sy), "bold"), bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(pady=(0, 10))

        stats_frame = tk.Frame(card, bg=COLORS["card_bg"])
        stats_frame.pack(fill="x", padx=18, pady=2)

        rank_title = "MASTER ARCHER" if self.score >= 40 else "EXPERT ARCHER" if self.score >= 25 else "NOVICE ARCHER"

        s_box1 = tk.Frame(stats_frame, bg=COLORS["card_inner"], highlightbackground=COLORS["panel_border"], highlightthickness=1)
        s_box1.pack(side="left", expand=True, fill="both", padx=3, ipady=4)
        tk.Label(s_box1, text="FINAL SCORE", font=("Segoe UI", int(7 * self.sy), "bold"), bg=COLORS["card_inner"], fg=COLORS["text_dim"]).pack()
        tk.Label(s_box1, text=str(self.score), font=("Segoe UI", int(15 * self.sy), "bold"), bg=COLORS["card_inner"], fg=COLORS["accent_gold"]).pack()

        s_box2 = tk.Frame(stats_frame, bg=COLORS["card_inner"], highlightbackground=COLORS["panel_border"], highlightthickness=1)
        s_box2.pack(side="left", expand=True, fill="both", padx=3, ipady=4)
        tk.Label(s_box2, text="ACCURACY", font=("Segoe UI", int(7 * self.sy), "bold"), bg=COLORS["card_inner"], fg=COLORS["text_dim"]).pack()
        tk.Label(s_box2, text=f"{self.hits}/{MAX_HITS}", font=("Segoe UI", int(15 * self.sy), "bold"), bg=COLORS["card_inner"], fg=COLORS["accent_green"]).pack()

        rank_box = tk.Frame(card, bg=COLORS["hud_bg"], highlightbackground=COLORS["panel_glow"], highlightthickness=1)
        rank_box.pack(fill="x", padx=21, pady=8, ipady=3)
        tk.Label(rank_box, text=f"ACHIEVED RANK:  {rank_title}", font=("Segoe UI", int(9 * self.sy), "bold"), bg=COLORS["hud_bg"], fg=COLORS["accent_gold_hover"]).pack()

        btn_box = tk.Frame(card, bg=COLORS["card_bg"])
        btn_box.pack(pady=(6, 10))

        btn_w, btn_h = int(130 * self.sx), int(32 * self.sy)
        f_sz = max(7, int(8 * self.sy))

        ModernButton(btn_box, "PLAY AGAIN", self.show_level_select, width=btn_w, height=btn_h, font_size=11).pack(side="left", padx=5)
        ModernButton(btn_box, "LEADERBOARD", self.show_leaderboard, width=btn_w, height=btn_h, font_size=11).pack(side="left", padx=5)


# =========================================================
# APPLICATION ENTRY POINT
# =========================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = ArcheryGame(root)
    root.mainloop()