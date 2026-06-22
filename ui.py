"""
Radar UI
Lee formato: angulo(int):distancia(int) desde puerto serial
Convierte a cartesianas y muestra en semicírculo radar estilo militar
"""
# [point = {x, y, age, angle, dist}]
import tkinter as tk
from tkinter import messagebox
import math
import threading

import serial
#  CONSTANTES
BG          = "#0a0f0a"
RADAR_BG    = "#060d06"
GRID_DIM    = "#1a3a1a"
GRID_MID    = "#1f6b1f"
SWEEP_COLOR = "#00ff41"
POINT_HOT   = "#00ff41"
POINT_FADE  = "#004d14"
TEXT_GREEN  = "#39ff14"
TEXT_DIM    = "#2a6b2a"
ACCENT      = "#00ff41"
PANEL_BG    = "#0d1a0d"
BORDER      = "#1a4a1a"
BUTTON_ACTIVE  = "#003310"
BUTTON_HOVER   = "#004d14"

FONT   = ("Courier New", 9)
BIG_FONT = ("Courier New", 11, "bold")
SMALL_FONT = ("Courier New", 8)


def polar_to_cartesian(angle_degree: int, distance: int, max_distance: int, circlex: int, circley: int, radius: int):
    pixel_radius = (distance / max_distance) * radius
    angle_radian = math.radians(angle_degree)
    x = circlex + pixel_radius * math.cos(angle_radian)
    y = circley - pixel_radius * math.sin(angle_radian)
    return x, y


class RadarApp:

    MAX_DISTANCE = 800
    MAX_POINTS  = 120
    SWEEP_SPEED = 1.5
    FPS         = 30 
    FADE_STEPS  = 40 

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RADAR 2D")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(820, 560)

        # SERIAL STATES
        self.serial_conn   = None
        self.serial_thread = None
        self.running       = False
        self.demo_mode     = False
        self.sweep_foward = False

        # Datos radar
        # [{x, y, age, angle, dist}]
        self.points: list[dict] = []          
        self.sweep_angle = 0.0   
        self.last_data   = "—"
        self.total_reads = 0

        self._build_ui()
        self._draw_radar_base()
        self._animate()

    #  CONSTRUCCIÓN DE LA UI

    def _build_ui(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        #Marco del panel izquierdo
        left = tk.Frame(self.root, bg=PANEL_BG, bd=0,
                        highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="ns", padx=(8,0), pady=8)

        # Título
        tk.Label(left, text="RADAR CTRL", font=("Courier New", 13, "bold"),
                 bg=PANEL_BG, fg=ACCENT).pack(pady=(16,4), padx=16)
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=8)

        #Sección serial
        self._section(parent=left, text="SERIAL PORT")

        self.port_var = "COM5"
        self.port_combo  = tk.Label(left, text="COM5", width=6, font=FONT)
        self.port_combo.pack(padx=16, pady=(0,4))

        self.baud_var = 9600
        baud_cb = tk.Label(left, text="9600", width=6, font=FONT)
        baud_cb.pack(padx=16, pady=(0,8))

        self.btn_connect = self._btn(parent=left, text="▶  CONNECT", cmd=self._toggle_connect)
        self.btn_connect.pack(fill="x", padx=16, pady=(0,4))

        #Sección parámetros
        self._section(parent=left, text="PARAMETERS")

        tk.Label(left, text="Max Distance: 800 cm",
                 bg=PANEL_BG, fg=TEXT_DIM, font=SMALL_FONT).pack(anchor="w", padx=16)


        #Sección estado
        self._section(parent=left, text="STATUS")

        self.status_lbl = tk.Label(left, text="● OFFLINE", font=BIG_FONT,
                                   bg=PANEL_BG, fg="#ff3333")
        self.status_lbl.pack(pady=(4,0))

        info_frame = tk.Frame(left, bg=PANEL_BG)
        info_frame.pack(fill="x", padx=16, pady=8)

        self._info_row(info_frame, "Last data:", "last_val")
        self._info_row(info_frame, "Reads:",     "reads_val")
        self._info_row(info_frame, "Points:",    "pts_val")
        self._info_row(info_frame, "Sweep:",     "sweep_val")

        self._btn(parent=left, text="✕  EXIT", cmd=self.root.quit, color="#330000").pack(
            fill="x", padx=16, pady=(0,16))

        #Panel derecho
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
        frame.pack(fill="x", padx=8, pady=(8,2))
        tk.Label(frame, text=text, font=("Courier New", 7, "bold"),
                 bg=PANEL_BG, fg=TEXT_DIM).pack(side="left", padx=8)
        tk.Frame(frame, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=4)

    def _btn(self, parent, text, cmd, color=BUTTON_ACTIVE):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=color, fg=TEXT_GREEN, activebackground=BUTTON_HOVER,
                      activeforeground=ACCENT, relief="flat", bd=0,
                      font=FONT, cursor="hand2", pady=5)
        return b

    def _info_row(self, parent, label, attr_name):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, font=SMALL_FONT, bg=PANEL_BG,
                 fg=TEXT_DIM, width=12, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="—", font=SMALL_FONT, bg=PANEL_BG,
                       fg=TEXT_GREEN, anchor="w")
        lbl.pack(side="left")
        setattr(self, attr_name, lbl)

    #  GEOMETRÍA DEL RADAR

    @property
    def _radar_geom(self):
        """
        Define las dimensiones del semicírculo en base al canvas actual
        para hacer la app responsive.
        """
        width = self.canvas.winfo_width()  or 600
        height = self.canvas.winfo_height() or 480
        margin = 40
        radius = min(width - (2*margin), (height - margin)*2) // 2
        circlex = width // 2
        circley = height - margin - 10
        return circlex, circley, radius

    def _on_resize(self, event=None):
        self._draw_radar_base()

    #  DIBUJO DE BASE

    def _draw_radar_base(self):
        self.canvas.delete("base")
        circlex, circley, radius = self._radar_geom
        max_distance = self.MAX_DISTANCE

        # Semicirculos de profundidad
        for i in range(1, 6): # Empieza de 1 porque 0 es el mero centro
            temp_radius  = radius * i / 5
            x0, y0 = circlex - temp_radius, circley - temp_radius
            x1, y1 = circlex + temp_radius, circley + temp_radius
            
            color = GRID_DIM
            if i == 5:
                color = GRID_MID 
            
            self.canvas.create_arc(x0, y0, x1, y1,
                                   start=0, extent=180,
                                   outline=color, style="arc",
                                   width=1 if i < 5 else 2,
                                   tags="base")
            # Etiqueta de distancia
            dist_label = f"{int(max_distance * i / 5)}"
            # Ubican los labels a la altura de la base del semicirculo.
            self.canvas.create_text(circlex + temp_radius + 3, circley,
                                    text=dist_label, fill=TEXT_DIM,
                                    font=SMALL_FONT, anchor="w", tags="base")

        # Línea de base
        self.canvas.create_line(circlex - radius, circley, circlex + radius, circley,
                                fill=GRID_MID, width=1, tags="base")

        for angle in range(0, 181, 30):
            theta = math.radians(angle)
            x2 = circlex + radius * math.cos(theta)
            y2 = circley - radius * math.sin(theta)
            self.canvas.create_line(circlex, circley, x2, y2,
                                    fill=GRID_DIM, dash=(4,6),
                                    tags="base")
            # Etiqueta angular
            lx = circlex + (radius + 20) * math.cos(theta)
            ly = circley - (radius + 20) * math.sin(theta)
            self.canvas.create_text(lx, ly, text=f"{angle}°",
                                    fill=TEXT_DIM, font=SMALL_FONT,
                                    tags="base")

        # Centro
        self.canvas.create_oval(circlex-4, circley-4, circlex+4, circley+4,
                                fill=ACCENT, outline="", tags="base")

        # Título radar
        self.canvas.create_text(circlex, 18,
                                 text="◈  POLAR RADAR  ◈",
                                 fill=TEXT_GREEN, font=("Courier New", 12, "bold"),
                                 tags="base")

    #  ANIMACIÓN

    def _animate(self):
        self._draw_frame()
        self.root.after(int(1000 / self.FPS), self._animate)

    def _draw_frame(self):
        self.canvas.delete("dynamic")
        circlex, circley, radius = self._radar_geom
        max_distance = self.MAX_DISTANCE

        for point in self.points:
            age_ratio = point["age"] / self.FADE_STEPS
            if age_ratio > 1:
                continue
            # Interpolar color
            green = int(255 * (1 - age_ratio))
            r_c   = int(0)
            b_c   = int(20 * (1 - age_ratio))
            color = f"#{r_c:02x}{green:02x}{b_c:02x}"
            size  = max(2, int(5 * (1 - age_ratio * 0.6)))
            x, y = polar_to_cartesian(angle_degree=point["angle"], distance=point["dist"],
                                      max_distance=max_distance, circlex=circlex, circley=circley, radius=radius)
            if ((circley - radius) <= y <= circley) and ((circlex - radius) <= x <= (circlex + radius)):
                self.canvas.create_oval(x-size, y-size, x+size, y+size,
                                        fill=color, outline="",
                                        tags="dynamic")
                # Cruz en punto reciente
                if age_ratio < 0.15:
                    offset = size + 4
                    self.canvas.create_line(x-offset, y, x+offset, y,
                                            fill=ACCENT, width=1,
                                            tags="dynamic")
                    self.canvas.create_line(x, y-offset, x, y+offset,
                                            fill=ACCENT, width=1,
                                            tags="dynamic")
        # Envejecer puntos
        for point in self.points:
            point["age"] += 1
        self.points = [point for point in self.points if point["age"] < self.FADE_STEPS * 1.5]

        theta = math.radians(self.sweep_angle)
        sx = circlex + radius * math.cos(theta)
        sy = circley - radius * math.sin(theta)
        self.canvas.create_line(circlex, circley, sx, sy,
                                fill=SWEEP_COLOR, width=2,
                                tags="dynamic")
        # Glow del sweep
        for offset, alpha in [(-3, "0d"), (-2, "1a"), (-1, "33")]:
            a_off = (self.sweep_angle + offset) % 180
            if 0 <= a_off <= 180:
                to = math.radians(a_off)
                gx = circlex + radius * math.cos(to)
                gy = circley - radius * math.sin(to)
                self.canvas.create_line(circlex, circley, gx, gy,
                                        fill=f"#00{alpha}00",
                                        width=1, tags="dynamic")

        self.last_val.config(text=self.last_data)
        self.reads_val.config(text=str(self.total_reads))
        self.pts_val.config(text=str(len(self.points)))
        self.sweep_val.config(text=f"{self.sweep_angle:.1f}°")

    #  LÓGICA

    def _toggle_connect(self):
        if self.running and not self.demo_mode:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var
        baud = self.baud_var
        try:
            self.serial_conn = serial.Serial(port, baud, timeout=1)
            self.running     = True
            self.demo_mode   = False
            self.serial_thread = threading.Thread(target=self._read_serial,
                                                   daemon=True)
            self.serial_thread.start()
            self._set_status(True, f"PORT {port} : {baud}")
            self.btn_connect.config(text="DISCONNECT")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def _disconnect(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.serial_conn = None
        self._set_status(False)
        self.btn_connect.config(text="CONNECT")

    def _read_serial(self):
        """Hilo de lectura serial continua."""
        while self.running and self.serial_conn:
            try:
                raw = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                if raw:
                    self._parse_and_add(raw)
            except Exception:
                break
        self.running = False

    #  PARSING

    def _parse_and_add(self, raw: str):
        raw = raw.strip()
        if not raw:
            return

        tokens = [t.strip() for t in raw.split(",") if t.strip()]

        for token in tokens:
            try:
                parts = token.split(":")
                if len(parts) != 2:
                    continue
                angle = int(parts[0].strip())
                dist  = int(parts[1].strip())

                if not (0 <= angle <= 180):
                    continue
                if dist <= 0:
                    continue

                self.total_reads += 1
                self.last_data = f"{angle}deg  {dist} cm"
                self.sweep_angle = float(angle)

                self.points.append({
                    "angle": angle,
                    "dist":  min(dist, self.MAX_DISTANCE),
                    "age":   0,
                })
                if len(self.points) > self.MAX_POINTS:
                    self.points.pop(0)

            except (ValueError, IndexError):
                continue
    def _set_status(self, online: bool, text: str = None):
        if online:
            txt = text or "ONLINE"
            self.status_lbl.config(text=txt, fg=ACCENT)
        else:
            self.status_lbl.config(text="OFFLINE", fg="#ff3333")



if __name__ == "__main__":
    root = tk.Tk()
    app  = RadarApp(root)

    # Centrar ventana
    root.update_idletasks()
    width, height = 960, 620
    x = (root.winfo_screenwidth()  - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()