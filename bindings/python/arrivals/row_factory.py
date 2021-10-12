import collections
import math
import time

from transit_service import TransitLine

Row = collections.namedtuple('Row', ['name', 'description', 'etas', 'color', 'y', 'dx_name', 'dx_description'])

class RowFactory:
    def create_rows(self, transit_lines, vertical_offset, horizontal_offset, cell_height, cell_width, max_rows):
        rows = []
        current_time = time.time()

        filtered_transit_lines = [transit_line for transit_line in transit_lines if any(
            eta for eta in transit_line.etas if self.is_visible_eta(eta, current_time)
        )]

        if len(filtered_transit_lines) == max_rows:
            # not enough rows to fill viewport; duplicate list as workaround
            filtered_transit_lines.extend(filtered_transit_lines)

        for i, transit_line in enumerate(filtered_transit_lines):
            y = (i + 1) * cell_height - vertical_offset
            if y < 0:
                y += len(filtered_transit_lines) * cell_height

            if len(filtered_transit_lines) >= max_rows:
                pseudo_y = y
            else:
                pseudo_y = -horizontal_offset

            should_scroll_name = len(transit_line.name) > 4
            should_scroll_description = len(transit_line.description) > 17
            
            rows.append(Row(
                name=transit_line.name,
                description=transit_line.description,
                etas=self.format_etas(transit_line.etas, current_time),
                color=transit_line.color,
                y = y,
                # TODO: define _/‾\_/‾\ cycle based on horizontal_offset & string lengths
                dx_name = -self.beveled_zigzag(
                    4 * cell_height - pseudo_y,
                    (len(transit_line.name) - 4) * cell_width,
                    2 * cell_height
                ) if should_scroll_name else 0,
                dx_description = -self.beveled_zigzag(
                    4 * cell_height - pseudo_y,
                    (len(transit_line.description) - 17) * cell_width,
                    2 * cell_height
                ) if should_scroll_description else 0
            ))

        return rows

    def beveled_zigzag(self, x, height, bevel_width):
        if height + bevel_width == 0:
            return 0
        return round(max(
            0,
            min(
                height,
                math.acos(
                    math.cos((x - bevel_width / 2) * math.pi / (height + bevel_width))
                ) / math.pi * (height + bevel_width) - (bevel_width / 2)
            )
        ))

    def format_etas(self, etas, current_time):
        eta_strings = self.convert_etas(etas, current_time)
        text = f'{eta_strings[0]}'
        for eta_string in eta_strings[1:]:
            if len(text) + 1 + len(eta_string) + 1 <= 8:
                text += f',{eta_string}'
            else:
                break
        text += 'm'
        return text
    
    def convert_etas(self, etas, current_time):
        return [str(int((eta - current_time) // 60)) for eta in etas if self.is_visible_eta(eta, current_time)]
    
    def is_visible_eta(self, eta, current_time):
        return (eta - current_time) // 60 > 0
