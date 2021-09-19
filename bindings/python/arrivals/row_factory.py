import collections
import math
import time

from transit_service import TransitLine

Row = collections.namedtuple('Row', ['text', 'color'])

class RowFactory:
    def create_rows(self, transit_lines):
        rows = []
        current_time = time.time()

        for transit_line in transit_lines:
            etas = [str(int(math.ceil((eta - current_time) / 60))) for eta in sorted(transit_line.etas) if current_time // 60 < eta // 60]

            if not etas:
                continue

            text = f'{transit_line.name}'
            text += ' ' * (5 - len(text))
            text += transit_line.description[:17]
            text += ' ' * (24 - len(text))
            text += etas[0]
            e = 1
            while (e < len(etas) and len(text) + 1 + len(etas[e]) + 1 <= 32):
                text += ',' + etas[e]
                e += 1
            text += 'm'
            rows.append(Row(
                text=text,
                color=transit_line.color
            ))

        return rows
