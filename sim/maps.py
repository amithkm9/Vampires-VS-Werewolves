"""Map loading (server XML format) and random map generation."""

from __future__ import annotations

import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class MapSpec:
    name: str
    rows: int
    cols: int
    humans: Dict[Tuple[int, int], int] = field(default_factory=dict)
    vampires: Tuple[int, int, int] = (0, 0, 0)  # x, y, count
    werewolves: Tuple[int, int, int] = (0, 0, 0)

    def to_xml(self) -> str:
        lines = [
            '<?xml version="1.0" encoding="utf-8" ?>',
            f'<Map Rows="{self.rows}" Columns="{self.cols}">',
        ]
        for (x, y), c in self.humans.items():
            lines.append(f'  <Humans X="{x}" Y="{y}" Count="{c}"/>')
        x, y, c = self.werewolves
        lines.append(f'  <Werewolves X="{x}" Y="{y}" Count="{c}"/>')
        x, y, c = self.vampires
        lines.append(f'  <Vampires X="{x}" Y="{y}" Count="{c}"/>')
        lines.append("</Map>")
        return "\n".join(lines) + "\n"


def load_map(path: str) -> MapSpec:
    root = ET.parse(path).getroot()
    spec = MapSpec(
        name=path.rsplit("/", 1)[-1],
        rows=int(root.attrib["Rows"]),
        cols=int(root.attrib["Columns"]),
    )
    for el in root:
        x, y, c = int(el.attrib["X"]), int(el.attrib["Y"]), int(el.attrib["Count"])
        if el.tag == "Humans":
            spec.humans[(x, y)] = c
        elif el.tag == "Vampires":
            spec.vampires = (x, y, c)
        elif el.tag == "Werewolves":
            spec.werewolves = (x, y, c)
    return spec


def random_map(rng: random.Random, name: str = "random") -> MapSpec:
    """Point-symmetric random map, so neither species is favoured by the layout."""
    rows = rng.randint(5, 16)
    cols = rng.randint(5, 20)
    start = rng.randint(3, 12)
    used = set()

    def mirror(x, y):
        return cols - 1 - x, rows - 1 - y

    while True:
        vx, vy = rng.randrange(cols), rng.randrange(rows)
        wx, wy = mirror(vx, vy)
        if (vx, vy) != (wx, wy):
            break
    used |= {(vx, vy), (wx, wy)}
    humans: Dict[Tuple[int, int], int] = {}
    homes = rng.randint(2, max(2, rows * cols // 12))
    for _ in range(homes):
        x, y = rng.randrange(cols), rng.randrange(rows)
        mx, my = mirror(x, y)
        if (x, y) in used or (mx, my) in used:
            continue
        c = rng.choice([1, 2, 2, 3, 3, 4, 4, 5, 6, 8, 10, 12, 15, 20])
        humans[(x, y)] = c
        humans[(mx, my)] = c
        used |= {(x, y), (mx, my)}
    return MapSpec(name, rows, cols, humans, (vx, vy, start), (wx, wy, start))
