import tkinter as tk
from PIL import Image, ImageTk, ImageSequence


class BackgroundSystem:

    def __init__(self, root):

        self.root = root

        # Load GIF
        self.gif = Image.open("assets/background.gif")

        self.frames = []

        for frame in ImageSequence.Iterator(self.gif):

            frame = frame.resize((1200, 800))

            self.frames.append(ImageTk.PhotoImage(frame))

        self.frame_index = 0

        self.bg_label = tk.Label(root, image=self.frames[0])
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # send background to back
        self.bg_label.lower()

    def animate(self):

        self.bg_label.config(image=self.frames[self.frame_index])

        self.frame_index = (self.frame_index + 1) % len(self.frames)

        self.root.after(40, self.animate)
