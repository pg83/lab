"""
Repology's repository-big badge, rendered the way repology-webapp does
(repology-rs, repology-webapp/src/badges.rs, font.rs, xmlwriter.rs and
handlers/badges/repository_big.rs): same cells, same geometry, same XML
text, byte for byte (see test_badge.py against their snapshots).

Text widths are the sum of DejaVu Sans 2.37 advances in f32, truncated,
as ttf_parser does it there; the advances of printable ASCII are below
(units of 2048 per em), which is all a repository badge needs.
"""

import struct

UPEM = 2048

# hmtx advances of U+0020..U+007E, DejaVuSans.ttf and DejaVuSans-Bold.ttf 2.37.
REGULAR = (
    651, 821, 942, 1716, 1303, 1946, 1597, 563, 799, 799, 1024, 1716, 651, 739, 651, 690,
    1303, 1303, 1303, 1303, 1303, 1303, 1303, 1303, 1303, 1303, 690, 690, 1716, 1716, 1716, 1087,
    2048, 1401, 1405, 1430, 1577, 1294, 1178, 1587, 1540, 604, 604, 1343, 1141, 1767, 1532, 1612,
    1235, 1612, 1423, 1300, 1251, 1499, 1401, 2025, 1403, 1251, 1403, 799, 690, 799, 1716, 1024,
    1024, 1255, 1300, 1126, 1300, 1260, 721, 1300, 1298, 569, 569, 1186, 569, 1995, 1298, 1253,
    1300, 1300, 842, 1067, 803, 1298, 1212, 1675, 1212, 1212, 1075, 1303, 690, 1303, 1716,
)
BOLD = (
    713, 934, 1067, 1716, 1425, 2052, 1786, 627, 936, 936, 1071, 1716, 778, 850, 778, 748,
    1425, 1425, 1425, 1425, 1425, 1425, 1425, 1425, 1425, 1425, 819, 819, 1716, 1716, 1716, 1188,
    2048, 1585, 1561, 1503, 1700, 1399, 1399, 1681, 1714, 762, 762, 1587, 1305, 2038, 1714, 1741,
    1501, 1741, 1577, 1475, 1397, 1663, 1585, 2259, 1579, 1483, 1485, 936, 748, 936, 1716, 1024,
    1024, 1382, 1466, 1214, 1466, 1389, 891, 1466, 1458, 702, 702, 1362, 702, 2134, 1458, 1407,
    1466, 1466, 1010, 1219, 979, 1458, 1335, 1892, 1321, 1335, 1192, 1458, 748, 1458, 1716,
)

HEADER_HEIGHT = 25
HEADER_FONT_SIZE = 15
CELL_HEIGHT = 20
CELL_FONT_SIZE = 11
CELL_HORIZONTAL_PADDING = 5
FONT_FAMILY = 'DejaVu Sans,Verdana,Geneva,sans-serif'

NEWEST_COLOR = '#4c1'
OUTDATED_COLOR = '#e05d44'
VULNERABLE_COLOR = '#e00000'
PROBLEMATIC_COLOR = '#9f9f9f'


def _f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def text_width(text, size, bold=False):
    # sum over chars of f32(advance * size / upem), in f32, then `as usize`.
    table = BOLD if bold else REGULAR
    total = _f32(0.0)

    for ch in text:
        code = ord(ch)

        if not 0x20 <= code <= 0x7e:
            raise ValueError(f'no advance for {ch!r}')

        total = _f32(total + _f32(_f32(float(table[code - 0x20]) * size) / UPEM))

    return int(total)


class Cell:
    def __init__(self, text='', color=None, align='center'):
        self.text = text
        self.color = color
        self.align = align


def _attr(value):
    return str(value).replace('&', '&amp;').replace('"', '&quot;')


def _text(value):
    return value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def tag(name, attrs, content=''):
    a = ''.join(f' {k}="{_attr(v)}"' for k, v in attrs)

    return f'<{name}{a}/>' if not content else f'<{name}{a}>{content}</{name}>'


def render_generic_badge(cells, header=None, min_width=0):
    num_columns = len(cells[0]) if cells else 0
    widths = [0] * num_columns

    for row in cells:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], text_width(cell.text, CELL_FONT_SIZE) + CELL_HORIZONTAL_PADDING * 2)

    header_height = 0

    if header:
        min_width = max(min_width, text_width(header, HEADER_FONT_SIZE, bold=True) + CELL_HORIZONTAL_PADDING * 2)
        header_height = HEADER_HEIGHT

    total_height = header_height + CELL_HEIGHT * len(cells)
    total_width = sum(widths)

    if total_width < min_width:
        if widths:
            widths[0] += min_width - total_width

        total_width = min_width

    offsets = []
    offset = 0

    for w in widths:
        offsets.append(offset)
        offset += w

    g = tag('rect', [('width', '100%'), ('height', '100%'), ('fill', '#555')])

    if header is not None:
        g += tag('g', [('fill', '#fff'), ('text-anchor', 'middle'), ('font-family', FONT_FAMILY), ('font-size', 15), ('font-weight', 'bold')],
                 tag('text', [('x', total_width // 2), ('y', HEADER_HEIGHT // 2 + 1), ('dominant-baseline', 'central'), ('fill', '#010101'), ('fill-opacity', '.3')], _text(header))
                 + tag('text', [('x', total_width // 2), ('y', HEADER_HEIGHT // 2), ('dominant-baseline', 'central')], _text(header)))

    for nrow, row in enumerate(cells):
        y = header_height + nrow * CELL_HEIGHT

        for cell, x, w in zip(row, offsets, widths):
            if cell.color is not None:
                g += tag('rect', [('x', x), ('y', y), ('width', w), ('height', CELL_HEIGHT), ('fill', cell.color)])

        g += tag('rect', [('y', y), ('width', '100%'), ('height', CELL_HEIGHT), ('fill', 'url(#grad)')])

        texts = ''

        for cell, x, w in zip(row, offsets, widths):
            if not cell.text:
                continue

            if cell.align == 'left':
                tx, anchor = x + CELL_HORIZONTAL_PADDING, 'start'
            elif cell.align == 'right':
                tx, anchor = x + w - CELL_HORIZONTAL_PADDING, 'end'
            else:
                tx, anchor = x + w // 2, 'middle'

            ty = y + CELL_HEIGHT // 2
            texts += tag('text', [('x', tx), ('y', ty + 1), ('text-anchor', anchor), ('dominant-baseline', 'central'), ('fill', '#010101'), ('fill-opacity', '.3')], _text(cell.text))
            texts += tag('text', [('x', tx), ('y', ty), ('text-anchor', anchor), ('dominant-baseline', 'central')], _text(cell.text))

        g += tag('g', [('fill', '#fff'), ('font-family', FONT_FAMILY), ('font-size', CELL_FONT_SIZE)], texts)

    return tag('svg', [('xmlns', 'http://www.w3.org/2000/svg'), ('width', total_width), ('height', total_height)],
               tag('clipPath', [('id', 'clip')], tag('rect', [('rx', 3), ('width', '100%'), ('height', '100%'), ('fill', '#000')]))
               + tag('linearGradient', [('id', 'grad'), ('x2', 0), ('y2', '100%')],
                     tag('stop', [('offset', 0), ('stop-color', '#bbb'), ('stop-opacity', '.1')])
                     + tag('stop', [('offset', 1), ('stop-opacity', '.1')]))
               + tag('g', [('clip-path', 'url(#clip)')], g))


def percentage(dividend, divisor):
    return '-' if divisor == 0 else f'{100.0 * dividend / divisor:.2f}%'


def repository_big(stats, header='Repository status'):
    """stats: dict with projects, comparable, newest, outdated, problematic,
    maintainers and, when known, vulnerable; None for an unknown repository.
    Without a vulnerable count the Vulnerable row is left out."""
    if stats is None:
        return render_generic_badge([[Cell('Repository not known or was removed', color=VULNERABLE_COLOR)]], header)

    right = 'right'
    rows = [
        [Cell('Projects total', align=right), Cell(str(stats['projects'])), Cell()],
        [Cell('Up to date', align=right), Cell(str(stats['newest']), NEWEST_COLOR),
         Cell(percentage(stats['newest'], stats['comparable']), NEWEST_COLOR)],
        [Cell('Outdated', align=right), Cell(str(stats['outdated']), OUTDATED_COLOR),
         Cell(percentage(stats['outdated'], stats['comparable']), OUTDATED_COLOR)],
    ]

    if stats.get('vulnerable') is not None:
        rows.append([Cell('Vulnerable', align=right), Cell(str(stats['vulnerable']), VULNERABLE_COLOR),
                     Cell(percentage(stats['vulnerable'], stats['projects']), VULNERABLE_COLOR)])

    rows.append([Cell('Bad versions', align=right), Cell(str(stats['problematic']), PROBLEMATIC_COLOR),
                 Cell(percentage(stats['problematic'], stats['projects']), PROBLEMATIC_COLOR)])

    if stats['maintainers'] > 0:
        rows.append([Cell('Maintainers', align=right), Cell(str(stats['maintainers'])), Cell()])

    return render_generic_badge(rows, header)
