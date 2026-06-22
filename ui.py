"""
Radar UI
Lee formato: angulo(int):distancia(int) desde puerto serial
Convierte a cartesianas y muestra en semicírculo radar estilo militar
"""
import tkinter as tk
from tkinter import messagebox
import math
import threading
import queue
import serial

#  IDENTIDAD VISUAL
BG          = "#0a0f0a"
RADAR_BG    = "#060d06"
GRID_DIM    = "#1a3a1a"
GRID_MID    = "#1f6b1f"
SWEEP_COLOR = "#00ff41"
TEXT_GREEN  = "#39ff14"
TEXT_DIM    = "#2a6b2a"
ACCENT      = "#00ff41"
PANEL_BG    = "#0d1a0d"
BORDER      = "#1a4a1a"
BUTTON_ACTIVE  = "#003310"
BUTTON_HOVER   = "#004d14"

FONT       = ("Courier New", 9)
BIG_FONT   = ("Courier New", 11, "bold")
SMALL_FONT = ("Courier New", 8)

TRACK_COLORS     = ["#00ff41", "#ff6b00", "#00cfff", "#ff003c", "#ffe600"]
MAX_TRACK_RADIUS = 40
MAX_TRACK_LOST   = 15
MIN_TRACK_HISTORY = 3


def polar_to_cartesian(angle_degree, distance, max_distance, circlex, circley, radius):
    pixel_radius = (distance / max_distance) * radius
    angle_radian = math.radians(angle_degree)
    x = circlex + pixel_radius * math.cos(angle_radian)
    y = circley - pixel_radius * math.sin(angle_radian)
    return x, y


class TrackedObject:
    _id_counter = 0

    def __init__(self, angle, dist, x, y):
        TrackedObject._id_counter += 1
        self.id        = TrackedObject._id_counter
        self.color     = TRACK_COLORS[(self.id - 1) % len(TRACK_COLORS)]
        self.angle     = angle
        self.dist      = dist
        self.x         = x
        self.y         = y
        self.history   = [(x, y)]
        self.lost      = 0
        self.speed_cms = 0.0
        self.pred_x    = x
        self.pred_y    = y

    def update(self, angle, dist, x, y):
        self.angle = angle
        self.dist  = dist
        self.x     = x
        self.y     = y
        self.lost  = 0
        self.history.append((x, y))
        if len(self.history) > 20:
            self.history.pop(0)

    def compute_velocity(self, px_per_cm, fps):
        if len(self.history) < MIN_TRACK_HISTORY:
            self.speed_cms = 0.0
            self.pred_x    = self.x
            self.pred_y    = self.y
            return

        dx_total, dy_total = 0.0, 0.0
        n = min(len(self.history), 5)
        for i in range(-n, -1):
            dx_total += self.history[i+1][0] - self.history[i][0]
            dy_total += self.history[i+1][1] - self.history[i][1]
        dx = dx_total / (n - 1)
        dy = dy_total / (n - 1)

        dist_px        = math.hypot(dx, dy)
        dist_cm        = dist_px / px_per_cm if px_per_cm > 0 else 0
        self.speed_cms = dist_cm * fps

        self.pred_x = self.x + dx * 3
        self.pred_y = self.y + dy * 3


class RadarApp:

    MAX_DISTANCE  = 450
    MAX_POINTS    = 120
    FPS           = 30
    FADE_STEPS    = 40

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RADAR 2D")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(820, 560)

        self._queue = queue.Queue()

        self.serial_conn   = None
        self.serial_thread = None
        self.running       = False
        self.demo_mode     = False

        self.points: list[dict] = []
        self.tracks: list[TrackedObject] = []
        self.sweep_angle = 0.0
        self.last_data   = "—"
        self.total_reads = 0

        self._build_ui()
        self._draw_radar_base()
        self._animate()


    def _build_ui(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = tk.Frame(self.root, bg=PANEL_BG, bd=0,
                        highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="ns", padx=(8, 0), pady=8)

        tk.Label(left, text="RADAR CTRL", font=("Courier New", 13, "bold"),
                 bg=PANEL_BG, fg=ACCENT).pack(pady=(16, 4), padx=16)
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=8)

        self._section(left, "SERIAL PORT")
        self.port_var = "COM5"
        tk.Label(left, text="COM5", width=6, font=FONT,
                 bg=PANEL_BG, fg=TEXT_GREEN).pack(padx=16, pady=(0, 4))
        self.baud_var = 9600
        tk.Label(left, text="9600", width=6, font=FONT,
                 bg=PANEL_BG, fg=TEXT_GREEN).pack(padx=16, pady=(0, 8))

        self.btn_connect = self._btn(left, "▶  CONNECT", self._toggle_connect)
        self.btn_connect.pack(fill="x", padx=16, pady=(0, 4))

        self._section(left, "PARAMETERS")
        tk.Label(left, text=f"Max Distance: {self.MAX_DISTANCE} cm",
                 bg=PANEL_BG, fg=TEXT_DIM, font=SMALL_FONT).pack(anchor="w", padx=16)

        self._section(left, "STATUS")
        self.status_lbl = tk.Label(left, text="● OFFLINE", font=BIG_FONT,
                                   bg=PANEL_BG, fg="#ff3333")
        self.status_lbl.pack(pady=(4, 0))

        info_frame = tk.Frame(left, bg=PANEL_BG)
        info_frame.pack(fill="x", padx=16, pady=8)
        self._info_row(info_frame, "Last data:", "last_val")
        self._info_row(info_frame, "Reads:",     "reads_val")
        self._info_row(info_frame, "Points:",    "pts_val")
        self._info_row(info_frame, "Sweep:",     "sweep_val")
        self._info_row(info_frame, "Tracks:",    "tracks_val")

        self._section(left, "TRACKS")
        self.tracks_frame = tk.Frame(left, bg=PANEL_BG)
        self.tracks_frame.pack(fill="x", padx=16, pady=(0, 8))

        self._btn(left, "✕  EXIT", self.root.quit, color="#330000").pack(
            fill="x", padx=16, pady=(0, 16))

        right = tk.Frame(self.root, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(right, bg=RADAR_BG, bd=0,
                                highlightthickness=1,
                                highlightbackground=BORDER)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_resize)

    def _section(self, parent, text):
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(frame, text=text, font=("Courier New", 7, "bold"),
                 bg=PANEL_BG, fg=TEXT_DIM).pack(side="left", padx=8)
        tk.Frame(frame, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=4)

    def _btn(self, parent, text, cmd, color=BUTTON_ACTIVE):
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg=TEXT_GREEN,
                         activebackground=BUTTON_HOVER, activeforeground=ACCENT,
                         relief="flat", bd=0, font=FONT, cursor="hand2", pady=5)

    def _info_row(self, parent, label, attr_name):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, font=SMALL_FONT, bg=PANEL_BG,
                 fg=TEXT_DIM, width=12, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="—", font=SMALL_FONT, bg=PANEL_BG,
                       fg=TEXT_GREEN, anchor="w")
        lbl.pack(side="left")
        setattr(self, attr_name, lbl)


    @property
    def _radar_geom(self):
        width  = self.canvas.winfo_width()  or 600
        height = self.canvas.winfo_height() or 480
        margin = 40
        radius = min(width - (2 * margin), (height - margin) * 2) // 2
        circlex = width  // 2
        circley = height - margin - 10
        return circlex, circley, radius

    def _on_resize(self, event=None):
        self._draw_radar_base()


    def _draw_radar_base(self):
        self.canvas.delete("base")
        circlex, circley, radius = self._radar_geom
        max_distance = self.MAX_DISTANCE

        for i in range(1, 6):
            temp_radius = radius * i / 5
            x0, y0 = circlex - temp_radius, circley - temp_radius
            x1, y1 = circlex + temp_radius, circley + temp_radius
            color = GRID_MID if i == 5 else GRID_DIM
            self.canvas.create_arc(x0, y0, x1, y1,
                                   start=0, extent=180,
                                   outline=color, style="arc",
                                   width=1 if i < 5 else 2,
                                   tags="base")
            dist_label = f"{int(max_distance * i / 5)}"
            self.canvas.create_text(circlex + temp_radius + 3, circley,
                                    text=dist_label, fill=TEXT_DIM,
                                    font=SMALL_FONT, anchor="w", tags="base")

        self.canvas.create_line(circlex - radius, circley,
                                circlex + radius, circley,
                                fill=GRID_MID, width=1, tags="base")

        for angle in range(0, 181, 30):
            theta = math.radians(angle)
            x2 = circlex + radius * math.cos(theta)
            y2 = circley - radius * math.sin(theta)
            self.canvas.create_line(circlex, circley, x2, y2,
                                    fill=GRID_DIM, dash=(4, 6), tags="base")
            lx = circlex + (radius + 20) * math.cos(theta)
            ly = circley - (radius + 20) * math.sin(theta)
            self.canvas.create_text(lx, ly, text=f"{angle}°",
                                    fill=TEXT_DIM, font=SMALL_FONT, tags="base")

        self.canvas.create_oval(circlex-4, circley-4, circlex+4, circley+4,
                                fill=ACCENT, outline="", tags="base")
        self.canvas.create_text(circlex, 18, text="◈  POLAR RADAR  ◈",
                                fill=TEXT_GREEN,
                                font=("Courier New", 12, "bold"), tags="base")


    def _animate(self):
        self._draw_frame()
        self.root.after(int(1000 / self.FPS), self._animate)

    def _draw_frame(self):
        circlex, circley, radius = self._radar_geom

        while not self._queue.empty():
            try:
                item  = self._queue.get_nowait()
                angle = item["angle"]
                dist  = item["dist"]

                self.total_reads += 1
                self.last_data    = f"{angle}deg  {dist} cm"
                self.sweep_angle  = float(angle)

                if dist > 0:
                    self._process_datapoint(angle, dist, circlex, circley, radius)
                    self.points.append({
                        "angle": angle,
                        "dist":  min(dist, self.MAX_DISTANCE),
                        "age":   0,
                    })
                    if len(self.points) > self.MAX_POINTS:
                        self.points.pop(0)
            except queue.Empty:
                break

        for track in self.tracks:
            track.lost += 1
        self.tracks = [t for t in self.tracks if t.lost < MAX_TRACK_LOST]

        self.canvas.delete("dynamic")
        max_distance = self.MAX_DISTANCE

        for point in self.points:
            age_ratio = point["age"] / self.FADE_STEPS
            if age_ratio > 1:
                continue
            green = int(255 * (1 - age_ratio))
            b_c   = int(20  * (1 - age_ratio))
            color = f"#00{green:02x}{b_c:02x}"
            size  = max(2, int(5 * (1 - age_ratio * 0.6)))
            x, y  = polar_to_cartesian(point["angle"], point["dist"],
                                       max_distance, circlex, circley, radius)
            if (circley - radius) <= y <= circley and (circlex - radius) <= x <= (circlex + radius):
                self.canvas.create_oval(x-size, y-size, x+size, y+size,
                                        fill=color, outline="", tags="dynamic")
                if age_ratio < 0.15:
                    offset = size + 4
                    self.canvas.create_line(x-offset, y, x+offset, y,
                                            fill=ACCENT, width=1, tags="dynamic")
                    self.canvas.create_line(x, y-offset, x, y+offset,
                                            fill=ACCENT, width=1, tags="dynamic")

        for point in self.points:
            point["age"] += 1
        self.points = [p for p in self.points if p["age"] < self.FADE_STEPS * 1.5]

        for track in self.tracks:
            c = track.color

            if len(track.history) >= 2:
                flat = [coord for pos in track.history for coord in pos]
                self.canvas.create_line(*flat, fill=c, width=1,
                                        dash=(3, 4), tags="dynamic")

            r = 8
            self.canvas.create_oval(track.x-r, track.y-r,
                                    track.x+r, track.y+r,
                                    outline=c, width=2, fill="", tags="dynamic")

            # Línea de predicción
            self.canvas.create_line(track.x, track.y,
                                    track.pred_x, track.pred_y,
                                    fill=c, width=1, dash=(2, 3), tags="dynamic")

            self.canvas.create_line(track.pred_x-6, track.pred_y,
                                    track.pred_x+6, track.pred_y,
                                    fill=c, width=1, dash=(2, 2), tags="dynamic")
            self.canvas.create_line(track.pred_x, track.pred_y-6,
                                    track.pred_x, track.pred_y+6,
                                    fill=c, width=1, dash=(2, 2), tags="dynamic")

            label = f"T{track.id}  {track.speed_cms:.0f} cm/s\n{track.dist:.0f} cm @ {track.angle}°"
            self.canvas.create_text(track.x + 12, track.y - 12,
                                    text=label, fill=c,
                                    font=SMALL_FONT, anchor="w", tags="dynamic")

        # Sweep
        theta = math.radians(self.sweep_angle)
        sx = circlex + radius * math.cos(theta)
        sy = circley - radius * math.sin(theta)
        self.canvas.create_line(circlex, circley, sx, sy,
                                fill=SWEEP_COLOR, width=2, tags="dynamic")
        for offset, alpha in [(-3, "0d"), (-2, "1a"), (-1, "33")]:
            a_off = self.sweep_angle + offset
            if 0 <= a_off <= 180:
                to = math.radians(a_off)
                gx = circlex + radius * math.cos(to)
                gy = circley - radius * math.sin(to)
                self.canvas.create_line(circlex, circley, gx, gy,
                                        fill=f"#00{alpha}00", width=1, tags="dynamic")

        self.last_val.config(text=self.last_data)
        self.reads_val.config(text=str(self.total_reads))
        self.pts_val.config(text=str(len(self.points)))
        self.sweep_val.config(text=f"{self.sweep_angle:.1f}°")
        self.tracks_val.config(text=str(len(self.tracks)))
        self._update_tracks_panel()


    def _process_datapoint(self, angle, dist, circlex, circley, radius):
        x, y       = polar_to_cartesian(angle, dist, self.MAX_DISTANCE, circlex, circley, radius)
        px_per_cm  = radius / self.MAX_DISTANCE

        best_track = None
        best_dist  = MAX_TRACK_RADIUS

        for track in self.tracks:
            d = math.hypot(x - track.x, y - track.y)
            if d < best_dist:
                best_dist  = d
                best_track = track

        if best_track:
            best_track.update(angle, dist, x, y)
        else:
            self.tracks.append(TrackedObject(angle, dist, x, y))

        for track in self.tracks:
            track.compute_velocity(px_per_cm, self.FPS)

    def _update_tracks_panel(self):
        for widget in self.tracks_frame.winfo_children():
            widget.destroy()

        if not self.tracks:
            tk.Label(self.tracks_frame, text="No targets", font=SMALL_FONT,
                     bg=PANEL_BG, fg=TEXT_DIM).pack(anchor="w")
            return

        for track in self.tracks:
            row = tk.Frame(self.tracks_frame, bg=PANEL_BG)
            row.pack(fill="x", pady=1)

            # Bolita de color
            tk.Label(row, text="●", font=SMALL_FONT,
                     bg=PANEL_BG, fg=track.color).pack(side="left")

            info = (f"T{track.id}  "
                    f"{track.dist:.0f}cm  "
                    f"{track.angle}°  "
                    f"{track.speed_cms:.0f}cm/s")
            tk.Label(row, text=info, font=SMALL_FONT,
                     bg=PANEL_BG, fg=track.color, anchor="w").pack(side="left")


    def _toggle_connect(self):
        if self.running and not self.demo_mode:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        try:
            self.serial_conn = serial.Serial(self.port_var, self.baud_var, timeout=1)
            self.running     = True
            self.demo_mode   = False
            self.serial_thread = threading.Thread(target=self._read_serial, daemon=True)
            self.serial_thread.start()
            self._set_status(True, f"PORT {self.port_var} : {self.baud_var}")
            self.btn_connect.config(text="DISCONNECT")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def _disconnect(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.serial_conn = None
        self._set_status(False)
        self.btn_connect.config(text="▶  CONNECT")

    def _read_serial(self):
        buffer = ""
        while self.running and self.serial_conn:
            try:
                char = self.serial_conn.read(1).decode("utf-8", errors="ignore")
                if char == ",":
                    token = buffer.strip()
                    buffer = ""
                    if token:
                        self._parse_token(token)
                else:
                    buffer += char
            except Exception:
                break
        self.running = False

    def _parse_token(self, token: str):
        try:
            parts = token.split(":")
            if len(parts) != 2:
                return
            angle = int(parts[0].strip())
            dist  = int(parts[1].strip())
            if not (0 <= angle <= 180):
                return
            self._queue.put({"angle": angle, "dist": dist})
        except (ValueError, IndexError):
            pass

    def _set_status(self, online: bool, text: str = None):
        if online:
            self.status_lbl.config(text=text or "ONLINE", fg=ACCENT)
        else:
            self.status_lbl.config(text="● OFFLINE", fg="#ff3333")


if __name__ == "__main__":
    root = tk.Tk()
    app  = RadarApp(root)

    root.update_idletasks()
    width, height = 960, 620
    x = (root.winfo_screenwidth()  - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()