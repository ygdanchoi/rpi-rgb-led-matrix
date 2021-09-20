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
            etas = self.get_etas(transit_line, current_time)

            if not etas:
                continue

            text = f'{transit_line.name[:4]:<5}{transit_line.description[:17]:<19}{etas[0]}'
            for eta in etas[1:]:
                if len(text) + 1 + len(eta) + 1 <= 32:
                    text += f',{eta}'
                else:
                    break
            text += 'm'
            
            rows.append(Row(
                text=text,
                color=transit_line.color
            ))

        return rows
    
    def get_etas(self, transit_line, current_time):
        return [self.format_eta(eta, current_time) for eta in transit_line.etas if current_time // 60 < eta // 60]
    
    def format_eta(self, eta, current_time):
        return str(int(math.ceil((eta - current_time) / 60)))
