import collections
import time

from transit_service import TransitLine

Row = collections.namedtuple('Row', ['name', 'description', 'etas', 'color', 'x', 'y'])

class RowFactory:
    def create_rows(self, transit_lines, vertical_offset, horizontal_offset, cell_height):
        rows = []
        current_time = time.time()

        filtered_transit_lines = [transit_line for transit_line in transit_lines if self.convert_etas(transit_line, current_time)]

        for i, transit_line in enumerate(filtered_transit_lines):
            y = (i + 1) * cell_height - vertical_offset
            if y < -cell_height:
                y += len(filtered_transit_lines) * cell_height
            
            rows.append(Row(
                name=transit_line.name,
                description=transit_line.description,
                etas=self.format_etas(self.convert_etas(transit_line, current_time)),
                color=transit_line.color,
                x = 0, # TODO: calculate this here instead of in TransitFeedView
                y = y
            ))

        return rows

    def format_etas(self, etas):
        text = f'{etas[0]}'
        for eta in etas[1:]:
            if len(text) + 1 + len(eta) + 1 <= 8:
                text += f',{eta}'
            else:
                break
        text += 'm'
        return text
    
    def convert_etas(self, transit_line, current_time):
        return [self.convert_eta(eta, current_time) for eta in transit_line.etas if (eta - current_time) // 60 > 0]
    
    def convert_eta(self, eta, current_time):
        return str(int((eta - current_time) // 60))
