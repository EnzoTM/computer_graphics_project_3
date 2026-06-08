"""Ponto de entrada do programa — Projeto 3: Iluminação Phong.

Controles:
  WASD + Space/Shift  — movimento da câmera
  Mouse               — look-around
  Arrows              — mover a medusa (fonte de luz exterior)
  1/2/3/4/5           — toggle luzes (medusa / lampada / monitor / luz da agua / ambiente)
  +/-                 — aumentar/diminuir intensidade ambiente
  [ / ]               — diminuir/aumentar componente difusa
  R / T               — aumentar/diminuir componente especular
  Esc                 — sair
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import glfw
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    glClear,
    glClearColor,
    glDisable,
    glEnable,
    glViewport,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from camera import Camera  # noqa: E402
from scene import Scene  # noqa: E402
from utils import perspective  # noqa: E402


WINDOW_W = 1280
WINDOW_H = 720
TITLE = "Projeto 3: Iluminação Phong"


class App:
    def __init__(self) -> None:
        if not glfw.init():
            raise RuntimeError("glfw.init() failed")
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)

        self.window = glfw.create_window(WINDOW_W, WINDOW_H, TITLE, None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("glfw.create_window failed")
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)

        glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        glfw.set_key_callback(self.window, self._on_key)
        glfw.set_cursor_pos_callback(self.window, self._on_mouse_move)
        glfw.set_framebuffer_size_callback(self.window, self._on_resize)

        glClearColor(0.02, 0.05, 0.10, 1.0)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)

        self.scene = Scene()
        self.camera = Camera(position=(35.0, 12.0, 35.0), yaw=math.radians(-150.0), pitch=-0.10)

        self.last_time = time.perf_counter()
        self.last_mouse: tuple[float, float] | None = None

        # Rate-limit vars para movimentação contínua da medusa
        self._last_arrow_up    = 0.0
        self._last_arrow_down  = 0.0
        self._last_arrow_left  = 0.0
        self._last_arrow_right = 0.0

    def _on_resize(self, _win, w: int, h: int) -> None:
        glViewport(0, 0, max(1, w), max(1, h))

    def _on_key(self, _win, key, _scan, action, _mods) -> None:
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(self.window, True)

        # Toggles de luz
        elif key == glfw.KEY_1:
            self.scene.lights.jelly_on = not self.scene.lights.jelly_on
            print(f"[input] luz medusa: {'ON' if self.scene.lights.jelly_on else 'OFF'}")
        elif key == glfw.KEY_2:
            self.scene.lights.lamp_on = not self.scene.lights.lamp_on
            print(f"[input] luz lampada: {'ON' if self.scene.lights.lamp_on else 'OFF'}")
        elif key == glfw.KEY_3:
            self.scene.lights.monitor_on = not self.scene.lights.monitor_on
            print(f"[input] luz monitor: {'ON' if self.scene.lights.monitor_on else 'OFF'}")
        elif key == glfw.KEY_4:
            self.scene.lights.water_on = not self.scene.lights.water_on
            print(f"[input] luz da agua: {'ON' if self.scene.lights.water_on else 'OFF'}")
        elif key == glfw.KEY_5:
            self.scene.lights.ambient_on = not self.scene.lights.ambient_on
            print(f"[input] luz ambiente: {'ON' if self.scene.lights.ambient_on else 'OFF'}")

        # Intensidade ambiente
        elif key in (glfw.KEY_EQUAL, glfw.KEY_KP_ADD):
            self.scene.lights.ambient = min(1.0, self.scene.lights.ambient + 0.05)
            print(f"[input] ambient: {self.scene.lights.ambient:.2f}")
        elif key in (glfw.KEY_MINUS, glfw.KEY_KP_SUBTRACT):
            self.scene.lights.ambient = max(0.0, self.scene.lights.ambient - 0.05)
            print(f"[input] ambient: {self.scene.lights.ambient:.2f}")

        # Componente difusa
        elif key == glfw.KEY_RIGHT_BRACKET:
            self.scene.lights.diffuse_mult = min(2.0, self.scene.lights.diffuse_mult + 0.1)
            print(f"[input] diffuse_mult: {self.scene.lights.diffuse_mult:.2f}")
        elif key == glfw.KEY_LEFT_BRACKET:
            self.scene.lights.diffuse_mult = max(0.0, self.scene.lights.diffuse_mult - 0.1)
            print(f"[input] diffuse_mult: {self.scene.lights.diffuse_mult:.2f}")

        # Componente especular
        elif key == glfw.KEY_R:
            self.scene.lights.specular_mult = min(2.0, self.scene.lights.specular_mult + 0.1)
            print(f"[input] specular_mult: {self.scene.lights.specular_mult:.2f}")
        elif key == glfw.KEY_T:
            self.scene.lights.specular_mult = max(0.0, self.scene.lights.specular_mult - 0.1)
            print(f"[input] specular_mult: {self.scene.lights.specular_mult:.2f}")

    def _on_mouse_move(self, _win, x: float, y: float) -> None:
        if self.last_mouse is None:
            self.last_mouse = (x, y)
            return
        lx, ly = self.last_mouse
        dx = x - lx
        dy = ly - y
        self.last_mouse = (x, y)
        self.camera.add_yaw_pitch(dx, dy)

    def _process_held_keys(self, dt: float) -> None:
        win = self.window
        fwd = side = vert = 0.0
        if glfw.get_key(win, glfw.KEY_W) == glfw.PRESS:
            fwd += 1.0
        if glfw.get_key(win, glfw.KEY_S) == glfw.PRESS:
            fwd -= 1.0
        if glfw.get_key(win, glfw.KEY_A) == glfw.PRESS:
            side -= 1.0
        if glfw.get_key(win, glfw.KEY_D) == glfw.PRESS:
            side += 1.0
        if glfw.get_key(win, glfw.KEY_SPACE) == glfw.PRESS:
            vert += 1.0
        if glfw.get_key(win, glfw.KEY_LEFT_SHIFT) == glfw.PRESS:
            vert -= 1.0
        self.camera.move(fwd, side, vert, dt)

        now = time.perf_counter()
        step = self.scene.JELLY_STEP

        if glfw.get_key(win, glfw.KEY_UP) == glfw.PRESS:
            if now - self._last_arrow_up > 0.08:
                self.scene.translate_jelly_step(dz=-step)
                self._last_arrow_up = now
        if glfw.get_key(win, glfw.KEY_DOWN) == glfw.PRESS:
            if now - self._last_arrow_down > 0.08:
                self.scene.translate_jelly_step(dz=+step)
                self._last_arrow_down = now
        if glfw.get_key(win, glfw.KEY_LEFT) == glfw.PRESS:
            if now - self._last_arrow_left > 0.08:
                self.scene.translate_jelly_step(dx=-step)
                self._last_arrow_left = now
        if glfw.get_key(win, glfw.KEY_RIGHT) == glfw.PRESS:
            if now - self._last_arrow_right > 0.08:
                self.scene.translate_jelly_step(dx=+step)
                self._last_arrow_right = now

    def run(self) -> None:
        while not glfw.window_should_close(self.window):
            now = time.perf_counter()
            dt = min(now - self.last_time, 0.1)
            self.last_time = now

            self._process_held_keys(dt)
            self.scene.update(dt)

            w, h = glfw.get_framebuffer_size(self.window)
            aspect = w / max(1, h)
            proj = perspective(60.0, aspect, 0.1, 600.0)
            view = self.camera.view_matrix()

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.scene.draw(view, proj, self.camera.position)

            glfw.swap_buffers(self.window)
            glfw.poll_events()

        glfw.terminate()


def main() -> int:
    GREEN = "\033[32m"
    RESET = "\033[0m"
    controls = (
        "[main] controls: WASD + Space/Shift, mouse look, "
        "Arrows=medusa, 1/2/3/4/5=toggle luzes, +/-=ambient, [/]=difuso, R/T=especular, Esc"
    )
    print("[main] starting submarine scene (Projeto 3: Iluminação Phong)")
    print(f"{GREEN}{controls}{RESET}")
    app = App()
    print(f"{GREEN}{controls}{RESET}")
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
