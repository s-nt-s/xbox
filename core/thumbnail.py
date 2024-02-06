from PIL import Image
import requests
from io import BytesIO


def mk_thumbnail(url: str, out: str, content=None):
    ext = out.rsplit(".")[-1].lower()
    if content is None:
        response = requests.get(url)
        content = response.content
    img = Image.open(BytesIO(content))
    img.thumbnail((150, 99999))
    if ext in ("jpg", "jpeg"):
        img = img.convert('RGB')
        img.save(out, optimize=True, quality=50)
        return
    if ext in ("png", ):
        img = img.convert(mode='P', palette=1, colors=256)
        img.save(out, optimize=True, quality=50, format="PNG")
        return
    raise Exception("Bad Format "+str(out))
