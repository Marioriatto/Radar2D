from tkinter import *
import serial
import time
import math
from random import randint
from threading import Thread
arduino_port = "COM3" 
baud_rate = 9600

def fullscreen(root):
    global is_fullscreen
    is_fullscreen = not is_fullscreen
    root.attributes('-fullscreen', is_fullscreen)

def mapScreen(x:int, y:int):
    x += int(canvas.cget("width"))/2
    y = int(canvas.cget("height"))/2-y
    return x, y

def simulate():
    global angle
    while True:
        angle += 1
        if angle == 361:
            angle = 0
        time.sleep(0.6/360)
targets = list()
angle = 0
def draw_radar(root, canvas):
    color = "#24D821"
    # circulo radar
    x0,y0 = mapScreen(200,200)
    x1,y1 = mapScreen(-200,-200)
    circulo = canvas.create_oval(x0,y0,x1,y1, outline=color,width=3)
    x0,y0 = mapScreen(0,0)
    x1,y1 = mapScreen(200 * math.cos(angle),200 * math.sin(angle))
    line = canvas.create_line(0,y0,x1,y1, fill=color, width=3)
    point = canvas.create_oval(100-3,100-3,100+3,100+3,fill=color, outline=color)
    Thread(target=simulate, daemon=True).start()
    while True:
        x0,y0 = mapScreen(0,0)
        x1,y1 = mapScreen(200 * math.cos(angle),200 * math.sin(angle))
        
        canvas.itemconfig(line,x0,y0,x1,y1)
        if angle == 0:
            xoffset = randint(10,-10)
            yoffset = randint(10,-10)
            x0 = int(canvas.itemcget(x0)) + xoffset - 3
            y0 = int(canvas.itemcget(y0)) + yoffset - 3
            x1 = int(canvas.itemcget(x1)) + xoffset + 3
            y1 = int(canvas.itemcget(y1)) + yoffset + 3
            canvas.itemconfig(point,x0,y0,x1,y1)
def serial_contact():
    global start
    start = True
    #PLANTILLA
    try:
        ser = serial.Serial(arduino_port, baud_rate, timeout=1)
        time.sleep(2)
        while True:
            if ser.in_waiting > 0:
                c = ser.readline().decode('utf-8').rstrip()
                print(c)
            if False:
                ser.write(c.encode('utf-8'))
    except KeyboardInterrupt:
        if 'ser' in locals() and ser.is_open:
            ser.close()

root = Tk()
root.title('RadarTEC')
root.resizable(width=NO, height=NO)
is_fullscreen = True
root.attributes('-fullscreen', is_fullscreen)
root.bind('<F11>',lambda event: fullscreen(root))


# PA DIBUJAR BIEN y UBICAR LOS WIDGETS
root.update_idletasks()

canvas = Canvas(root, width=root.winfo_width(), height=root.winfo_height(),bg="black")
canvas.pack(fill='both', expand=True, anchor='center')

draw_radar(root, canvas)
root.mainloop()