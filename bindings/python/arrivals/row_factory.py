import collections
import time

from transit_service import TransitLine

Row = collections.namedtuple('Row', ['name', 'description', 'etas', 'color', 'y', 'dx_name', 'dx_description'])

class RowFactory:
    def create_rows(self, transit_lines, vertical_offset, horizontal_offset, cell_height, cell_width):
        rows = []
        current_time = time.time()

        filtered_transit_lines = [transit_line for transit_line in transit_lines if self.convert_etas(transit_line, current_time)]

        if len(filtered_transit_lines) == 4:
            # not enough rows to fill viewport; duplicate list as workaround
            filtered_transit_lines.extend(filtered_transit_lines)

        for i, transit_line in enumerate(filtered_transit_lines):
            y = (i + 1) * cell_height - vertical_offset
            if y < 0:
                y += len(filtered_transit_lines) * cell_height

            # TODO: do this less stupidly lol
            if vertical_offset == horizontal_offset:
                pseudo_y = y
            else:
                pseudo_y = -horizontal_offset

            should_scroll_name = len(transit_line.name) > 4
            should_scroll_description = len(transit_line.description) > 17
            
            rows.append(Row(
                name=transit_line.name,
                description=transit_line.description,
                etas=self.format_etas(self.convert_etas(transit_line, current_time)),
                color=transit_line.color,
                y = y,
                dx_name = max(
                    min(0, pseudo_y - 4 - 2 * cell_height),
                    (4 - len(transit_line.name)) * cell_width
                ) if should_scroll_name else 0,
                dx_description = max(
                    min(0, pseudo_y - 4 - 2 * cell_height),
                    (17 - len(transit_line.description)) * cell_width
                ) if should_scroll_description else 0
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
