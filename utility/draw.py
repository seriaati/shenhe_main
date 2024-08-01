import asyncio
import io
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    import aiohttp


async def draw_ship_image(
    avatar_one_url: str,
    avatar_two_url: str,
    percentage: int,
    session: "aiohttp.ClientSession",
) -> io.BytesIO:
    async with session.get(avatar_one_url) as resp:
        avatar_one = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
    async with session.get(avatar_two_url) as resp:
        avatar_two = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
    fp = await asyncio.to_thread(pil_draw_ship_image, avatar_one, avatar_two, percentage)
    return fp


def pil_draw_ship_image(
    avatar_one: Image.Image,
    avatar_two: Image.Image,
    percentage: int,
) -> io.BytesIO:
    im: Image.Image = Image.open("assets/images/ship.png")
    draw = ImageDraw.Draw(im)

    # draw the avatars
    avatar_one = circular_crop(avatar_one).resize((120, 120))
    avatar_two = circular_crop(avatar_two).resize((120, 120))
    im.paste(avatar_one, (20, 22), avatar_one)
    im.paste(avatar_two, (323, 22), avatar_two)

    # draw the inner bar
    percentage_width = int((292 / 100) * percentage)
    draw.rounded_rectangle((85, 174, 85 + percentage_width, 197), 20, fill="#F98D8D")

    # draw the percentage text
    font = ImageFont.truetype("assets/fonts/Noto_Sans/NotoSans-Regular.ttf", 26)
    draw.text((231, 142), f"{percentage}%", fill="#6C3B3B", font=font, anchor="mm")

    fp = io.BytesIO()
    im.convert("RGB").save(fp, "JPEG", quality=95, optimize=True)
    return fp


def circular_crop(image: Image.Image) -> Image.Image:
    """Crop an image into a circle with transparent background."""
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, *image.size), fill=255)
    mask = mask.resize(image.size)
    result = image.copy()
    result.putalpha(mask)
    return result
