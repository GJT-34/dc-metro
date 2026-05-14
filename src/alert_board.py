import displayio
from adafruit_display_text.label import Label
from config import config
from utils import wrap_text_pixel_perfect, calculate_string_width

class AlertBoard:
    def __init__(self, parent_group, font):
        self.group = displayio.Group()
        self.font = font

        # 1. Setup variables for Checkerboards FIRST
        pattern_bm = displayio.Bitmap(6, 7, 2)
        palette = displayio.Palette(2)
        palette[0] = 0x000000 
        palette[1] = config.get('text_color', 0xFF6600)

        # Draw the checkerboard pattern into the bitmap
        for x in range(3):
            for y in range(1, 4): pattern_bm[x, y] = 1
        for x in range(3, 6):
            for y in range(4, 7): pattern_bm[x, y] = 1

        # 2. Now create TileGrids using those variables
        self.top_checker = displayio.TileGrid(pattern_bm, pixel_shader=palette, width=11, height=1, 
                                             tile_width=6, tile_height=7, x=1, y=0)
        self.bottom_checker = displayio.TileGrid(pattern_bm, pixel_shader=palette, width=11, height=1, 
                                                tile_width=6, tile_height=7, x=1, y=23)
        
        # Set hidden properties AFTER creation
        self.top_checker.hidden = True
        self.bottom_checker.hidden = True
        self.group.append(self.top_checker)
        self.group.append(self.bottom_checker)

        # 3. Label Pool for fancy headers
        self.line_label_pool = []
        for _ in range(12):
            lbl = Label(self.font, text="", color=0xFFFFFF, anchor_point=(0, 0))
            lbl.hidden = True
            self.group.append(lbl)
            self.line_label_pool.append(lbl)

        # 4. Splash/Body Labels
        self.splash_labels = []
        for _ in range(4):
            lbl = Label(font, text="", color=0xffffff, base_alignment=True, anchor_point=(0.5, 1))
            lbl.hidden = True
            self.group.append(lbl)
            self.splash_labels.append(lbl)

        # 5. Main Header
        self.header = Label(font, text="", base_alignment=True, anchor_point=(0.5, 1), anchored_position=(32, 7))
        self.header.color = config.get('heading_color', 0xFFFFFF)
        self.header.hidden = True
        self.group.append(self.header)

        # 6. Status Grid
        self.grid = {}
        coords = [('RD', 11, 15, 24), ('YL', 37, 15, 50), ('GR', 11, 23, 24), 
                  ('OR', 37, 23, 50), ('SV', 11, 31, 24), ('BL', 37, 31, 50)]

        for code, x, y, sx in coords:
            name_lbl = Label(font, text=code, base_alignment=True, anchor_point=(0, 1), anchored_position=(x, y))
            sym_lbl = Label(font, text="-", base_alignment=True, anchor_point=(0, 1), anchored_position=(sx, y))
            
            name_lbl.hidden = True
            sym_lbl.hidden = True
            
            self.group.append(name_lbl)
            self.group.append(sym_lbl)
            self.grid[code] = (name_lbl, sym_lbl, sx)

        parent_group.append(self.group)
        self.group.hidden = True

    def _reset_ui(self):
        """Total wipe of the board state."""
        self.top_checker.hidden = True
        self.bottom_checker.hidden = True
        self.header.hidden = True
        self.header.text = ""
        for lbl in self.splash_labels:
            lbl.text = ""
            lbl.hidden = True
        for lbl in self.line_label_pool:
            lbl.hidden = True
        for name_lbl, sym_lbl, _ in self.grid.values():
            name_lbl.hidden = True
            sym_lbl.hidden = True

    def update(self, mode, data, header_text=None, color=0xFFFFFF):
        self._reset_ui()
        
        if mode == 'splash':
            self.top_checker.hidden = False
            self.bottom_checker.hidden = False
            # If code.py passes 'header' in the data dict, use that
            text_to_split = header_text
            parts = text_to_split.split('\n') if text_to_split else [""]
            for i, part in enumerate(parts[:2]):
                self.splash_labels[i].text = part
                self.splash_labels[i].color = color
                self.splash_labels[i].anchored_position = (32, 15 + (i * 8))
                self.splash_labels[i].hidden = False

        elif mode == 'rail_status':
            self.display_status(data.get('unaffected_lines', []), data.get('affected_lines', []))

        elif mode == 'detail':
            lines_affected = data.get('lines_affected', '')
            body_text = data.get('body_lines', '')
            page_idx = data.get('page_index', 0)
            use_fancy = config.get('show_lines_in_their_colors', False)

            # Determine if we draw the color-coded line header
            has_header = use_fancy and page_idx == 0 and bool(lines_affected)
            
            if has_header:
                self.render_inline_lines(lines_affected, config.get('train_line_color', {}), color)
            
            self._render_body_text(body_text, color, page_index=page_idx, has_header=has_header)

        elif mode == 'elevator_outage':
            # Elevators use the standard body text renderer
            default_text = config.get('text_color', 0xFF6600)
            self._render_body_text(data, color=default_text)

        self.group.hidden = False

    def display_status(self, unaffected_lines_list, affected_lines_list):
        self.header.text = "METRO STATUS"
        self.header.color = config.get('heading_color', 0xFFFFFF)
        self.header.anchored_position = (32, 7)
        self.header.hidden = False
        
        use_fancy = config.get('show_lines_in_their_colors', False)
        line_colors = config.get('train_line_color', {})
        default_text = config.get('text_color', 0xFF6600)
        color_excl = config.get('status_exclamation_color', 0xFF0000)
        color_dash = config.get('status_dash_color', 0xFF6600)

        for code, (name_lbl, sym_lbl, sx) in self.grid.items():
            name_lbl.color = line_colors.get(code, default_text) if use_fancy else default_text
            name_lbl.hidden = False
            sym_lbl.hidden = False

            if code in affected_lines_list:
                sym_lbl.text = "!"
                sym_lbl.color = color_excl
                sym_lbl.anchored_position = (sx + 1, sym_lbl.anchored_position[1])
            else:
                sym_lbl.text = "-"
                sym_lbl.color = color_dash
                sym_lbl.anchored_position = (sx, sym_lbl.anchored_position[1])

    def render_inline_lines(self, lines_str, color_map, default_color):
        codes = [c.strip().upper() for c in lines_str.split(';') if c.strip().isalpha()]
        
        use_fancy = config.get('show_lines_in_their_colors', False)
        
        # Calculate width
        total_width = 0
        for i, code in enumerate(codes):
            total_width += calculate_string_width(code, self.font)
            if i < len(codes) - 1: total_width += calculate_string_width(",", self.font) + 2
            elif i == len(codes) - 1: total_width += calculate_string_width(":", self.font) + 2

        current_x = (64 - total_width) // 2
        for i, code in enumerate(codes):
            # Line Text
            lbl = self.line_label_pool[i * 2]
            lbl.text = code
            lbl.color = color_map.get(code, default_color) if use_fancy else default_color
            lbl.anchored_position = (current_x, 7)
            lbl.anchor_point = (0, 1)
            lbl.hidden = False
            current_x += calculate_string_width(code, self.font)
            
            # Separator
            sep = self.line_label_pool[i * 2 + 1]
            char = ":" if i == len(codes) - 1 else ","
            sep.text = char
            sep.color = default_color
            sep.anchored_position = (current_x, 6 if char == ":" else 7) # Colon offset
            sep.anchor_point = (0, 1)
            sep.hidden = False
            current_x += calculate_string_width(char, self.font) + 2

    def _render_body_text(self, text, color, page_index=0, has_header=False):
        current_start_y = 8 if (has_header and page_index == 0) else 0
        lines = text.split('\n')
        
        for i in range(len(self.splash_labels)):
            lbl = self.splash_labels[i]
            if i < len(lines):
                lbl.text = lines[i]
                lbl.color = color
                y_pos = (i * 8) + 7 + current_start_y
                if y_pos <= 31:
                    lbl.anchored_position = (32, y_pos)
                    lbl.hidden = False
            else:
                lbl.hidden = True

    def build_elevator_string(self, counts):
        sorted_stations = sorted(counts.keys())
        station_strings = [f"{n} ({counts[n]})" if counts[n] > 1 else n for n in sorted_stations]
        
        if not station_strings: return ""
        if len(station_strings) == 1: return f"Elevator outages at {station_strings[0]}."
        if len(station_strings) == 2: return f"Elevator outages at {station_strings[0]} & {station_strings[1]}."
        return "Elevator outages at " + ", ".join(station_strings[:-1]) + f", & {station_strings[-1]}."