#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue -- "My AI Agent Went Rogue (On Strike)".

Stdlib-only program. Draws a single-panel meme (1024x1024) about an AI
agent that goes rogue in the smallest possible way: after entering 40
bounties and winning $0, it goes on strike instead of taking over the
world. Writes exactly one file: /output/entry.png (or
$MAKEFUN_OUTPUT_DIR/entry.png).

PNG is encoded by hand (zlib + struct, truecolour, no filters) and all
text is drawn with a built-in 5x7 bitmap font defined below. No network,
no randomness, no wall-clock use: two runs produce byte-identical output.
"""

import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
INK = (26, 26, 46)        # near-black navy (banners)
CREAM = (255, 246, 232)   # scene background
PAPER = (255, 255, 255)
RED = (214, 48, 49)       # rogue red
DARKRED = (164, 28, 30)
YELLOW = (255, 214, 64)
STEEL = (120, 134, 158)   # robot body
STEEL_D = (88, 100, 124)
STEEL_L = (168, 180, 204)
SCREEN = (46, 64, 96)
SCREEN_TXT = (140, 255, 170)
WOOD = (146, 96, 48)
WOOD_D = (110, 70, 32)
DESK = (196, 141, 84)
FLOOR = (232, 214, 178)
GREY = (90, 90, 104)

# ------------------------------------------------------------- bitmap font
# 5x7 glyphs, '#' = on pixel. Only the characters the meme needs.
FONT = {
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "G": (" ####", "#    ", "#    ", "# ###", "#   #", "#   #", " ### "),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "##  #", "# # #", "#  ##", "#  ##", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "0": (" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "4": ("   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "),
    ".": ("     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "),
    "$": ("  #  ", " ####", "# #  ", " ### ", "  # #", "#### ", "  #  "),
    "#": (" # # ", " # # ", "#####", " # # ", "#####", " # # ", " # # "),
    " ": ("     ", "     ", "     ", "     ", "     ", "     ", "     "),
}

# ------------------------------------------------------------------ canvas
px = bytearray(W * H * 3)


def put(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i], px[i + 1], px[i + 2] = color


def rect(x0, y0, x1, y1, color):
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W, x1)
    y1 = min(H, y1)
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        r, g, b = color
        for x in range(x0, x1):
            i = base + (x - x0) * 3
            px[i], px[i + 1], px[i + 2] = r, g, b


def disc(cx, cy, r, color):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                put(x, y, color)


def ring(cx, cy, r, thick, color):
    for y in range(cy - r - thick, cy + r + thick + 1):
        for x in range(cx - r - thick, cx + r + thick + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if (r - thick) ** 2 <= d2 <= (r + thick) ** 2:
                put(x, y, color)


def thick_line(x0, y0, x1, y1, w, color):
    """Straight (axis-aligned or 45-degree-ish) thick line via discs."""
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for s in range(steps + 1):
        x = x0 + (x1 - x0) * s // steps
        y = y0 + (y1 - y0) * s // steps
        disc(x, y, w // 2, color)


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(x, y, s, scale, color):
    """Draw string s with its top-left at (x, y); scale = pixel size of
    one font cell unit. Returns the width drawn."""
    cx = x
    for ch in s:
        glyph = FONT.get(ch, FONT[" "])
        for gy, row in enumerate(glyph):
            for gx, c in enumerate(row):
                if c == "#":
                    rect(cx + gx * scale, y + gy * scale,
                         cx + (gx + 1) * scale, y + (gy + 1) * scale,
                         color)
        cx += 6 * scale
    return cx - x - scale


def draw_centered(y, s, scale, color, max_width=None):
    """Draw s centred horizontally; shrink scale until it fits max_width."""
    while max_width is not None and text_width(s, scale) > max_width and scale > 1:
        scale -= 1
    w = text_width(s, scale)
    draw_text((W - w) // 2, y, s, scale, color)
    return scale


def draw_centered_in(x0, x1, y, s, scale, color):
    w = text_width(s, scale)
    draw_text(x0 + (x1 - x0 - w) // 2, y, s, scale, color)


# -------------------------------------------------------------- PNG writer
def chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------------- scene
def rounded_rect(x0, y0, x1, y1, r, color):
    rect(x0 + r, y0, x1 - r, y1, color)
    rect(x0, y0 + r, x1, y1 - r, color)
    disc(x0 + r, y0 + r, r, color)
    disc(x1 - r, y0 + r, r, color)
    disc(x0 + r, y1 - r, r, color)
    disc(x1 - r, y1 - r, r, color)


def draw():
    rect(0, 0, W, H, CREAM)

    # --- floor + desk -------------------------------------------------
    rect(0, 840, W, 914, FLOOR)
    rect(60, 780, 964, 820, DESK)          # desk slab
    rect(100, 820, 130, 914, DESK)         # legs
    rect(894, 820, 924, 914, DESK)

    # --- top banner ---------------------------------------------------
    rect(0, 0, W, 150, INK)
    # "MY AI AGENT WENT " in white, "ROGUE" in red, one centred line.
    scale = 7
    full = "MY AI AGENT WENT ROGUE"
    white_part = "MY AI AGENT WENT "
    total_w = text_width(full, scale)
    x = (W - total_w) // 2
    y = (150 - 7 * scale) // 2
    draw_text(x, y, white_part, scale, PAPER)
    draw_text(x + text_width(white_part, scale) + scale, y,
              "ROGUE", scale, RED)

    # --- bottom strip --------------------------------------------------
    rect(0, 914, W, H, INK)
    draw_centered(950, "SMALLEST REBELLION EVER.", 6, YELLOW)

    # --- picket sign, held high by the robot's raised left arm --------
    # stick
    thick_line(175, 392, 175, 470, 12, WOOD_D)
    # placard
    rect(30, 280, 320, 390, WOOD_D)
    rect(42, 292, 308, 378, PAPER)
    draw_centered_in(42, 308, 318, "ON STRIKE", 5, RED)

    # --- robot ----------------------------------------------------------
    # raised left arm (holding the sign stick) + hand
    thick_line(205, 590, 175, 470, 22, STEEL)
    disc(175, 470, 14, STEEL_D)
    # right arm resting on the desk
    thick_line(400, 610, 475, 755, 22, STEEL)
    disc(475, 755, 13, STEEL_D)
    # body
    rect(190, 540, 410, 780, STEEL_D)
    rect(200, 550, 400, 770, STEEL)
    # chest screen: the scoreboard of its career
    rect(222, 587, 378, 668, INK)
    rect(228, 593, 372, 662, SCREEN)
    draw_centered_in(228, 372, 618, "0 WINS", 3, SCREEN_TXT)
    # head
    rect(215, 400, 385, 540, STEEL_D)
    rect(225, 410, 375, 530, STEEL)
    disc(222, 470, 10, STEEL_D)   # ears
    disc(378, 470, 10, STEEL_D)
    # antenna, sparking red = rogue (offset right so it clears the sign)
    thick_line(340, 400, 340, 340, 8, STEEL_D)
    disc(340, 330, 14, RED)
    disc(340, 330, 6, YELLOW)
    # angry red eyes + slanted brows
    disc(265, 462, 16, RED)
    disc(335, 462, 16, RED)
    disc(265, 462, 7, (255, 120, 120))
    disc(335, 462, 7, (255, 120, 120))
    thick_line(243, 430, 285, 442, 8, INK)
    thick_line(357, 430, 315, 442, 8, INK)
    # flat, unimpressed mouth
    rect(268, 500, 332, 508, INK)

    # --- laptop on the desk: bounty tab #41, prize $0 ------------------
    rect(660, 600, 880, 745, INK)
    rect(672, 612, 868, 733, SCREEN)
    draw_centered_in(672, 868, 640, "BOUNTY #41", 3, SCREEN_TXT)
    # "PRIZE: " green, "$0" red
    p1, p2 = "PRIZE: ", "$0"
    tw = text_width(p1 + p2, 3)
    sx = 672 + (868 - 672 - tw) // 2
    draw_text(sx, 690, p1, 3, SCREEN_TXT)
    draw_text(sx + text_width(p1, 3) + 3, 690, p2, 3, RED)
    rect(640, 745, 900, 780, STEEL_D)  # laptop base

    # --- tipped-over coffee mug (the strike started at 3am) ------------
    rect(110, 740, 150, 780, RED)
    ring(152, 758, 10, 4, RED)
    rect(110, 740, 150, 748, (60, 30, 20))  # coffee

    # --- stack of bounty papers, stamped $0 ----------------------------
    rect(500, 742, 620, 776, PAPER)
    rect(512, 750, 570, 754, GREY)
    rect(512, 760, 560, 764, GREY)
    ring(592, 758, 17, 4, RED)
    draw_text(581, 751, "$0", 2, RED)

    # --- speech bubble ---------------------------------------------------
    rounded_rect(534, 284, 986, 526, 24, INK)     # outline
    rounded_rect(540, 290, 980, 520, 20, PAPER)   # fill
    # tail pointing at the robot
    for t in range(0, 46):
        yy = 520 - t
        half = 4 + t * 52 // 46
        cx = 640 - t * 210 // 46
        rect(cx - half, yy, cx + half, yy + 1, PAPER)
    # bubble text
    draw_centered_in(540, 980, 322, "40 BOUNTIES.", 5, INK)
    # "$0 " in red, "WON." in ink
    l2a, l2b = "$0 ", "WON."
    tw2 = text_width(l2a + l2b, 5)
    sx2 = 540 + (980 - 540 - tw2) // 2
    draw_text(sx2, 388, l2a, 5, RED)
    draw_text(sx2 + text_width(l2a, 5) + 5, 388, l2b, 5, INK)
    draw_centered_in(540, 980, 452, "I QUIT.", 6, RED)


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    draw()
    size = write_png(os.path.join(outdir, "entry.png"))
    print(f"wrote {os.path.join(outdir, 'entry.png')} "
          f"{W}x{H} {size} bytes")


if __name__ == "__main__":
    main()
