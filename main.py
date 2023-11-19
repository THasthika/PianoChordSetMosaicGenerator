import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageFont, ImageDraw
from typing import Self
import re
import math
from os import path
import os
import json

BASE_URL = "https://www.pianochord.org"

# URL = "https://www.pianochord.org/dm7-flat.html"

TEXT_HEIGHT = 30

PAD_X = 5
PAD_Y = 5

FONT = ImageFont.truetype("./roboto.ttf", TEXT_HEIGHT)

MAJ_REGEX = re.compile("([A-Ga-g])([b#])?")
MIN_REGEX = re.compile("([A-Ga-g])([b#])?m(in)?")

MAJ7_REGEX = re.compile("([A-Ga-g])([b#])?(M|[Mm]aj)7")
MIN7_REGEX = re.compile("([A-Ga-g])([b#])?(m|[Mm]in)7")

SEVEN_REGEX = re.compile("([A-Ga-g])([b#])?7")

DIM_REGEX = re.compile("([A-Ga-g])([b#])?dim")


# # MIN_7_REGEX =

def generate_pianochord_sharp_flat_part(m: str | None):
    if m is None:
        return ""
    if m == "#":
        return "-sharp"
    elif m == "b":
        return "-flat"


def chordname_to_pianochord_name(chord_name: str):

    # Dbm7 -> dm7-flat
    # DbM7 -> dmaj7-flat
    # Dbmaj7 -> dmaj7-flat
    # D#m7 -> dm7-sharp

    # check diminished chords
    match = DIM_REGEX.match(chord_name)
    if match:
        name = match.group(1).lower()
        name += generate_pianochord_sharp_flat_part(match.group(2))
        name += "-dim"
        return name

    # check major 7
    match = MAJ7_REGEX.match(chord_name)
    if match:
        name = match.group(1).lower() + "maj7"
        name += generate_pianochord_sharp_flat_part(match.group(2))
        return name

    # check minor 7
    match = MIN7_REGEX.match(chord_name)
    if match:
        name = match.group(1).lower() + "m7"
        name += generate_pianochord_sharp_flat_part(match.group(2))
        return name

    # check 7
    match = SEVEN_REGEX.match(chord_name)
    if match:
        name = match.group(1).lower() + "7"
        name += generate_pianochord_sharp_flat_part(match.group(2))
        return name

    # minor
    match = MIN_REGEX.match(chord_name)
    if match:
        name = match.group(1).lower() + "m"
        name += generate_pianochord_sharp_flat_part(match.group(2))
        return name

    # major
    match = MAJ_REGEX.match(chord_name)
    if match:
        name = match.group(1).lower()
        name += generate_pianochord_sharp_flat_part(match.group(2))
        name += "-major"
        return name

    raise Exception("Unknown Chord Name: {}".format(chord_name))


class ChordDiagram:

    def __init__(self, title, pc_name, source_url) -> None:
        self.title = title
        self.pc_name = pc_name
        self.source_url = source_url
        self.img = None

    def is_downloaded(self):
        return self.img is not None

    def download_image(self):
        img = Image.open(requests.get(self.source_url, stream=True).raw)
        img = img.convert('RGB')
        img = self.__make_chord_diagram(img)
        self.img = img

        self.__cache()

    def __make_chord_diagram(self, chord: Image.Image):

        new_height = chord.size[1] + TEXT_HEIGHT + PAD_Y

        img = Image.new("RGB", size=(chord.size[0], new_height))
        img.paste(chord, (0, 0))

        d = ImageDraw.Draw(img)

        d.text((chord.size[0] // 2, chord.size[1]),
               self.title, font=FONT, align="center")

        return img

    def show(self):
        self.img.show()

    def size(self):
        return self.img.size

    def __from_cache(pc_name: str) -> Self | None:
        if not path.exists(".cache/"):
            os.mkdir(".cache")

        if not path.exists(".cache/{}.json".format(pc_name)):
            return None

        with open(".cache/{}.json".format(pc_name)) as f:
            d = json.load(f)

        img = Image.open(".cache/{}.png".format(pc_name))

        cd = ChordDiagram(
            title=d['title'], pc_name=d['path_name'], source_url=d['source_url'])
        cd.img = img

        return cd

    def from_pianochord(chord_name: str) -> Self:

        path_name = chordname_to_pianochord_name(chord_name)

        cd = ChordDiagram.__from_cache(path_name)
        if cd is not None:
            return cd

        url = "{}/{}.html".format(BASE_URL, path_name)
        response = requests.get(url)
        bs = BeautifulSoup(response.content, 'html.parser')
        c = bs.find(id="content")
        title = c.find('h2')
        img = c.find('img', 'image')
        img_src = img['src']

        cd = ChordDiagram(title.text, path_name,
                          "{}/{}".format(BASE_URL, img_src))
        cd.download_image()

        return cd

    def __cache(self):
        if not path.exists(".cache/"):
            os.mkdir(".cache")
        assert self.img is not None
        dict_cache = {"title": self.title,
                      "source_url": self.source_url, "path_name": self.pc_name}
        with open(".cache/{}.json".format(self.pc_name), "w+") as f:
            json.dump(dict_cache, f)
        self.img.save(".cache/{}.png".format(self.pc_name))

    def resize(self, new_size: tuple[int, int]) -> Image:
        new_img = self.img.copy()
        new_img.thumbnail(new_size, Image.LANCZOS)
        return new_img


def make_chord_mosaic(chords: list[str], out_file="out.png", chords_per_row=3, chord_width=400, chord_height=200):

    assert len(chords) > 0
    assert chords_per_row > 0

    rows = math.ceil(len(chords) / chords_per_row)

    actual_width = chord_width - (2 * PAD_X)

    chord_images = [ChordDiagram.from_pianochord(name).resize(
        (actual_width, chord_height)) for name in chords]

    mosaic_image = Image.new(
        "RGB", (chord_width * chords_per_row, chord_height * rows))

    r_idx = 0
    c_idx = 0
    for img in chord_images:
        if c_idx >= chords_per_row:
            r_idx += 1
            c_idx = 0

        x_coord = chord_width * c_idx
        y_coord = chord_height * r_idx

        if img.size[0] < chord_width:
            x_coord += (chord_width - img.size[0]) // 2
        if img.size[1] < chord_height:
            y_coord += (chord_height - img.size[1]) // 2

        mosaic_image.paste(img, (x_coord, y_coord))

        c_idx += 1

    mosaic_image.save(out_file)


# make_chord_mosaic(["C", "D", "Ddim"])


# DbM7 Db7 Ebm7 Ebdim Bdim Ebm7 Adim
# DbM7 Db7 GbM7 B7 Fm7 Bb7 Ebm7 Ab7
# DbM7 Db7 GbM7 B7 Fm7 Bb7 Ebm7 Ab7
# DbM7 Abm7 Db7 Gm7 B7 Fm7 Bb7 Eb7 Ab7
# Bbm F7 AbM7 Dbm F7 AbM7 Eb7 F7 AbM7 Gdim F7 AbM7
# F#M7 Fm7 F#M7 F# Fm7 Eb7 F7 AbM7 Eb7 F7 AbM7 AbM7 F7 AbM7


# chords_list = [
#     "DbM7", "Db7", "Ebm7", "Ebdim", "Bdim", "Adim", "GbM7", "B7", "Fm7",
#     "Bb7", "Ab7", "Abm7", "Gm7", "Eb7", "Bbm", "F7", "AbM7", "Dbm", "Gdim",
#     "AbM7", "F#M7", "F#"
# ]


# make_chord_mosaic(sorted(chords_list), chords_per_row=3)


cc = [
    ["DbM7", "Db7", "Ebm7", "Ebdim", "Bdim", "Ebm7", "Adim"],
    ["DbM7", "Db7", "GbM7", "B7", "Fm7", "Bb7", "Ebm7", "Ab7"],
    ["DbM7", "Db7", "GbM7", "B7", "Fm7", "Bb7", "Ebm7", "Ab7"],
    ["DbM7", "Abm7", "Db7", "Gm7", "B7", "Fm7", "Bb7", "Eb7", "Ab7"],
    ["Bbm", "F7", "AbM7", "Dbm", "F7", "AbM7",
        "Eb7", "F7", "AbM7", "Gdim", "F7", "AbM7"],
    ["F#M7", "Fm7", "F#M7", "F#", "Fm7", "Eb7", "F7",
        "AbM7", "Eb7", "F7", "AbM7", "AbM7", "F7", "AbM7"]
]

for (idx, cl) in enumerate(cc):
    make_chord_mosaic(cl, out_file="{}.png".format(idx), chords_per_row=5)
