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

# 5px pixel font (glyphs taken from Silkscreen, SIL OFL 1.1). Each glyph: (advance, 7 rows).
FONT = {
    'A': (6, '000000|001100|010010|011110|010010|010010|000000'),
    'B': (6, '000000|011100|010010|011110|010010|011100|000000'),
    'C': (6, '000000|001100|010010|010000|010010|001100|000000'),
    'D': (6, '000000|011100|010010|010010|010010|011100|000000'),
    'E': (5, '00000|01110|01000|01110|01000|01110|00000'),
    'F': (5, '00000|01110|01000|01110|01000|01000|00000'),
    'G': (6, '000000|001110|010000|010110|010010|001100|000000'),
    'H': (6, '000000|010010|010010|011110|010010|010010|000000'),
    'I': (3, '000|010|010|010|010|010|000'),
    'J': (6, '000000|000010|000010|000010|010010|001100|000000'),
    'K': (6, '000000|010010|010100|011000|010100|010010|000000'),
    'L': (5, '00000|01000|01000|01000|01000|01110|00000'),
    'M': (7, '0000000|0100010|0110110|0101010|0100010|0100010|0000000'),
    'N': (7, '0000000|0100010|0110010|0101010|0100110|0100010|0000000'),
    'O': (6, '000000|001100|010010|010010|010010|001100|000000'),
    'P': (6, '000000|011100|010010|011100|010000|010000|000000'),
    'Q': (6, '000000|001100|010010|010010|010010|001100|000010'),
    'R': (6, '000000|011100|010010|011100|010100|010010|000000'),
    'S': (6, '000000|001110|010000|001100|000010|011100|000000'),
    'T': (5, '00000|01110|00100|00100|00100|00100|00000'),
    'U': (6, '000000|010010|010010|010010|010010|001100|000000'),
    'V': (7, '0000000|0100010|0100010|0010100|0010100|0001000|0000000'),
    'W': (7, '0000000|0100010|0101010|0101010|0101010|0010100|0000000'),
    'X': (7, '0000000|0100010|0010100|0001000|0010100|0100010|0000000'),
    'Y': (7, '0000000|0100010|0010100|0001000|0001000|0001000|0000000'),
    'Z': (5, '00000|01110|00010|00100|01000|01110|00000'),
    '0': (6, '000000|001100|010010|010010|010010|001100|000000'),
    '1': (5, '00000|01100|00100|00100|00100|01110|00000'),
    '2': (6, '000000|011100|000010|001100|010000|011110|000000'),
    '3': (6, '000000|011100|000010|001100|000010|011100|000000'),
    '4': (6, '000000|010100|010100|011110|000100|000100|000000'),
    '5': (6, '000000|011110|010000|011100|000010|011100|000000'),
    '6': (6, '000000|001100|010000|011100|010010|001100|000000'),
    '7': (6, '000000|011110|000010|000100|001000|001000|000000'),
    '8': (6, '000000|001100|010010|001100|010010|001100|000000'),
    '9': (6, '000000|001100|010010|001110|000010|001100|000000'),
    ' ': (4, '0000|0000|0000|0000|0000|0000|0000'),
    '.': (3, '000|000|000|000|000|010|000'),
    ',': (4, '0000|0000|0000|0000|0000|0010|0100'),
    ':': (3, '000|000|010|000|010|000|000'),
    '/': (5, '00000|00010|00010|00100|01000|01000|00000'),
    '-': (5, '00000|00000|00000|01110|00000|00000|00000'),
    '+': (7, '0000000|0001000|0001000|0111110|0001000|0001000|0000000'),
    '!': (3, '000|010|010|010|000|010|000'),
    '?': (6, '000000|011100|000010|001100|000000|001000|000000'),
    "'": (3, '000|010|010|000|000|000|000'),
    '#': (7, '0000000|0010100|0111110|0010100|0111110|0010100|0000000'),
    '&': (6, '000100|001110|010000|001100|010000|001110|000100'),
    '(': (4, '0000|0010|0100|0100|0100|0010|0000'),
    ')': (4, '0000|0100|0010|0010|0010|0100|0000'),
    '%': (7, '0000000|0110100|0110100|0001000|0010110|0010110|0000000'),
    '·': (3, '000|000|000|010|000|000|000'),
}

GOLD, GOLD_D, TXT, MUTED, DIM = '#FFD93D', '#D4A017', '#F0F3F6', '#8B949E', '#6E7681'
BG, EDGE, HI, LO = '#161B22', '#05070A', '#232B36', '#0E1217'
LEVELS = {  # base, highlight, shade
    1: ('#5C4A12', '#7A6218', '#3F320B'),
    2: ('#9A760E', '#B88E14', '#6B520A'),
    3: ('#D4A017', '#F2C230', '#9E7608'),
    4: ('#FFD93D', '#FFF3A6', '#C99A12'),
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
    return sum(FONT.get(c, FONT[' '])[0] for c in s.upper()) * scale


def text(s, x, y, scale, color, anchor='start'):
    """Pixel text; y is the top of the capitals."""
    if anchor == 'end':
        x -= text_width(s, scale)
    elif anchor == 'middle':
        x -= text_width(s, scale) // 2
    out = []
    cx = x
    for ch in s.upper():
        adv, rows = FONT.get(ch, FONT[' '])
        for ry, row in enumerate(rows.split('|')):
            i = 0
            while i < len(row):
                if row[i] == '1':
                    j = i
                    while j + 1 < len(row) and row[j + 1] == '1':
                        j += 1
                    out.append(r(cx + i * scale, y + (ry - 1) * scale, (j - i + 1) * scale, scale, color))
                    i = j + 1
                else:
                    i += 1
        cx += adv * scale
    return ''.join(out)


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


MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']


def month_day(date):
    return f'{MONTHS[int(date[5:7]) - 1]} {int(date[8:10])}'


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

    W, H = 1200, 392
    b = [panel(W, H)]
    # headline
    b.append(text('Contributions', 36, 36, 3, GOLD))
    num = f'{total:,}'.replace(',', ' ')
    b.append(text(num, 36 + 4, 62 + 4, 9, GOLD_D))
    b.append(text(num, 36, 62, 9, TXT))
    b.append(text('in the last 12 months', 36, 120, 3, MUTED))
    # stat slots
    stats = [('Streak', str(current), 'day' if current == 1 else 'days'),
             ('Longest', str(longest), 'day' if longest == 1 else 'days'),
             ('Best day', str(best['contributionCount'] if best else 0), 'on ' + (month_day(best['date']) if best else '-'))]
    sw, gap = 220, 14
    x0 = W - 36 - 3 * sw - 2 * gap
    for i, (lbl, val, unit) in enumerate(stats):
        x = x0 + i * (sw + gap)
        b.append(slot(x, 32, sw, 104))
        b.append(text(lbl, x + 18, 50, 3, MUTED))
        b.append(text(val, x + 18, 78, 6, GOLD))
        ux = x + 26 + text_width(val, 6)
        room = x + sw - 14 - ux
        for us, uy in ((3, 93), (2, 96)):      # shrink the unit if it does not fit
            if text_width(unit, us) <= room or us == 2:
                break
        if text_width(unit, us) > room:
            unit = unit.replace('on ', '')
        b.append(text(unit, ux, uy, us, MUTED))
    # month labels + grid
    cs, step = 18, 21
    gx = (W - (len(weeks) * step - 3)) // 2
    gy = 196
    last_label = -9
    prev_month = None
    for wi, w in enumerate(weeks):
        first = w['contributionDays'][0]['date']
        m = int(first[5:7])
        if m != prev_month and wi - last_label >= 3 and wi < len(weeks) - 1:
            if prev_month is not None or int(first[8:10]) <= 7:
                b.append(text(MONTHS[m - 1],
                              gx + wi * step, gy - 26, 3, DIM))
                last_label = wi
        prev_month = m
    for wi, w in enumerate(weeks):
        col = []
        for d in w['contributionDays']:
            lvl = LEVEL_NAMES.get(d['contributionLevel'], 0)
            col.append(cell(gx + wi * step, gy + d['weekday'] * step, lvl, d['date']))
        # columns drop in one after another when the image loads
        # (visible by default, so renderers without SMIL still show the calendar)
        b.append(f'<g><animate attributeName="opacity" values="0;1" keyTimes="0;{min(.99, wi * 0.02 / 1.2):.3f}" '
                 f'calcMode="discrete" dur="1.2s" fill="freeze"/>{"".join(col)}</g>')
    # today: a blinking selection frame
    if days:
        last = days[-1]
        tx, ty = gx + (len(weeks) - 1) * step - 3, gy + last['weekday'] * step - 3
        b.append(f'<g fill="none" stroke="{TXT}" stroke-width="2"><rect x="{tx + 1}" y="{ty + 1}" width="{cs + 4}" height="{cs + 4}"/>'
                 f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></g>')
    # footer: updated date + legend
    fy = gy + 7 * step + 22
    b.append(text(f'Updated {today}', gx, fy, 3, DIM))
    lx = gx + len(weeks) * step - 3
    b.append(text('More', lx, fy, 3, DIM, anchor='end'))
    lx -= text_width('More', 3) + 10 + 5 * step
    for lv in range(5):
        b.append(cell(lx + lv * step, fy - 2, lv, f'legend{lv}'))
    b.append(text('Less', lx - 10, fy, 3, DIM, anchor='end'))
    title = f'{total} contributions in the last year, current streak {current}, longest streak {longest}'
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
