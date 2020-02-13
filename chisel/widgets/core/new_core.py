import io
import json
from pathlib import Path
from random import choice

import numpy as np
from PIL import Image

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture

GRAVITY = .02
FRICTION = .9
DISLODGE_VELOCITY = 1e-3
MAX_VELOCITY = .2

IMAGE_SCALE = .75
IMAGE_DIM = 100, 100

RADIUS = R = 1
MIN_POWER = 1e-5
CHISEL_POWER = 100

BACKGROUND = str(Path("/home/salt/Documents/Python/chisel/assets",
                                 "img", "background.png"))
SOUND = tuple(str(Path('assets', 'sounds', f'00{i}.wav')) for i in range(1, 5))

BOULDER_IMAGE_PATHS = tuple(Path("/home/salt/Documents/Python/chisel/assets",
                                 "img", "boulder", f"{i}.png") for i in range(5))

def is_dislodged(velocity):
    """
    Return False if velocity isn't enough to dislodge a pebble, else return the clipped
    velocity vector.
    """
    x, y = velocity
    magnitude = (x**2 + y**2)**.5
    if magnitude < DISLODGE_VELOCITY:
        return False
    if magnitude > MAX_VELOCITY:
        x *= MAX_VELOCITY / magnitude
        y *= MAX_VELOCITY / magnitude
    return x, y


class Pebble:
    """
    This handles physics for dislodged pebbles. Deletes itself after pebbles reach the floor.
    """

    def __init__(self, index, pixel, chisel, velocity):
        self.index = index
        self.pixel = pixel
        self.chisel = chisel
        self.velocity = velocity
        self.update = Clock.schedule_interval(self.step, 1 / 30)

    def step(self, dt):
        """Gravity Physics"""
        x, y = self.pixel.x, self.pixel.y
        vx, vy = self.velocity
        vx *= FRICTION
        vy *= FRICTION
        vy -= GRAVITY
        # Bounce off walls
        if not 0 < x < 1:
            vx *= -1

        self.velocity = vx, vy
        self.pixel.x, self.pixel.y = x + vx, max(0, y + vy)
        chisel = self.chisel
        self.pixel.rescale(chisel.width, chisel.height)

        if not self.pixel.y:
            self.update.cancel()
            del chisel.pebbles[self.index]  # Remove reference // kill this object


class Pixel(Rectangle):
    """
    Kivy Rectangle with unscaled coordinates (x, y) and color information.
    """

    def __init__(self, x, y, z, screen_width, screen_height, color, *args, **kwargs):
        self.x = x
        self.y = y
        self.z = z
        self.color = Color(*color)
        super().__init__(*args, **kwargs)
        self.rescale(screen_width, screen_height)

    def rescale(self, screen_width, screen_height):
        self.pos = self.x * screen_width, self.y * screen_height


class Chisel(Widget):
    """
    Handles collision detection between pebbles and the hammer.  Creates Pebbles on collision.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tool = 0  # 0, 1, or 2
        self.sounds = tuple(SoundLoader.load(sound) for sound in SOUND)
        self.setup_canvas()
        self.resize_event = Clock.schedule_once(lambda dt: None, 0)
        self.bind(size=self._delayed_resize, pos=self._delayed_resize)

    def get_pebble_size(self):
        pass

    def setup_canvas(self):
        self.pebbles = {}

        image = Image.open(choice(BOULDER_IMAGE_PATHS))
        image.thumbnail(IMAGE_DIM, Image.NEAREST)
        w, h = image.size
        image = np.frombuffer(image.tobytes(), dtype=np.uint8)
        self.image = image.reshape((h, w, 4))[::-1, :, :].copy()

        self.texture = Texture.create(size=(w, h))
        self.texture.mag_filter = 'nearest'
        self.texture.blit_buffer(self.image.tobytes(), colorfmt='rgba', bufferfmt='ubyte')

        with self.canvas:
            self.background_color = Color(1, 1, 1, 1)
            self.background = Rectangle(source=BACKGROUND)
            self.background.texture.mag_filter = 'nearest'

            self.rect = Rectangle(texture=self.texture)

    def _delayed_resize(self, *args):
        self.resize_event.cancel()
        self.resize_event = Clock.schedule_once(lambda dt: self.resize(*args), .3)

    def resize(self, *args):
        self.background.pos = self.pos
        self.background.size = self.size
        self.rect.size = IMAGE_SCALE * self.width, IMAGE_SCALE * self.height
        self.rect.pos = self.width * (1 - IMAGE_SCALE) / 2, self.height / 10

    def tool(self, i):
        self._tool = i

    def poke_power(self, tx, ty, touch_velocity, pebble_x, pebble_y):
        """
        Returns the force vector of a poke.
        """
        dx, dy = pebble_x - tx, pebble_y - ty
        distance = dx**2 + dy**2

        if distance > CHISEL_RADIUS:
            return 0, 0
        if not distance:
            distance = 1e-4

        power = max(CHISEL_POWER * touch_velocity, MIN_POWER) / distance
        return power * dx, power * dy

    def poke(self, touch):
        tx, ty = touch.spos
        x, y = 1.333 * (tx - .125), 1.333 * (ty - .1) # 1/IMAGE_SCALE * pos - offset --will make
        if not (0 <= x <= 1 and 0 <= y <= 1):         # constants later.
            return
        h, w, _ = self.image.shape
        x, y = int(x * w), int(y * h)

        tdx, tdy = touch.dsx, touch.dsy
        touch_velocity = tdx**2 + tdy**2

        image = self.image
        view = image[y - R:y + R + 1, x - R:x + R + 1, :-1]
        image[y - R:y + R + 1, x - R:x + R + 1, :-1] = view * .8
        mask = view[:, :, :-1].sum(axis=2) < 100 # If color is sufficiently dark...
        image[y - R:y + R + 1, x - R:x + R + 1, -1][mask] = 0 # ...then set alpha to 0.

        self.texture.blit_buffer(image.tobytes(), colorfmt='rgba', bufferfmt='ubyte')
        self.canvas.ask_update()

    def on_touch_down(self, touch):
        self.poke(touch)
        choice(self.sounds).play()
        return True

    def on_touch_move(self, touch):
        self.poke(touch)
        return True

if __name__ == '__main__':
    class ChiselApp(App):
        def build(self):
            return Chisel()
    ChiselApp().run()
