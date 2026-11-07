#!/usr/bin/env python3
"""Draw the pixel-style contribution card shown in the profile README.

Reads the contribution calendar from the GitHub GraphQL API and writes an SVG.
Only uses the standard library, so it runs on a plain GitHub Actions runner.

    GITHUB_TOKEN=... python3 contributions.py <login> <out.svg>
    python3 contributions.py <login> <out.svg> --mock days.json   # offline preview
"""
import datetime
import hashlib
import json
import os
import sys
import urllib.request

# Minecraft-style pixel font ("Minecraft" by Pwnage_Block, CC BY-SA 3.0), one entry per glyph:
# (advance, 8 rows from the top of the capitals; the last row is the descender).
FONT = {
    'A': (6, '011100|100010|111110|100010|100010|100010|100010|000000'),
    'B': (6, '111100|100010|111100|100010|100010|100010|111100|000000'),
    'C': (6, '011100|100010|100000|100000|100000|100010|011100|000000'),
    'D': (6, '111100|100010|100010|100010|100010|100010|111100|000000'),
    'E': (6, '111110|100000|111000|100000|100000|100000|111110|000000'),
    'F': (6, '111110|100000|111000|100000|100000|100000|100000|000000'),
    'G': (6, '011110|100000|100110|100010|100010|100010|011100|000000'),
    'H': (6, '100010|100010|111110|100010|100010|100010|100010|000000'),
    'I': (4, '1110|0100|0100|0100|0100|0100|1110|0000'),
    'J': (6, '000010|000010|000010|000010|000010|100010|011100|000000'),
    'K': (6, '100010|100100|111000|100100|100010|100010|100010|000000'),
    'L': (6, '100000|100000|100000|100000|100000|100000|111110|000000'),
    'M': (6, '100010|110110|101010|100010|100010|100010|100010|000000'),
    'N': (6, '100010|110010|101010|100110|100010|100010|100010|000000'),
    'O': (6, '011100|100010|100010|100010|100010|100010|011100|000000'),
    'P': (6, '111100|100010|111100|100000|100000|100000|100000|000000'),
    'Q': (6, '011100|100010|100010|100010|100010|100100|011010|000000'),
    'R': (6, '111100|100010|111100|100010|100010|100010|100010|000000'),
    'S': (6, '011110|100000|011100|000010|000010|100010|011100|000000'),
    'T': (6, '111110|001000|001000|001000|001000|001000|001000|000000'),
    'U': (6, '100010|100010|100010|100010|100010|100010|011100|000000'),
    'V': (6, '100010|100010|100010|100010|010100|010100|001000|000000'),
    'W': (6, '100010|100010|100010|100010|101010|110110|100010|000000'),
    'X': (6, '100010|010100|001000|010100|100010|100010|100010|000000'),
    'Y': (6, '100010|010100|001000|001000|001000|001000|001000|000000'),
    'Z': (6, '111110|000010|000100|001000|010000|100000|111110|000000'),
    'a': (6, '000000|000000|011100|000010|011110|100010|011110|000000'),
    'b': (6, '100000|100000|101100|110010|100010|100010|111100|000000'),
    'c': (6, '000000|000000|011100|100010|100000|100010|011100|000000'),
    'd': (6, '000010|000010|011010|100110|100010|100010|011110|000000'),
    'e': (6, '000000|000000|011100|100010|111110|100000|011110|000000'),
    'f': (5, '00110|01000|11110|01000|01000|01000|01000|00000'),
    'g': (6, '000000|000000|011110|100010|100010|011110|000010|111100'),
    'h': (6, '100000|100000|101100|110010|100010|100010|100010|000000'),
    'i': (2, '10|00|10|10|10|10|10|00'),
    'j': (6, '000010|000000|000010|000010|000010|100010|100010|011100'),
    'k': (5, '10000|10000|10010|10100|11000|10100|10010|00000'),
    'l': (3, '100|100|100|100|100|100|010|000'),
    'm': (6, '000000|000000|110100|101010|101010|100010|100010|000000'),
    'n': (6, '000000|000000|111100|100010|100010|100010|100010|000000'),
    'o': (6, '000000|000000|011100|100010|100010|100010|011100|000000'),
    'p': (6, '000000|000000|101100|110010|100010|111100|100000|100000'),
    'q': (6, '000000|000000|011010|100110|100010|011110|000010|000010'),
    'r': (6, '000000|000000|101100|110010|100000|100000|100000|000000'),
    's': (6, '000000|000000|011110|100000|011100|000010|111100|000000'),
    't': (4, '0100|1110|0100|0100|0100|0100|0010|0000'),
    'u': (6, '000000|000000|100010|100010|100010|100010|011110|000000'),
    'v': (6, '000000|000000|100010|100010|100010|010100|001000|000000'),
    'w': (6, '000000|000000|100010|100010|101010|101010|011110|000000'),
    'x': (6, '000000|000000|100010|010100|001000|010100|100010|000000'),
    'y': (6, '000000|000000|100010|100010|100010|011110|000010|111100'),
    'z': (6, '000000|000000|111110|000100|001000|010000|111110|000000'),
    '0': (6, '011100|100010|100110|101010|110010|100010|011100|000000'),
    '1': (6, '001000|011000|001000|001000|001000|001000|111110|000000'),
    '2': (6, '011100|100010|000010|001100|010000|100000|111110|000000'),
    '3': (6, '011100|100010|000010|001100|000010|100010|011100|000000'),
    '4': (6, '000110|001010|010010|100010|111110|000010|000010|000000'),
    '5': (6, '111110|100000|111100|000010|000010|100010|011100|000000'),
    '6': (6, '001100|010000|100000|111100|100010|100010|011100|000000'),
    '7': (6, '111110|100010|000010|000100|001000|001000|001000|000000'),
    '8': (6, '011100|100010|100010|011100|100010|100010|011100|000000'),
    '9': (6, '011100|100010|100010|011110|000010|000100|011000|000000'),
    ' ': (2, '00|00|00|00|00|00|00|00'),
    '.': (2, '00|00|00|00|00|10|10|00'),
    ',': (2, '00|00|00|00|00|10|10|10'),
    ':': (2, '00|10|10|00|00|10|10|00'),
    '/': (6, '000010|000100|000100|001000|010000|010000|100000|000000'),
    '-': (6, '000000|000000|000000|000000|111110|000000|000000|000000'),
    '+': (6, '000000|000000|001000|001000|111110|001000|001000|000000'),
    '!': (2, '10|10|10|10|10|00|10|00'),
    '?': (6, '011100|100010|000010|000100|001000|000000|001000|000000'),
    "'": (2, '10|10|00|00|00|00|00|00'),
    '&': (6, '001000|010100|001000|011010|101100|100100|011010|000000'),
    '(': (5, '00110|01000|10000|10000|10000|01000|00110|00000'),
    ')': (5, '11000|00100|00010|00010|00010|00100|11000|00000'),
    '%': (6, '100010|100100|000100|001000|010000|010010|100010|000000'),
    '#': (6, '010100|010100|111110|010100|111110|010100|010100|000000'),
}

GOLD, TXT, MUTED, DIM, XP = '#FFD93D', '#FFFFFF', '#AAB2BB', '#7D8590', '#80FF20'
BG, EDGE, HI, LO = '#161B22', '#05070A', '#232B36', '#0E1217'
LEVELS = {  # base, highlight, shade: from dark grass to experience-orb green
    1: ('#1F4A22', '#2B5E2E', '#153318'),
    2: ('#2E7D32', '#41A046', '#1F5A22'),
    3: ('#4CB050', '#74D078', '#357A38'),
    4: ('#80FF20', '#BFFF8A', '#55B312'),
}
LEVEL_NAMES = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2, 'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } } } } }"""


def fetch(login, token):
    body = json.dumps({'query': QUERY, 'variables': {'login': login}}).encode()
    req = urllib.request.Request('https://api.github.com/graphql', data=body, headers={
        'Authorization': f'bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'profile-readme'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if 'errors' in data:
        raise SystemExit(f'GraphQL error: {data["errors"]}')
    return data['data']['user']['contributionsCollection']['contributionCalendar']


def r(x, y, w, h, c):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>'


def text_width(s, scale):
    return sum(FONT.get(c, FONT[' '])[0] for c in s) * scale


def shadow_of(color):
    h = color.lstrip('#')
    return '#' + ''.join(f'{int(h[i:i + 2], 16) // 4:02X}' for i in (0, 2, 4))


def glyphs(s, x, y, scale, color):
    out = []
    cx = x
    for ch in s:
        adv, rows = FONT.get(ch, FONT[' '])
        for ry, row in enumerate(rows.split('|')):
            i = 0
            while i < len(row):
                if row[i] == '1':
                    j = i
                    while j + 1 < len(row) and row[j + 1] == '1':
                        j += 1
                    out.append(r(cx + i * scale, y + ry * scale, (j - i + 1) * scale, scale, color))
                    i = j + 1
                else:
                    i += 1
        cx += adv * scale
    return ''.join(out)


def text(s, x, y, scale, color, anchor='start', shadow=True):
    """Pixel text with a Minecraft-style drop shadow; y is the top of the capitals."""
    if anchor == 'end':
        x -= text_width(s, scale)
    elif anchor == 'middle':
        x -= text_width(s, scale) // 2
    return (glyphs(s, x + scale, y + scale, scale, shadow_of(color)) if shadow else '') + glyphs(s, x, y, scale, color)


def panel(w, h, p=4):
    return ''.join([r(p, 0, w - 2 * p, p, EDGE), r(p, h - p, w - 2 * p, p, EDGE), r(0, p, p, h - 2 * p, EDGE),
                    r(w - p, p, p, h - 2 * p, EDGE), r(p, p, w - 2 * p, h - 2 * p, BG),
                    r(p, p, w - 2 * p, p, GOLD), r(p, 2 * p, w - 2 * p, p, '#7A6218'), r(p, p, p, h - 2 * p, HI),
                    r(p, h - 2 * p, w - 2 * p, p, LO), r(w - 2 * p, p, p, h - 2 * p, LO)])


def slot(x, y, w, h, p=4, fill='#0F141A'):
    return r(x, y, w, h, fill) + r(x, y, w, p, '#06080B') + r(x, y, p, h, '#06080B') + \
        r(x, y + h - p, w, p, '#2A3340') + r(x + w - p, y, p, h, '#2A3340')


def cell(x, y, level, seed, s=3):
    """A 6x6 sprite: an empty slot or a block whose brightness follows the level."""
    if level == 0:
        return r(x, y, 6 * s, 6 * s, '#0D1117') + r(x, y, 6 * s, s, '#06080B') + r(x, y, s, 6 * s, '#06080B') + \
            r(x, y + 5 * s, 6 * s, s, '#1C232D') + r(x + 5 * s, y, s, 6 * s, '#1C232D')
    base, hi, lo = LEVELS[level]
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    sx, sy = 1 + h % 3, 1 + (h >> 4) % 3
    return (r(x, y, 6 * s, 6 * s, base) + r(x, y, 6 * s, s, hi) + r(x, y, s, 5 * s, hi) +
            r(x, y + 5 * s, 6 * s, s, lo) + r(x + 5 * s, y + s, s, 5 * s, lo) +
            r(x + sx * s, y + sy * s, s, s, hi) + r(x + (sx + 1) * s, y + (sy + 2) * s, s, s, lo))


SPRITES = {  # pixel art drawn for this profile: rows separated by |, one letter per colour
    'pickaxe': ('....a...........|...abaaa........|...acbbba.......|...adcccbaa.....|....aaddcbba....|......aadcbba...|........adcba...|......aa.adcba..|.....aefa.adcba.|....aeffa.adcba.|...aeffa...acba.|..aeffa....adcba|.aeffa......aaa.|aeffa...........|affa............|.aa.............', {'a': '#24292F', 'b': '#F2F5F8', 'c': '#B4BEC9', 'd': '#7F8A96', 'e': '#7A5228', 'f': '#A0703A'}),
    'flame': ('......a.....|......a.....|.....aa.....|.....aba....|.....bba....|....abbb....|....abcb....|...abccbad..|.aaabceca...|.aabceecbaa.|.aabceecbaa.|aabceeeecbaa|abbceeeecbaa|abceeeeeecba', {'a': '#E2470E', 'b': '#FF8A1E', 'c': '#FFD24A', 'd': '#FFB347', 'e': '#FFF6C8'}),
    'chest': ('.aaaaaaaaaaaa.|abbbbbbbbbbbba|acccccccccccca|aaaaaaddaaaaaa|aaaaaadeaaaaaa|acccccddccccca|acccccccccccca|acccccccccccca|affffffffffffa|aaaaaaaaaaaaaa|.aaaaaaaaaaaa.', {'a': '#3A2410', 'b': '#C08A4A', 'c': '#A0703A', 'd': '#5E4404', 'e': '#D9DEE4', 'f': '#7A5228'}),
    'gem': ('..aaaa..|.abbcca.|abbcccca|acccccda|.acccda.|..acda..|...aa...', {'a': '#0B3A44', 'b': '#E8FFFF', 'c': '#55FFFF', 'd': '#1FA8C0'}),
    'orb': ('..aaaa..|.abbcca.|abbcccca|acccccda|acccccda|abccccda|.acddda.|..aaaa..', {'a': '#1D4D08', 'b': '#E9FFB8', 'c': '#9CFF3C', 'd': '#4FB80F'}),
    'star': ('....a....|...aba...|...aba...|aaabbbaaa|abbbcbbba|.abbbbba.|..abbba..|.abba.aba|.aa.....a', {'a': '#5A3D00', 'b': '#FFE24D', 'c': '#FFFBD0'}),
    'heart': ('.aa...aa.|abba.abba|abcbabbba|abbbbbbba|.abbbbba.|..abbba..|...aba...|....a....', {'a': '#2A0606', 'b': '#E8312E', 'c': '#FFB0A8'}),
    'heart_empty': ('.aa...aa.|abba.abba|abbbabbba|abbbbbbba|.abbbbba.|..abbba..|...aba...|....a....', {'a': '#1A0B0B', 'b': '#3A2224'}),
}

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def month_day(date):
    return f'{MONTHS[int(date[5:7]) - 1]} {int(date[8:10])}'


def sprite(name, x, y, scale, locked=False):
    rows, pal = SPRITES[name]
    out = []
    for ry, row in enumerate(rows.split('|')):
        i = 0
        while i < len(row):
            ch = row[i]
            if ch == '.':
                i += 1
                continue
            j = i
            while j + 1 < len(row) and row[j + 1] == ch:
                j += 1
            col = pal[ch]
            if locked:      # dark silhouette for advancements that are not earned yet
                v = sum(int(col[k:k + 2], 16) for k in (1, 3, 5)) / 3
                col = '#%02X%02X%02X' % ((26 + int(v / 10),) * 3)
            out.append(r(x + i * scale, y + ry * scale, (j - i + 1) * scale, scale, col))
            i = j + 1
    return ''.join(out)


def sprite_size(name):
    rows = SPRITES[name][0].split('|')
    return max(len(x) for x in rows), len(rows)


def outlined(s, x, y, scale, color, anchor='start'):
    """Number drawn with a black outline, like the level above the experience bar."""
    if anchor == 'middle':
        x -= text_width(s, scale) // 2
    out = [glyphs(s, x + dx * scale, y + dy * scale, scale, '#000000') for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
    return ''.join(out) + glyphs(s, x, y, scale, color)


def xp_bar(x, y, units, u, frac):
    """Experience bar drawn on a 5-pixel-high grid (u = size of one pixel)."""
    out = [r(x + u, y, (units - 2) * u, u, '#000000'), r(x + u, y + 4 * u, (units - 2) * u, u, '#000000'),
           r(x, y + u, u, 3 * u, '#000000'), r(x + (units - 1) * u, y + u, u, 3 * u, '#000000')]
    inner = units - 2
    filled = int(round(inner * frac))
    for i in range(inner):
        px = x + (i + 1) * u
        on = i < filled
        notch = (i + 1) % 10 == 0
        if on:
            cols = ('#7DD43C', '#5FB322', '#4A9416') if notch else ('#C6FF8A', '#80FF20', '#4FB80F')
        else:
            cols = ('#0E1A08', '#0B1506', '#081004') if notch else ('#22361A', '#1A2A12', '#132010')
        for k, c in enumerate(cols):
            out.append(r(px, y + (k + 1) * u, u, u, c))
    return ''.join(out)


ADVANCEMENTS = [
    # (title, description, icon, key, goal)
    ('First Steps', 'Contribute once', 'pickaxe', 'total', 1),
    ('Hot Streak', '3 days in a row', 'flame', 'longest', 3),
    ('Committed', '50 in a year', 'chest', 'total', 50),
    ('Leveling Up', 'Reach level 5', 'orb', 'level', 5),
    ('Week Warrior', '7 days in a row', 'gem', 'longest', 7),
    ('Centurion', '100 in a year', 'star', 'total', 100),
]


def xp_for_level(level):
    """Total experience needed to reach a level, using Minecraft's formula."""
    if level <= 16:
        return level * level + 6 * level
    if level <= 31:
        return 2.5 * level * level - 40.5 * level + 360
    return 4.5 * level * level - 162.5 * level + 2220


def level_of(xp):
    level = 0
    while xp_for_level(level + 1) <= xp:
        level += 1
    span = xp_for_level(level + 1) - xp_for_level(level)
    return level, (xp - xp_for_level(level)) / span, int(round(xp_for_level(level + 1) - xp))


def streaks(days):
    counts = [d['contributionCount'] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:      # today may simply not have started yet
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return current, longest


def render(cal, today):
    weeks = cal['weeks']
    days = [d for w in weeks for d in w['contributionDays']]
    total = cal['totalContributions']
    current, longest = streaks(days)
    best = max(days, key=lambda d: d['contributionCount']) if days else None

    level, frac, to_next = level_of(total)
    W, H = 1200, 756
    b = [panel(W, H)]
    # headline
    b.append(text('CONTRIBUTIONS', 36, 34, 2, GOLD))
    num = f'{total:,}'.replace(',', ' ')
    b.append(text(num, 36, 58, 8, TXT))
    b.append(text('in the last 12 months', 36, 128, 2, MUTED))
    # stat slots
    stats = [('Streak', str(current), 'day' if current == 1 else 'days'),
             ('Longest', str(longest), 'day' if longest == 1 else 'days'),
             ('Best day', str(best['contributionCount'] if best else 0), 'on ' + (month_day(best['date']) if best else '-'))]
    sw, gap = 220, 14
    x0 = W - 36 - 3 * sw - 2 * gap
    for i, (lbl, val, unit) in enumerate(stats):
        x = x0 + i * (sw + gap)
        b.append(slot(x, 32, sw, 104))
        b.append(text(lbl, x + 18, 48, 2, MUTED))
        b.append(text(val, x + 18, 72, 5, XP))
        ux = x + 26 + text_width(val, 5)
        room = x + sw - 14 - ux
        for us, uy in ((3, 84), (2, 90)):      # shrink the unit if it does not fit
            if text_width(unit, us) <= room or us == 2:
                break
        if text_width(unit, us) > room:
            unit = unit.replace('on ', '')
        b.append(text(unit, ux, uy, us, MUTED))

    cs, step = 18, 21
    gw = len(weeks) * step - 3
    gx = (W - gw) // 2
    # --- HUD: hearts for the last 10 days, level and experience bar
    u = 6
    units = gw // u
    bx = (W - units * u) // 2
    by = 224
    recent = days[-10:]
    hx = bx
    for d in recent:
        b.append(sprite('heart' if d['contributionCount'] else 'heart_empty', hx, by - 46, 4))
        hx += 40
    b.append(outlined(str(level), W // 2, by - 52, 5, XP, anchor='middle'))
    b.append(xp_bar(bx, by, units, u, frac))
    b.append(text('Hearts: last 10 days', bx, by + 42, 2, DIM))
    b.append(text(f'Level {level}, {to_next} more to level {level + 1}', bx + units * u, by + 42, 2, DIM, anchor='end'))

    # --- calendar
    gy = 336
    last_label = -9
    prev_month = None
    for wi, w in enumerate(weeks):
        first = w['contributionDays'][0]['date']
        m = int(first[5:7])
        if m != prev_month and wi - last_label >= 3 and wi < len(weeks) - 1:
            if prev_month is not None or int(first[8:10]) <= 7:
                b.append(text(MONTHS[m - 1], gx + wi * step, gy - 28, 2, DIM))
                last_label = wi
        prev_month = m
    for wi, w in enumerate(weeks):
        b.append(''.join(cell(gx + wi * step, gy + d['weekday'] * step, LEVEL_NAMES.get(d['contributionLevel'], 0), d['date'])
                         for d in w['contributionDays']))
    if days:        # today: a blinking selection frame
        last = days[-1]
        tx, ty = gx + (len(weeks) - 1) * step - 3, gy + last['weekday'] * step - 3
        b.append(f'<g fill="none" stroke="#FFFFFF" stroke-width="2"><rect x="{tx + 1}" y="{ty + 1}" width="{cs + 4}" height="{cs + 4}"/>'
                 f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></g>')
    fy = gy + 7 * step + 22
    b.append(text(f'Updated {today}', gx, fy, 2, DIM))
    lx = gx + gw
    b.append(text('More', lx, fy, 2, DIM, anchor='end'))
    lx -= text_width('More', 2) + 10 + 5 * step
    for lv in range(5):
        b.append(cell(lx + lv * step, fy - 2, lv, f'legend{lv}'))
    b.append(text('Less', lx - 10, fy, 2, DIM, anchor='end'))

    # --- advancements, earned from the same data
    ay = fy + 44
    values = {'total': total, 'longest': longest, 'level': level}
    earned_n = sum(values[k] >= g for _, _, _, k, g in ADVANCEMENTS)
    b.append(text('ADVANCEMENTS', gx, ay, 2, GOLD))
    b.append(text(f'{earned_n}/{len(ADVANCEMENTS)} earned', gx + gw, ay, 2, DIM, anchor='end'))
    n = len(ADVANCEMENTS)
    tgap = 12
    tw_ = (gw - (n - 1) * tgap) // n
    ty0 = ay + 28
    for i, (title_, desc, icon, key, goal) in enumerate(ADVANCEMENTS):
        x = gx + i * (tw_ + tgap)
        got = values[key] >= goal
        b.append(slot(x, ty0, tw_, 150, fill='#0F141A'))
        fs = 72
        fx = x + (tw_ - fs) // 2
        fyy = ty0 + 16
        frame_col = XP if got else '#2A3340'
        b.append(r(fx, fyy, fs, fs, '#0A0D11'))
        b.append(r(fx, fyy, fs, 4, frame_col) + r(fx, fyy + fs - 4, fs, 4, frame_col) +
                 r(fx, fyy, 4, fs, frame_col) + r(fx + fs - 4, fyy, 4, fs, frame_col))
        iw, ih = sprite_size(icon)
        sc = max(1, min(44 // iw, 44 // ih))
        b.append(sprite(icon, fx + (fs - iw * sc) // 2, fyy + (fs - ih * sc) // 2, sc, locked=not got))
        b.append(text(title_, x + tw_ // 2, ty0 + 100, 2, TXT if got else MUTED, anchor='middle'))
        if got:
            b.append(text(desc, x + tw_ // 2, ty0 + 122, 2, DIM, anchor='middle', shadow=False))
        else:
            prog = f'{min(values[key], goal)}/{goal}' + (' days' if key == 'longest' else '')
            b.append(text(prog, x + tw_ // 2, ty0 + 122, 2, DIM, anchor='middle', shadow=False))
    title = (f'{total} contributions in the last year, current streak {current}, longest streak {longest}, '
             f'level {level}, {earned_n} of {len(ADVANCEMENTS)} advancements')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">'
            f'<title>{title}</title><g shape-rendering="crispEdges">{"".join(b)}</g></svg>\n')


def main():
    login, out = sys.argv[1], sys.argv[2]
    if '--mock' in sys.argv:
        cal = json.load(open(sys.argv[sys.argv.index('--mock') + 1]))
    else:
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            raise SystemExit('GITHUB_TOKEN is not set')
        cal = fetch(login, token)
    today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w') as f:
        f.write(render(cal, today))


if __name__ == '__main__':
    main()
