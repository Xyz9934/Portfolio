import logging
import math
import os
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.video import Video
from kivy.uix.widget import Widget
from plyer import filechooser

from assistant_memory import ensure_assistant_storage, get_due_reminders, mark_task_reminder_sent
from brain_runtime import clear_pending_pc_command, get_pending_pc_command, has_pending_pc_command
from cognitive_background import run_background_cognition_tick
from control_profile import answer_badge, normalize_control_mode, profile_to_label
from debug_runtime import format_debug_snapshot, read_debug_snapshot
from desktop_voice import listen_once, microphone_available, start_wake_listener
from emotion_brain import detect_emotion_from_text
from initiative_engine import peek_initiative_suggestion
from learning_logger import log_interaction
from mobile_voice_core import set_voice_style, speak
from pc_control import execute_pc_command, is_confirmation_reply, is_positive_confirmation
from personality_engine import get_voice_style
from presence_engine import get_presence_prompt
from routine_brain import (
    can_handle_routine_command,
    ensure_routine_storage,
    get_due_scheduled_routines,
    get_routine_names,
    handle_routine_command,
    mark_schedule_ran,
)
from storage_status import ensure_local_storage_files
from thinking_engine import set_planner_callback

logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.WARNING)

Window.clearcolor = (0.03, 0.05, 0.08, 1)

VIDEO_BACKGROUND = r"C:\Users\DARK_SOUL\Downloads\sukuna-crimson-dominion.960x540.mp4"
_qa_engine = None
_screen_vision = None
_semantic_brain = None


def normalize_reply_text(reply):
    if isinstance(reply, str):
        return reply.strip()
    if isinstance(reply, dict):
        message = reply.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        for key in ("final_answer", "answer", "text"):
            value = reply.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(reply).strip()
    if reply is None:
        return ""
    return str(reply).strip()


def get_qa_engine():
    global _qa_engine
    if _qa_engine is None:
        import qa_engine as module

        _qa_engine = module
    return _qa_engine


def get_screen_vision():
    global _screen_vision
    if _screen_vision is None:
        import screen_vision as module

        _screen_vision = module
    return _screen_vision


def get_semantic_brain():
    global _semantic_brain
    if _semantic_brain is None:
        import semantic_brain as module

        _semantic_brain = module
    return _semantic_brain


class GlassPanel(BoxLayout):
    def __init__(self, fill=(0.09, 0.11, 0.15, 0.34), stroke=(0.86, 0.95, 1, 0.62), radius=dp(24), **kwargs):
        super().__init__(**kwargs)
        self.fill = fill
        self.stroke = stroke
        self.radius = radius
        with self.canvas.before:
            Color(*self.fill)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            Color(*self.stroke)
            self.border_line = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, self.radius], width=1.05)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rounded_rectangle = [self.x, self.y, self.width, self.height, self.radius]


class DismissibleMiniPanel(GlassPanel):
    def __init__(self, title="PANEL", dismiss_callback=None, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.dismiss_callback = dismiss_callback
        self.panel_title = title
        self._touch_start = None
        self.padding = dp(10)
        self.spacing = dp(4)
        self.size_hint_y = None

        self.title_label = Label(
            text=title,
            halign="left",
            valign="middle",
            color=(0.96, 0.99, 1, 0.96),
            font_size="11sp",
            size_hint_y=None,
            height=dp(16),
        )
        self.title_label.bind(size=self._fit_text)
        self.body_label = Label(
            text="",
            halign="left",
            valign="top",
            color=(0.90, 0.96, 1, 0.88),
            font_size="11sp",
            size_hint=(1, 1),
            markup=False,
        )
        self.body_label.bind(size=self._fit_text)
        self.add_widget(self.title_label)
        self.add_widget(self.body_label)

    def _fit_text(self, instance, *args):
        instance.text_size = instance.size

    def set_content(self, title, body):
        self.panel_title = title
        self.title_label.text = f"{title}  |  swipe right to hide"
        self.body_label.text = body

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start = touch.pos
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._touch_start and self.collide_point(*touch.pos):
            dx = touch.pos[0] - self._touch_start[0]
            dy = abs(touch.pos[1] - self._touch_start[1])
            if dx > dp(90) and dy < dp(60):
                if self.dismiss_callback:
                    self.dismiss_callback(self)
                self._touch_start = None
                return True
        self._touch_start = None
        return super().on_touch_up(touch)


class DeckButton(Button):
    def __init__(self, fill=(0.10, 0.13, 0.18, 0.42), stroke=(0.86, 0.95, 1, 0.78), text_color=(0.97, 0.99, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.fill = fill
        self.stroke = stroke
        self.text_color = text_color
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = self.text_color
        self.bold = True
        self.font_size = "16sp"
        with self.canvas.before:
            Color(*self.fill)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
            Color(*self.stroke)
            self.border_line = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, dp(18)], width=1.05)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rounded_rectangle = [self.x, self.y, self.width, self.height, dp(18)]


class ChatInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = (0.96, 0.98, 1, 1)
        self.cursor_color = (0.65, 0.92, 1, 1)
        self.hint_text_color = (0.82, 0.90, 0.96, 0.65)
        self.padding = [dp(18), dp(20), dp(18), dp(20)]
        self.font_size = "17sp"
        with self.canvas.before:
            Color(0.06, 0.09, 0.14, 0.46)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(22)])
            Color(0.88, 0.96, 1, 0.76)
            self.border_line = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, dp(22)], width=1.05)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rounded_rectangle = [self.x, self.y, self.width, self.height, dp(22)]


class RadarHub(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase = 0
        with self.canvas.before:
            Color(0.92, 0.98, 1, 0.08)
            self.outer_glow = Ellipse(pos=self.pos, size=self.size)
            Color(0.68, 0.92, 1, 0.52)
            self.ring_outer = Line(circle=(0, 0, 0), width=1.15)
            Color(0.68, 0.92, 1, 0.36)
            self.ring_mid = Line(circle=(0, 0, 0), width=1)
            Color(0.68, 0.92, 1, 0.18)
            self.ring_inner = Line(circle=(0, 0, 0), width=1)
            Color(0.90, 0.98, 1, 0.72)
            self.sweep = Line(points=[], width=1.2)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        cx = self.center_x
        cy = self.center_y
        radius = min(self.width, self.height) / 2
        self.outer_glow.pos = (cx - radius, cy - radius)
        self.outer_glow.size = (radius * 2, radius * 2)
        self.ring_outer.circle = (cx, cy, radius * 0.92)
        self.ring_mid.circle = (cx, cy, radius * 0.66)
        self.ring_inner.circle = (cx, cy, radius * 0.36)
        self._update_sweep()

    def animate(self, phase):
        self.phase = phase
        self._update_sweep()

    def _update_sweep(self):
        radius = min(self.width, self.height) / 2
        angle = self.phase * math.pi * 2
        cx = self.center_x
        cy = self.center_y
        x = cx + math.cos(angle) * radius * 0.88
        y = cy + math.sin(angle) * radius * 0.88
        self.sweep.points = [cx, cy, x, y]


class MessageBubble(AnchorLayout):
    def __init__(self, text, kind="assistant", **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.padding = [0, dp(2), 0, dp(2)]
        self.kind = kind

        if kind == "user":
            self.anchor_x = "right"
            self.fill = (0.03, 0.03, 0.04, 0.96)
            self.stroke = (0.18, 0.18, 0.20, 0.88)
            self.text_color = (0.98, 0.98, 0.99, 1)
        elif kind == "status":
            self.anchor_x = "center"
            self.fill = (0.16, 0.20, 0.26, 0.32)
            self.stroke = (0.88, 0.95, 1, 0.30)
            self.text_color = (0.95, 0.98, 1, 0.94)
        else:
            self.anchor_x = "left"
            self.fill = (0.98, 0.98, 0.99, 0.96)
            self.stroke = (0.86, 0.89, 0.94, 0.95)
            self.text_color = (0.08, 0.10, 0.13, 1)

        self.anchor_y = "top"
        self.card = BoxLayout(orientation="vertical", size_hint=(None, None), padding=[dp(18), dp(14), dp(18), dp(14)])
        with self.card.canvas.before:
            Color(*self.fill)
            self.card_bg = RoundedRectangle(pos=self.card.pos, size=self.card.size, radius=[dp(20)])
            Color(*self.stroke)
            self.card_border = Line(rounded_rectangle=[self.card.x, self.card.y, self.card.width, self.card.height, dp(20)], width=1.0)

        self.label = Label(
            text=text,
            markup=True,
            halign="left",
            valign="middle",
            color=self.text_color,
            font_size="17sp" if kind != "status" else "14sp",
            size_hint=(None, None),
        )
        self.card.add_widget(self.label)
        self.add_widget(self.card)

        self.card.bind(pos=self._redraw_card, size=self._redraw_card)
        self.bind(width=self._update_layout)
        self.label.bind(texture_size=self._update_layout)
        Clock.schedule_once(self._update_layout, 0)

    def _redraw_card(self, *args):
        self.card_bg.pos = self.card.pos
        self.card_bg.size = self.card.size
        self.card_border.rounded_rectangle = [self.card.x, self.card.y, self.card.width, self.card.height, dp(20)]

    def _update_layout(self, *args):
        max_width = dp(520)
        if self.width:
            max_width = min(max_width, self.width * (0.82 if self.kind == "status" else 0.68))

        max_width = max(max_width, dp(220))
        inner_width = max_width - dp(36)
        self.label.text_size = (inner_width, None)
        self.label.texture_update()
        self.label.size = (inner_width, self.label.texture_size[1])
        self.card.size = (max_width, self.label.texture_size[1] + dp(26))
        self.height = self.card.height + dp(6)


class FridayUI(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase = 0
        self.awaiting_wake_command = False
        self.screen_share_enabled = False
        self.screen_watch_busy = False
        self.last_screen_watch_summary = ""
        self.processing_bubble = None
        self.routine_buttons = []
        self.video_enabled = False
        self.show_planner_stream = False
        self.answer_mode = normalize_control_mode("auto")
        self.mode_picker = None
        self.request_counter = 0
        self.active_request_id = 0
        self.last_user_input = ""
        self.last_assistant_reply = ""
        self.last_reply_profile = normalize_control_mode("auto")

        self.video_widget = None
        self.video_source_exists = os.path.exists(VIDEO_BACKGROUND)

        self.background_layer = FloatLayout(size_hint=(1, 1))
        self.add_widget(self.background_layer)

        self.fx_layer = Widget()
        with self.fx_layer.canvas.before:
            self.base_overlay_color = Color(0.02, 0.04, 0.07, 0.42 if self.video_enabled else 1)
            self.base_overlay = Rectangle(pos=self.pos, size=self.size)
            Color(0.10, 0.16, 0.24, 0.10)
            self.left_band = Rectangle(pos=self.pos, size=(self.width * 0.42, self.height))
            Color(0.30, 0.08, 0.32, 0.08)
            self.right_band = Rectangle(pos=(self.width * 0.62, 0), size=(self.width * 0.38, self.height))
            Color(0.72, 0.92, 1, 0.07)
            self.scanline = Rectangle(pos=self.pos, size=(self.width, dp(44)))
            Color(0.72, 0.92, 1, 0.05)
            self.grid_lines = [Line(points=[], width=1) for _ in range(14)]
        self.background_layer.add_widget(self.fx_layer)
        self.bind(pos=self._update_background, size=self._update_background)

        shell = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12), size_hint=(1, 1))
        self.add_widget(shell)

        top_bar = GlassPanel(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(112),
            padding=dp(18),
            spacing=dp(16),
            fill=(0.08, 0.10, 0.14, 0.28),
            stroke=(0.90, 0.97, 1, 0.72),
        )
        shell.add_widget(top_bar)

        title_box = BoxLayout(orientation="vertical", size_hint_x=0.44, spacing=dp(4))
        self.title_label = Label(
            text="[b]FRIDAY // COMMAND DECK[/b]",
            markup=True,
            halign="left",
            valign="middle",
            color=(0.98, 0.99, 1, 1),
            font_size="24sp",
        )
        self.title_label.bind(size=self._fit_text)
        self.sub_label = Label(
            text="Adaptive AI bridge for desktop control, memory, voice, and routines",
            halign="left",
            valign="middle",
            color=(0.88, 0.94, 0.98, 0.86),
            font_size="13sp",
        )
        self.sub_label.bind(size=self._fit_text)
        title_box.add_widget(self.title_label)
        title_box.add_widget(self.sub_label)
        top_bar.add_widget(title_box)

        center_hud = AnchorLayout(size_hint_x=0.18)
        self.radar = RadarHub(size_hint=(None, None), size=(dp(88), dp(88)))
        center_hud.add_widget(self.radar)
        top_bar.add_widget(center_hud)

        status_panel = GlassPanel(
            orientation="vertical",
            size_hint_x=0.38,
            padding=dp(12),
            spacing=dp(2),
            fill=(0.09, 0.11, 0.15, 0.24),
            stroke=(0.92, 0.97, 1, 0.64),
        )
        self.clock_label = Label(
            text="",
            markup=True,
            halign="right",
            valign="middle",
            color=(0.98, 0.99, 1, 1),
            font_size="22sp",
        )
        self.clock_label.bind(size=self._fit_text)
        self.status_label = Label(
            text="[b]ONLINE[/b]  |  VOICE READY  |  DESKTOP LINKED",
            markup=True,
            halign="right",
            valign="middle",
            color=(0.90, 0.96, 1, 0.86),
            font_size="12sp",
        )
        self.status_label.bind(size=self._fit_text)
        status_panel.add_widget(self.clock_label)
        status_panel.add_widget(self.status_label)
        top_bar.add_widget(status_panel)

        self.routine_bar = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(10))
        shell.add_widget(self.routine_bar)
        self.refresh_routine_bar()

        center_panel = GlassPanel(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(12),
            fill=(0.08, 0.10, 0.14, 0.20),
            stroke=(0.86, 0.95, 1, 0.42),
        )
        shell.add_widget(center_panel)

        hint_bar = BoxLayout(size_hint_y=None, height=dp(26))
        hint = Label(
            text="Chat-first console with live voice, missions, storage memory, and desktop control",
            halign="left",
            valign="middle",
            color=(0.92, 0.97, 1, 0.88),
            font_size="12sp",
        )
        hint.bind(size=self._fit_text)
        hint_bar.add_widget(hint)
        self.mode_hint = Label(
            text="MODE: AUTO",
            halign="right",
            valign="middle",
            color=(0.90, 0.96, 1, 0.82),
            font_size="12sp",
            size_hint_x=0.26,
        )
        self.mode_hint.bind(size=self._fit_text)
        hint_bar.add_widget(self.mode_hint)

        self.restore_debug_btn = DeckButton(text="DEBUG", size_hint_x=0.09, font_size="11sp", fill=(0.10, 0.13, 0.18, 0.74))
        self.restore_debug_btn.bind(on_press=lambda instance: self.restore_signal_card("debug"))
        hint_bar.add_widget(self.restore_debug_btn)

        self.restore_suggestion_btn = DeckButton(text="SUGGEST", size_hint_x=0.11, font_size="11sp", fill=(0.10, 0.13, 0.18, 0.74))
        self.restore_suggestion_btn.bind(on_press=lambda instance: self.restore_signal_card("suggestion"))
        hint_bar.add_widget(self.restore_suggestion_btn)
        center_panel.add_widget(hint_bar)

        self.signal_row = BoxLayout(size_hint_y=None, height=dp(84), spacing=dp(10))
        center_panel.add_widget(self.signal_row)

        self.debug_panel = DismissibleMiniPanel(
            title="COGNITIVE DEBUG",
            dismiss_callback=lambda panel: self.hide_signal_card("debug"),
            height=dp(84),
            fill=(0.07, 0.09, 0.13, 0.76),
            stroke=(0.72, 0.92, 1, 0.38),
        )
        self.signal_row.add_widget(self.debug_panel)

        self.initiative_panel = DismissibleMiniPanel(
            title="FRIDAY SUGGESTION",
            dismiss_callback=lambda panel: self.hide_signal_card("suggestion"),
            height=dp(84),
            fill=(0.09, 0.12, 0.18, 0.78),
            stroke=(0.86, 0.95, 1, 0.32),
        )
        self.signal_row.add_widget(self.initiative_panel)
        self.hidden_signal_cards = set()
        self.update_signal_restore_buttons()

        self.chat = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None, padding=[0, dp(8), 0, dp(10)])
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll = ScrollView(bar_width=dp(4), scroll_type=["bars", "content"])
        self.scroll.add_widget(self.chat)
        center_panel.add_widget(self.scroll)

        if not self.video_source_exists:
            self.add_chat("Background video unavailable. Install `ffpyplayer` if you want cinematic looping video.", kind="status")
        self.add_chat("Mission routines online. Say or type `list routines`, `run routine focus mode`, or `schedule routine focus mode every morning`.", kind="status")

        bottom_bar = GlassPanel(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(86),
            padding=dp(10),
            spacing=dp(10),
            fill=(0.08, 0.10, 0.14, 0.28),
            stroke=(0.90, 0.97, 1, 0.72),
        )
        shell.add_widget(bottom_bar)

        self.input = ChatInput(
            multiline=False,
            hint_text="Message FRIDAY...",
            size_hint_x=0.40,
        )
        self.input.bind(on_text_validate=self.send)

        self.mode_btn = DeckButton(text="+", size_hint_x=0.08, fill=(0.17, 0.14, 0.22, 0.84))
        self.mode_btn.bind(on_press=self.open_mode_picker)

        mic_btn = DeckButton(text="MIC", size_hint_x=0.11)
        mic_btn.bind(on_press=self.listen_mic)

        self.screen_btn = DeckButton(text="SHARE", size_hint_x=0.12, fill=(0.11, 0.16, 0.20, 0.78))
        self.screen_btn.bind(on_press=self.toggle_screen_share)

        send_btn = DeckButton(text="SEND", size_hint_x=0.12, fill=(0.14, 0.19, 0.24, 0.82))
        send_btn.bind(on_press=self.send)

        upload_btn = DeckButton(text="PDF", size_hint_x=0.10, fill=(0.20, 0.18, 0.24, 0.80))
        upload_btn.bind(on_press=self.upload_pdf)

        bottom_bar.add_widget(self.mode_btn)
        bottom_bar.add_widget(self.input)
        bottom_bar.add_widget(mic_btn)
        bottom_bar.add_widget(self.screen_btn)
        bottom_bar.add_widget(send_btn)
        bottom_bar.add_widget(upload_btn)

        self.update_mode_hint()
        self.update_header()
        Clock.schedule_interval(self.update_header, 1)
        Clock.schedule_interval(self.animate_background, 1 / 16)
        Clock.schedule_interval(self.check_due_reminders, 30)
        Clock.schedule_interval(self.check_due_routines, 30)
        Clock.schedule_interval(self.screen_watch_tick, 4)
        Clock.schedule_interval(self.check_presence, 60)
        Clock.schedule_interval(self.update_debug_panel, 2)
        Clock.schedule_interval(self.update_initiative_panel, 4)
        Clock.schedule_interval(self.run_background_cognition, 300)
        Clock.schedule_once(self.start_background_video, 0.2)

        if microphone_available():
            Clock.schedule_once(self.start_wake_mode, 0.8)

    def _restart_video(self, *args):
        try:
            self.video_widget.state = "stop"
            self.video_widget.state = "play"
        except Exception:
            pass

    def start_background_video(self, *args):
        if self.video_widget is not None or not self.video_source_exists:
            return
        try:
            video = Video(source=VIDEO_BACKGROUND, state="play", options={"eos": "loop"}, volume=0)
            video.size_hint = (1, 1)
            video.pos_hint = {"x": 0, "y": 0}
            video.bind(eos=self._restart_video)
            self.video_widget = video
            self.video_enabled = True
            self.background_layer.add_widget(video, index=0)
            self.base_overlay_color.rgba = (0.02, 0.04, 0.07, 0.30)
        except Exception:
            self.video_widget = None
            self.video_enabled = False

    def start_wake_mode(self, *args):
        try:
            start_wake_listener(lambda: Clock.schedule_once(lambda dt: self.on_wake_word()), wake_word="friday")
            self.add_chat("Wake word armed. Say `friday` to start voice input.", kind="status")
        except Exception:
            self.add_chat("Wake word listener could not start on this PC.", kind="status")

    def _fit_text(self, instance, *args):
        instance.text_size = instance.size

    def _update_background(self, *args):
        self.base_overlay.pos = self.pos
        self.base_overlay.size = self.size
        self.left_band.pos = self.pos
        self.left_band.size = (self.width * 0.42, self.height)
        self.right_band.pos = (self.x + self.width * 0.62, self.y)
        self.right_band.size = (self.width * 0.38, self.height)
        self._update_scanline()
        self._update_grid()

    def _update_scanline(self):
        y = self.y + ((self.phase * self.height) % max(self.height, 1))
        self.scanline.pos = (self.x, y)
        self.scanline.size = (self.width, dp(38))

    def _update_grid(self):
        if self.width <= 0 or self.height <= 0:
            return
        vertical_count = 8
        horizontal_count = 6
        for index in range(vertical_count):
            x = self.x + (index + 1) * (self.width / (vertical_count + 1))
            self.grid_lines[index].points = [x, self.y, x, self.top]
        for index in range(horizontal_count):
            y = self.y + (index + 1) * (self.height / (horizontal_count + 1))
            self.grid_lines[vertical_count + index].points = [self.x, y, self.right, y]

    def update_header(self, *args):
        now = datetime.now()
        self.clock_label.text = f"[b]{now.strftime('%I:%M:%S %p')}[/b]"
        self.status_label.text = f"{now.strftime('%A')}  |  {now.strftime('%d %B %Y')}  |  [b]VOICE READY[/b]"

    def animate_background(self, dt):
        self.phase = (self.phase + dt * 0.12) % 1
        glow = 0.5 + 0.5 * math.sin(Clock.get_boottime() * 0.8)
        self.left_band.size = (self.width * (0.36 + glow * 0.09), self.height)
        self.right_band.pos = (self.right - self.width * (0.30 + (1 - glow) * 0.08), self.y)
        self.right_band.size = (self.width * (0.30 + (1 - glow) * 0.08), self.height)
        self._update_scanline()
        self.radar.animate(self.phase)

    def add_chat(self, text, kind="assistant"):
        bubble = MessageBubble(text=text, kind=kind)
        self.chat.add_widget(bubble)
        Clock.schedule_once(lambda dt: self.scroll_down(), 0.05)
        return bubble

    def get_answer_mode_label(self, mode=None):
        return profile_to_label(mode or self.answer_mode)

    def update_mode_hint(self):
        label = self.get_answer_mode_label()
        self.mode_hint.text = f"MODE: {label}"

    def update_signal_restore_buttons(self):
        self.restore_debug_btn.opacity = 1 if "debug" in self.hidden_signal_cards else 0.55
        self.restore_suggestion_btn.opacity = 1 if "suggestion" in self.hidden_signal_cards else 0.55

    def hide_signal_card(self, card_name):
        panel = self.debug_panel if card_name == "debug" else self.initiative_panel
        if panel.parent is self.signal_row:
            self.signal_row.remove_widget(panel)
            self.hidden_signal_cards.add(card_name)
            self.update_signal_restore_buttons()

    def restore_signal_card(self, card_name):
        if card_name not in self.hidden_signal_cards:
            return
        panel = self.debug_panel if card_name == "debug" else self.initiative_panel
        if panel.parent is None:
            insert_index = 0 if card_name == "debug" else len(self.signal_row.children)
            self.signal_row.add_widget(panel, index=insert_index)
            self.hidden_signal_cards.discard(card_name)
            self.update_signal_restore_buttons()

    def update_debug_panel(self, dt):
        try:
            snapshot = read_debug_snapshot()
            compact = format_debug_snapshot(snapshot).replace("COGNITIVE DEBUG\n", "")
            compact = compact[:220].replace("\n\n", "\n").strip() or "Waiting for a reply..."
            self.debug_panel.set_content("COGNITIVE DEBUG", compact)
        except Exception:
            self.debug_panel.set_content("COGNITIVE DEBUG", "Unavailable.")

    def update_initiative_panel(self, dt):
        try:
            item = peek_initiative_suggestion()
        except Exception:
            item = None
        if not item:
            self.initiative_panel.set_content("FRIDAY SUGGESTION", "No proactive suggestion yet.")
            return
        message = (item.get("message") or "").strip()
        reason = (item.get("reason") or "").strip().replace("_", " ")
        priority = float(item.get("priority") or 0.0)
        compact = f"{message[:140]}\n[{reason} | priority {priority:.2f}]"
        self.initiative_panel.set_content("FRIDAY SUGGESTION", compact)

    def open_mode_picker(self, instance):
        if self.mode_picker:
            self.mode_picker.dismiss()

        picker = ModalView(size_hint=(None, None), size=(dp(420), dp(760)), background_color=(0, 0, 0, 0.18), auto_dismiss=True)
        panel = GlassPanel(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(10),
            fill=(0.08, 0.10, 0.14, 0.94),
            stroke=(0.90, 0.97, 1, 0.72),
            size_hint_y=None,
        )
        panel.bind(minimum_height=panel.setter("height"))
        title = Label(
            text="[b]Choose Reply Mode[/b]",
            markup=True,
            halign="left",
            valign="middle",
            color=(0.98, 0.99, 1, 1),
            font_size="18sp",
            size_hint_y=None,
            height=dp(30),
        )
        title.bind(size=self._fit_text)
        panel.add_widget(title)

        options = [
            (
                {
                    "depth_mode": "safe",
                    "response_style": "default",
                    "force_fast": True,
                    "safe_mode": True,
                    "ollama_strategy": "quick",
                    "mode_label": "QUICK / SAFE REPLY",
                    "badge_label": "Quick / Safe Reply",
                },
                "QUICK / SAFE REPLY",
                "Uses Ollama 3.2 for the fastest safe answer",
            ),
            (
                {
                    "depth_mode": "deep",
                    "response_style": "default",
                    "ollama_strategy": "deep",
                    "mode_label": "INTERMEDIATE POWER",
                    "badge_label": "Intermediate Power",
                },
                "INTERMEDIATE POWER",
                "Uses Ollama 3 for stronger local reasoning",
            ),
            (
                {
                    "depth_mode": "deep",
                    "response_style": "default",
                    "ollama_strategy": "deep",
                    "full_research": True,
                    "mode_label": "RESEARCH",
                    "badge_label": "Research",
                },
                "RESEARCH",
                "Uses FRIDAY's full stack: memory, critic, simulation, and all available providers",
            ),
        ]
        for mode_value, button_text, subtitle in options:
            button = DeckButton(
                text=f"{button_text}\n{subtitle}",
                fill=(0.12, 0.15, 0.22, 0.86),
                size_hint_y=None,
                height=dp(56),
                font_size="14sp",
            )
            button.bind(on_press=lambda btn, selected_mode=mode_value: self.set_answer_mode(selected_mode))
            panel.add_widget(button)

        scroller = ScrollView(bar_width=dp(4))
        scroller.add_widget(panel)
        picker.add_widget(scroller)
        self.mode_picker = picker
        picker.open()

    def set_answer_mode(self, mode):
        profile = normalize_control_mode(mode if isinstance(mode, dict) else self.answer_mode)
        profile["response_style"] = self.answer_mode.get("response_style", "default")
        self.answer_mode = profile
        self.update_mode_hint()
        if self.mode_picker:
            self.mode_picker.dismiss()
            self.mode_picker = None
        self.add_chat(f"Answer mode set to {self.get_answer_mode_label()}.", kind="status")

    def set_response_style(self, style):
        profile = dict(self.answer_mode)
        profile["response_style"] = (style or "default").strip().lower()
        self.answer_mode = normalize_control_mode(profile)
        self.update_mode_hint()
        if self.mode_picker:
            self.mode_picker.dismiss()
            self.mode_picker = None
        self.add_chat(f"Response style set to {self.answer_mode['response_style'].replace('_', ' ')}.", kind="status")

    def toggle_better_question_mode(self):
        profile = dict(self.answer_mode)
        profile["ask_better_question"] = not profile.get("ask_better_question", False)
        self.answer_mode = normalize_control_mode(profile)
        self.update_mode_hint()
        if self.mode_picker:
            self.mode_picker.dismiss()
            self.mode_picker = None
        state = "enabled" if self.answer_mode.get("ask_better_question") else "disabled"
        self.add_chat(f"Ask-better-question mode {state}.", kind="status")

    def refine_last_answer(self):
        if self.mode_picker:
            self.mode_picker.dismiss()
            self.mode_picker = None
        if not self.last_user_input:
            self.add_chat("No previous answer available to refine yet.", kind="status")
            return
        refine_profile = normalize_control_mode({"depth_mode": "deep", "response_style": self.answer_mode.get("response_style", "default"), "refine_last": True})
        prompt = f"Refine this answer for the same user request.\n\nOriginal user request:\n{self.last_user_input}\n\nPrevious answer:\n{self.last_assistant_reply}"
        self.start_request(prompt, answer_mode=refine_profile)

    def refresh_routine_bar(self, *args):
        self.routine_bar.clear_widgets()
        self.routine_buttons = []
        for name in get_routine_names(limit=4):
            button = DeckButton(
                text=name.upper(),
                fill=(0.10, 0.12, 0.18, 0.76),
                size_hint_x=1,
                font_size="15sp",
            )
            button.bind(on_press=lambda instance, routine_name=name: self.start_request(f"run routine {routine_name}"))
            self.routine_bar.add_widget(button)
            self.routine_buttons.append(button)

    def scroll_down(self):
        self.scroll.scroll_y = 0

    def send(self, instance):
        user = self.input.text.strip()
        if not user:
            return
        self.start_request(user, answer_mode=self.answer_mode)

    def start_request(self, user, answer_mode="auto"):
        self.request_counter += 1
        self.active_request_id = self.request_counter
        control = normalize_control_mode(answer_mode)
        self.add_chat(user, kind="user")
        self.input.text = ""
        mode_label = self.get_answer_mode_label(control)
        self.processing_bubble = self.add_chat(f"FRIDAY is thinking... [{mode_label}]", kind="status")
        self.plan_bubble = None
        thread = threading.Thread(target=self.process, args=(user, control, self.active_request_id), daemon=True)
        thread.start()

    def listen_mic(self, instance):
        if not microphone_available():
            self.add_chat("Microphone is not available on this PC.", kind="status")
            return

        self.awaiting_wake_command = True
        self.add_chat("Listening for your command...", kind="status")
        listen_once(
            on_result=lambda text: Clock.schedule_once(lambda dt: self.on_mic_result(text)),
            on_error=lambda error: Clock.schedule_once(lambda dt: self.on_mic_error(error)),
        )

    def on_wake_word(self):
        if self.awaiting_wake_command:
            return
        self.awaiting_wake_command = True
        self.add_chat("Wake word detected. Listening...", kind="status")
        try:
            speak("Yes?")
        except Exception:
            pass
        listen_once(
            on_result=lambda text: Clock.schedule_once(lambda dt: self.on_mic_result(text)),
            on_error=lambda error: Clock.schedule_once(lambda dt: self.on_mic_error(error)),
        )

    def on_mic_result(self, text):
        self.awaiting_wake_command = False
        emotion = detect_emotion_from_text(text)
        if emotion and emotion != "neutral":
            self.add_chat(f"Emotion signal detected: {emotion}.", kind="status")
        self.start_request(text)

    def on_mic_error(self, error):
        self.awaiting_wake_command = False
        self.add_chat(error, kind="status")

    def upload_pdf(self, instance):
        pdf_path = filechooser.open_file(filters=[("PDF files", "*.pdf")])
        if pdf_path:
            get_semantic_brain().ingest_pdf(pdf_path[0])
            self.add_chat("PDF uploaded and indexed into memory.", kind="status")

    def toggle_screen_share(self, instance):
        self.screen_share_enabled = not self.screen_share_enabled
        if self.screen_share_enabled:
            self.screen_btn.text = "STOP"
            self.add_chat("Continuous screen copilot is now watching your screen.", kind="status")
            self.last_screen_watch_summary = ""
            Clock.schedule_once(lambda dt: self.minimize_for_screen_share(), 0.2)
            threading.Thread(target=self.run_screen_watch_capture, kwargs={"announce": True}, daemon=True).start()
        else:
            self.screen_btn.text = "SHARE"
            self.add_chat("Continuous screen copilot stopped watching your screen.", kind="status")

    def minimize_for_screen_share(self):
        try:
            Window.minimize()
        except Exception:
            pass

    def screen_watch_tick(self, dt):
        if not self.screen_share_enabled or self.screen_watch_busy:
            return
        thread = threading.Thread(target=self.run_screen_watch_capture, kwargs={"announce": False}, daemon=True)
        thread.start()

    def run_screen_watch_capture(self, announce=False):
        self.screen_watch_busy = True
        try:
            snapshot = get_screen_vision().capture_screen_snapshot(save_to_memory=True)
            if snapshot.get("error"):
                if announce:
                    Clock.schedule_once(lambda dt: self.add_chat(snapshot["error"], kind="status"))
                return

            summary = snapshot.get("summary", "").strip()
            if announce:
                message = f"Screen sharing active. Latest readable text:\n\n{summary or 'No readable text detected.'}"
                Clock.schedule_once(lambda dt, m=message: self.add_chat(m, kind="status"))

            if summary:
                self.last_screen_watch_summary = summary
        finally:
            self.screen_watch_busy = False

    def check_due_reminders(self, dt):
        reminders = get_due_reminders()
        for task in reminders[:3]:
            due = f" Due: {task['due']}." if task.get("due") else ""
            self.add_chat(f"Reminder: {task.get('title', '')}.{due}", kind="status")
            mark_task_reminder_sent(task.get("id"))
            try:
                speak(f"Reminder: {task.get('title', '')}")
            except Exception:
                pass

    def check_due_routines(self, dt):
        for item in get_due_scheduled_routines():
            routine_name = item.get("routine", "")
            if not routine_name:
                continue
            mark_schedule_ran(routine_name)
            reply = handle_routine_command(f"run routine {routine_name}", lambda step: execute_pc_command(step))
            self.add_chat(f"Scheduled mission triggered.\n{reply}", kind="status")
            try:
                speak(f"Scheduled routine {routine_name} is running.")
            except Exception:
                pass

    def check_presence(self, dt):
        if not getattr(self, "screen_share_enabled", False):
            return
        try:
            prompt = get_presence_prompt()
        except Exception:
            prompt = ""

        if not prompt:
            return

        self.add_chat(prompt, kind="assistant")
        try:
            set_voice_style(get_voice_style(prompt, prompt))
            speak(prompt)
        except Exception:
            pass

    def run_background_cognition(self, dt):
        try:
            run_background_cognition_tick()
        except Exception:
            pass

    def process(self, user, answer_mode="auto", request_id=0):
        set_planner_callback(self.update_plan_stream if self.show_planner_stream else None)
        try:
            if has_pending_pc_command() and is_confirmation_reply(user):
                if is_positive_confirmation(user):
                    pending = get_pending_pc_command()
                    clear_pending_pc_command()
                    result = execute_pc_command(pending, allow_risky=True)
                    if isinstance(result, dict):
                        reply = result.get("message", "I still need confirmation for that action.")
                    else:
                        reply = result or "Confirmed."
                else:
                    clear_pending_pc_command()
                    reply = "Cancelled the pending PC action."
            elif has_pending_pc_command():
                reply = "I still have a pending PC action. Reply yes to continue or no to cancel."
            elif get_screen_vision().is_start_screen_share_command(user):
                self.screen_share_enabled = True
                self.last_screen_watch_summary = ""
                Clock.schedule_once(lambda dt: setattr(self.screen_btn, "text", "STOP"))
                self.run_screen_watch_capture(announce=True)
                reply = "Continuous screen copilot started."
            elif get_screen_vision().is_stop_screen_share_command(user):
                self.screen_share_enabled = False
                Clock.schedule_once(lambda dt: setattr(self.screen_btn, "text", "SHARE"))
                reply = "Continuous screen copilot stopped."
            else:
                reply = get_qa_engine().ask_friday(user, answer_mode=answer_mode)
                if can_handle_routine_command(user):
                    Clock.schedule_once(self.refresh_routine_bar, 0)
        except Exception as exc:
            reply = f"System error occurred: {exc}"

        Clock.schedule_once(lambda dt: self.show_reply(user, reply, "", request_id, answer_mode))

    def update_plan_stream(self, text):
        if not self.show_planner_stream:
            return
        if not text:
            return
        if self.plan_bubble and self.plan_bubble.parent is self.chat:
            self.plan_bubble.label.text = text
            self.plan_bubble._update_layout()
        else:
            self.plan_bubble = self.add_chat(text, kind="status")

    def show_reply(self, user, reply, plan_preview="", request_id=0, answer_mode=None):
        if request_id and request_id != self.active_request_id:
            return
        if self.processing_bubble and self.processing_bubble.parent is self.chat:
            self.chat.remove_widget(self.processing_bubble)
        self.processing_bubble = None

        if self.plan_bubble and self.plan_bubble.parent is self.chat:
            self.chat.remove_widget(self.plan_bubble)
            self.plan_bubble = None
        clean_reply = normalize_reply_text(reply) or "Here’s the shortest reliable answer I can give right now."
        badge = answer_badge(answer_mode or self.answer_mode)
        self.add_chat(f"[b]{badge}[/b]\n{clean_reply}", kind="assistant")
        self.last_user_input = user
        self.last_assistant_reply = clean_reply
        self.last_reply_profile = normalize_control_mode(answer_mode or self.answer_mode)

        try:
            log_interaction(user, clean_reply, source="desktop_ui")
        except Exception:
            pass

        try:
            set_voice_style(get_voice_style(user, clean_reply))
            speak(clean_reply)
        except Exception:
            pass


class FridayApp(App):
    def build(self):
        ensure_local_storage_files()
        ensure_assistant_storage()
        ensure_routine_storage()
        return FridayUI()


if __name__ == "__main__":
    FridayApp().run()
