import time
time.sleep(2) # Give the hardware and USB serial a moment to settle
import displayio 
displayio.release_displays() # Release displays to prevent Errno 5
import board
from digitalio import DigitalInOut, Direction, Pull
import gc
import os
import adafruit_requests
import adafruit_connection_manager
from adafruit_matrixportal.matrix import Matrix
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
import wifi

from config import config
from metro_api import MetroApi
from train_board import TrainBoard
from alert_board import AlertBoard
from utils import report_memory, log_screen, safe_refresh, wrap_text_pixel_perfect, STATIONS_FOR_OUTAGES

gc.collect()

# --- 1. Hardware & Display Setup ---

matrix = Matrix(width=64, height=32, bit_depth=3)
display = matrix.display
display.auto_refresh = False

matrix_group = displayio.Group() # trains/alerts: in super_group
trains_subgroup = displayio.Group() # train arrival data: in matrix_group
alerts_subgroup = displayio.Group() # alerts data: in matrix_group
matrix_group.append(trains_subgroup)
matrix_group.append(alerts_subgroup)
indicator_group = displayio.Group() # button press indicators: in super_group
super_group = displayio.Group() # the root container
super_group.append(matrix_group)
super_group.append(indicator_group)
display.root_group = super_group

shared_font = bitmap_font.load_font('metroesque.bdf')

loading_label = Label(
    shared_font, 
    text="Loading...", 
    color=config['text_color'],
    base_alignment=True,
    anchor_point=(0.5, 1),
    anchored_position=(32, 19)
)
matrix_group.append(loading_label)
safe_refresh(display)

gc.collect()

# --- 2. Indicators & Buttons ---

indicator_pixels_color = config.get('indicator_pixels_color', [0x000000])
indicator_bitmap = displayio.Bitmap(64, 1, len(indicator_pixels_color))
indicator_palette = displayio.Palette(len(indicator_pixels_color))
for i, color in enumerate(indicator_pixels_color):
    indicator_palette[i] = color
indicator_tile_grid = displayio.TileGrid(indicator_bitmap, pixel_shader=indicator_palette)
indicator_pixels_subgroup = displayio.Group(x=0, y=31)
indicator_pixels_subgroup.append(indicator_tile_grid)
indicator_group.append(indicator_pixels_subgroup)

def get_pin(pin_id):
    try:
        p = DigitalInOut(pin_id)
        p.direction = Direction.INPUT
        p.pull = Pull.UP
        return p
    except ValueError:
        # If the pin is already in use (common during soft-reboots)
        # some users prefer to deinit, but usually, a clean script start handles it.
        raise RuntimeError(f"Could not initialize pin {pin_id}. Is it already in use?")

pin_up = get_pin(board.BUTTON_UP)
pin_down = get_pin(board.BUTTON_DOWN)

gc.collect()

# --- 3. WiFi Setup ---

radio = wifi.radio
wifi_max_attempts = config.get('wifi_max_attempts', 5)
attempt = 0
connected = False
print("Connecting to wifi...")

while not connected:
    try:
        loading_label.text = f"     Wifi\ntry {attempt+1} of {wifi_max_attempts}"
        loading_label.anchored_position=(32, 23)
        safe_refresh(display)

        radio.connect(os.getenv("WIFI_SSID"), os.getenv("WIFI_PASSWORD"))
            
        connected = True
        loading_label.text = ""

    except Exception as e:
        attempt += 1
        print(f"Attempt {attempt} failed: {e}")
        if attempt >= wifi_max_attempts:
            loading_label.color = config.get('heading_color', 0xFF0000)
            loading_label.text = "Wifi Error"
            safe_refresh(display)
            while True:
                time.sleep(60)
        else:
            time.sleep(2)

pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)
requests = adafruit_requests.Session(pool, ssl_context)
print("Connected!")

gc.collect()

# --- 4. State Management ---
api = MetroApi()
train_board = TrainBoard(trains_subgroup, shared_font)
alert_board = AlertBoard(alerts_subgroup, shared_font)
start_secs = time.monotonic() 
current_idx = 0
is_rotating = config.get('start_in_rotating_mode', True)
show_rail_alerts = config.get('rail_alert_display_frequency', 600) >= 0
show_elevator_outages = config.get('elevator_outage_display_frequency', 1200) >= 0
up_was_pressed = down_was_pressed = False
button_up_time = button_down_time = 0
def set_indicator(color_idx):
    for x in range(64): indicator_bitmap[x, 0] = color_idx

def blink_indicator_pixels(color_idx, times, duration):
    for _ in range(times):
        set_indicator(color_idx); safe_refresh(display); time.sleep(duration)
        set_indicator(0); safe_refresh(display); time.sleep(duration)

def check_buttons():
    global up_was_pressed, down_was_pressed, button_up_time, button_down_time
    global is_rotating, show_rail_alerts, show_elevator_outages
    
    now = time.monotonic()
    threshold = config.get('long_press_threshold', 0.5)
    long_blink = config.get('long_blink_time', 0.5)
    short_blink = config.get('short_blink_time', 0.25)

    # --- UP BUTTON: Rotate (Long) / Advance (Short) ---

    if not pin_up.value and not up_was_pressed:
        button_up_time = now
        up_was_pressed = True

    if pin_up.value and up_was_pressed:
        duration = now - button_up_time
        up_was_pressed = False # Reset immediately

        if duration >= threshold:
            # --- LONG PRESS: TOGGLE STATE ---
            is_rotating = not is_rotating
            
            if not is_rotating:
                # Toggled to Stationary: 1 indicator pixels blink using color 1
                print(f"[{time.monotonic() - start_secs:.1f}s] STATE: STATIONARY")
                blink_indicator_pixels(1, 1, long_blink)
            else:
                # Toggled to Rotating: 2 indicator pixels blinks using color 1
                print(f"[{time.monotonic() - start_secs:.1f}s] STATE: ROTATING")
                blink_indicator_pixels(1, 2, short_blink)
            
            return "STATE_CHANGE_ROTATION"
            
        else:
            # --- SHORT PRESS: ADVANCE ---
            # 1 blink using color 2
            print("MANUAL ADVANCE")
            blink_indicator_pixels(2, 1, short_blink)
            return "MOVE_NEXT"

    # --- DOWN BUTTON: Detailed Alerts (Short) / Elevator Outages (Long) ---
    if not pin_down.value and not down_was_pressed:
        button_down_time = now
        down_was_pressed = True
        
    if pin_down.value and down_was_pressed:
        duration = now - button_down_time
        down_was_pressed = False
        
        if duration < threshold:
            # SHORT PRESS: Toggle Elevator Outages (True/False)
            show_elevator_outages = not show_elevator_outages
            new_state = show_elevator_outages
            
            # Visual Feedback: 1 blink for OFF, 2 blinks for ON (color 4)
            blinks = 2 if new_state else 1
            blink_indicator_pixels(4, blinks, long_blink)
            
            state_label = "ON" if new_state else "OFF"
            print(f"[{time.monotonic() - start_secs:.1f}s] ELEVATOR OUTAGES: {state_label}")
            
            return "STATE_CHANGE_ALERTS" # Force a rotation rebuild
            
        else:
            # LONG PRESS: Toggle Detailed Rail Alerts (True/False)
            show_rail_alerts = not show_rail_alerts
            new_state = show_rail_alerts
            
            # Visual Feedback: 1 blink for OFF, 2 blinks for ON (color 3)
            blinks = 2 if new_state else 1
            blink_indicator_pixels(3, blinks, short_blink)
            
            state_label = "ON" if new_state else "OFF"
            print(f"[{time.monotonic() - start_secs:.1f}s] DETAILED ALERTS: {state_label}")
            return "STATE_CHANGE_ALERTS" # Force a rotation rebuild


    return None

gc.collect()
report_memory()

# --- 5. Main Loop ---

active_rotation = []
last_rail_status_display_time = -config.get('rail_status_display_frequency', 60)
last_rail_alert_display_time = -config.get('rail_alert_display_frequency', 60)
last_elevator_outages_display_time = -config.get('elevator_outage_display_frequency', 60)
last_rotation_time = time.monotonic()
is_repeated_screen = False
loading_label.hidden = True
trains_subgroup.hidden = True
alerts_subgroup.hidden = True
safe_refresh(display)
intermission = config.get('metro_api_fetch_intermission', 30)
last_fetch_time_alerts = -100
last_fetch_time_elevators = -100
last_fetch_time_trains = {}
rail_alerts = []
elevator_outages = []
train_predictions_cache = {}

# Terminology: "line" means train line, not a line of pixels or a line of text
 
while True:
    gc.collect() 
    now = time.monotonic()

    # We rebuild screenlist on first pass & after each screen rotation cycle
    if current_idx == 0:

        # 1. THE CONDUCTOR (DETERMINES HOW MANY & WHICH SCREENS TO INCLUDE)
        # We rebuild if:
        # A) It's the very first run (active_rotation is empty)
        # B) We are back at the start, unless we are stationary and repeating the same screen

        should_rebuild = not active_rotation or not is_repeated_screen

        if should_rebuild:
            new_rotation = []

            # --- TRAIN PLACEHOLDERS ---
            for stat in config.get('train_arrival_screens', []):
                new_rotation.append({
                    'type': 'train',
                    'station_code': stat.get('station_code', 'A01'),
                    'config_details': stat 
                })

            # --- RAIL STATUS & DETAILED RAIL ALERTS ---
            status_interval = config.get('rail_status_display_frequency', 120)
            alert_interval = config.get('rail_alert_display_frequency', 600)

            time_since_status = now - last_rail_status_display_time
            time_since_alerts = now - last_rail_alert_display_time

            # We fetch data if either "card" is due to be added to the playlist
            due_for_status = status_interval >= 0 and (status_interval == 0 or time_since_status >= status_interval)
            due_for_alerts = show_rail_alerts and (alert_interval == 0 or time_since_alerts >= alert_interval)

            if due_for_status or due_for_alerts:
                try:

                    # Check if the pantry data is stale
                    if (now - last_fetch_time_alerts) >= intermission:
                        rail_alerts = api.fetch_rail_alerts(requests) or []
                        last_fetch_time_alerts = now  # Record the specific fetch time
                        print(f"[{time.monotonic() - start_secs:.1f}s] Fresh Fetch: Rail Alerts")
   
                    # --- RAIL STATUS ---
                    if due_for_status:
                        all_lines = ["RD", "YL", "GR", "OR", "SV", "BL"]
                        affected_lines = []
                        for inc in rail_alerts:
                            affected = inc.get('LinesAffected', '')
                            for l in all_lines:
                                if l in affected and l not in affected_lines:
                                    affected_lines.append(l)
                        unaffected_lines = [l for l in all_lines if l not in affected_lines]

                        if config.get('show_splash'):
                            new_rotation.append({'type': 'splash', 'header': "METRORAIL\nSTATUS"})
                        
                        new_rotation.append({
                            'type': 'rail_status',
                            'unaffected_lines_list': unaffected_lines,
                            'affected_lines_list': affected_lines
                        })

                    # --- DETAILED ALERTS ---
                    if due_for_alerts and rail_alerts:
                        target_lines = config.get('rail_alert_lines', [])
                        alert_pages_added = False
                        use_fancy = config.get('show_lines_in_their_colors', False)

                        for inc in rail_alerts:
                            lines_str = inc.get('LinesAffected', 'All').rstrip(';')
                            affected_lines_list = [l.strip() for l in lines_str.split(';') if l.strip()]
                            
                            # 1. Filter by line
                            if not target_lines or any(line in affected_lines_list for line in target_lines):
                                desc = inc.get('Description', '').strip()
                                if not desc: 
                                    continue

                                # 2. DEFINE all_wrapped HERE so it is always available
                                if not use_fancy:
                                    clean_lines = lines_str.rstrip('; ').replace(';', ',')
                                    full_text = f"{clean_lines}: {desc}"
                                    all_wrapped = wrap_text_pixel_perfect(full_text, 64, shared_font)
                                else:
                                    all_wrapped = wrap_text_pixel_perfect(desc, 64, shared_font)

                                # 3. SAFETY CHECK: If wrapping failed, move to next alert
                                if not all_wrapped:
                                    print("Wrap_text_pixel_perfect returned nothing")
                                    continue

                                # 4. Add Splash
                                if config.get('show_splash') and not alert_pages_added:
                                    new_rotation.append({'type': 'splash', 'header': "METRORAIL\nALERTS"})
                                    alert_pages_added = True

                                # 5. Add Detail Cards
                                if not use_fancy:
                                    for i in range(0, len(all_wrapped), 4):
                                        new_rotation.append({
                                            'type': 'rail_alert',
                                            'lines_affected': lines_str,
                                            'body_lines': "\n".join(all_wrapped[i:i+4]),
                                            'page_index': i // 4
                                        })
                                else:
                                    # Page 1 (Top row reserved for fancy boxes)
                                    new_rotation.append({
                                        'type': 'rail_alert',
                                        'lines_affected': lines_str,
                                        'body_lines': "\n".join(all_wrapped[:3]),
                                        'page_index': 0
                                    })
                                    # Pages 2+
                                    remaining = all_wrapped[3:]
                                    for i in range(0, len(remaining), 4):
                                        new_rotation.append({
                                            'type': 'rail_alert',
                                            'lines_affected': lines_str,
                                            'body_lines': "\n".join(remaining[i:i+4]),
                                            'page_index': (i // 4) + 1
                                        })

                except Exception as e:
                    print(f"[{time.monotonic() - start_secs:.1f}s] [ERROR] Rail Logic: {e}")

            # --- ELEVATOR OUTAGES ---
            elevator_outage_interval = config.get('elevator_outage_display_frequency', 1200)
            time_since_last_elevator_outage = now - last_elevator_outages_display_time
            if show_elevator_outages and (elevator_outage_interval == 0 or time_since_last_elevator_outage >= elevator_outage_interval):
                try:
                    # elevator_outages is a list of station codes with outages
                    # Separate timer check for elevators
                    if (now - last_fetch_time_elevators) >= intermission:
                        elevator_outages = api.fetch_elevator_outages(requests) or []
                        last_fetch_time_elevators = now  # Record the specific fetch time
                        print(f"[{time.monotonic() - start_secs:.1f}s] Fresh Fetch: Elevator Outages")

                    if elevator_outages:
                        outage_counts = {}
                        for code in elevator_outages:
                            # Check if this station code is one we care about mapping
                            if code in STATIONS_FOR_OUTAGES:
                                name = STATIONS_FOR_OUTAGES[code]
                                outage_counts[name] = outage_counts.get(name, 0) + 1

                        if outage_counts:
                            # 1. Generate the full sentence here so we can measure it
                            full_sentence = alert_board.build_elevator_string(outage_counts) # Helper below
                            wrapped = wrap_text_pixel_perfect(full_sentence, 64, shared_font)
                            
                            if config.get('show_splash'):
                                new_rotation.append({'type': 'splash', 'header': "ELEVATOR\nOUTAGES", 'color': 0xFF6600})

                            # 2. Add one rotation item PER 4 lines of text
                            for i in range(0, len(wrapped), 4):
                                new_rotation.append({
                                    'type': 'elevator_outage',
                                    'body_lines': "\n".join(wrapped[i:i+4]),
                                    'page_index': i // 4
                                })
                except Exception as e:  
                    print(f"[{time.monotonic() - start_secs:.1f}s] [ERROR] Elevator Logic: {e}")

            active_rotation = new_rotation
            print(f"Playlist updated. Items: {len(active_rotation)}")

    # --- 2. THE PERFORMER (HANDLES UI EXECUTION LOGIC)
    if not active_rotation:
        print("Waiting for Conductor to build rotation...")
        time.sleep(1)
        continue 

    active_item = active_rotation[current_idx]

    try:
        if active_item['type'] == 'train':
            trains_subgroup.hidden = False
            alerts_subgroup.hidden = True

            target_cfg = active_item.get('config_details')
            s_code = active_item.get('station_code')
            lines = "".join(target_cfg.get('lines', []))
            group_name = "".join([str(g) for g in target_cfg.get('groups', [])])
            cache_key = f"{s_code}_{group_name}"
            
            age = now - last_fetch_time_trains.get(cache_key, -100)

            if age >= intermission:
                try:
                    train_predictions = api.fetch_train_predictions(requests, target_cfg) or []
                    train_predictions_cache[cache_key] = train_predictions
                    last_fetch_time_trains[cache_key] = now
                    print(f"[{time.monotonic() - start_secs:.1f}s] Fresh Fetch: {cache_key}")
                except Exception as e:
                    print(f"[{time.monotonic() - start_secs:.1f}s] [API] Fail: {e}")
                    if cache_key not in train_predictions_cache:
                        train_predictions_cache[cache_key] = []
                
            train_data = train_predictions_cache.get(cache_key, [])
            train_board.refresh(target_cfg, train_data)
            log_screen(start_secs, is_rotating, target_cfg)

        elif active_item['type'] in ['splash', 'rail_status', 'rail_alert', 'elevator_outage']:
            trains_subgroup.hidden = True
            alerts_subgroup.hidden = False
            
            # 1. Determine the Mode and Color
            a_type = active_item['type']
            
            # Use heading_color for splashes, otherwise use functional alert colors
            if a_type == 'splash':
                alert_color = config.get('heading_color', 0xFF0000)
            else:
                alert_color = config.get('text_color', 0xFF6600)

            # 2. Routing to the Unified Update
            if a_type == 'splash':                
                alert_board.update('splash', None, header_text=active_item['header'], color=alert_color)
            
            elif a_type == 'rail_status':
                data = {
                    'unaffected_lines': active_item.get('unaffected_lines_list', []),
                    'affected_lines': active_item.get('affected_lines_list', [])
                }
                alert_board.update('rail_status', data)

            elif a_type == 'rail_alert':
                data = {
                    'lines_affected': active_item.get('lines_affected', 'All'),
                    'body_lines': active_item.get('body_lines', ''),
                    'page_index': active_item.get('page_index', 0)
                }
                # Let the board handle the rest!
                alert_board.update('detail', data, color=alert_color)

            elif a_type == 'elevator_outage':
                alert_board.update('elevator_outage', active_item.get('body_lines', ''))

            # 3. Logging
            log_header = active_item.get('header', 'ALERT').replace('\n', ' ')
            log_screen(start_secs, is_rotating, {
                'station_code': 'STATUS', 
                'lines': [log_header],
                'groups': [] 
            })

    except Exception as e:
        print(f"[{time.monotonic() - start_secs:.1f}s] [ERROR] Loop execution: {e}")

    # --- 3. THE STAGE MANAGER (TIMING & ROTATION) ---
    safe_refresh(display)
    report_memory()

    if active_item.get('type') == 'splash':
        rotation_wait = config.get('splash_rotation_speed', 2)

    elif active_item.get('type') in ['rail_alert', 'elevator_outage']:
        rotation_wait = config.get('alerts_rotation_speed', 5)

    else:
        # Existing speed for the main train predictions
        rotation_wait = config.get('general_rotation_speed', 7)

    # We need to know if the loop ended because of a button press 
    # or because time just ran out.
    
    start_wait = time.monotonic()
    btn_result = None
    while (time.monotonic() - start_wait) < rotation_wait:
        btn_result = check_buttons()
        if btn_result:
            break
        time.sleep(0.05)

    # Check for Alert Mode Changes (Immediate Rebuild + Jump to Start)
    if btn_result == "STATE_CHANGE_ALERTS":
        current_idx = 0
        last_rail_alert_display_time = 0
        last_rail_status_display_time = 0
        last_elevator_outages_display_time = 0
        is_repeated_screen = False 
        print(f"[{time.monotonic() - start_secs:.1f}s] Alert Mode Changed: Resetting to Start.")

    # Check for Rotation Toggles (Rebuild but stay on current screen)
    elif btn_result == "STATE_CHANGE_ROTATION":
        is_repeated_screen = False
        print(f"[{time.monotonic() - start_secs:.1f}s] Rotation Toggled: is_rotating={is_rotating}")

    # Handle Manual Advance or Automatic Rotation
    else:
        should_increment = (is_rotating and not btn_result) or (btn_result == "MOVE_NEXT")

        if should_increment:
            # Match these names EXACTLY to what the Conductor uses at the top
            p_type = active_item.get('type')
            if p_type == 'rail_status':
                last_rail_status_display_time = time.monotonic()
            elif p_type == 'rail_alert':
                last_rail_alert_display_time = time.monotonic()
            elif p_type == 'elevator_outage':
                last_elevator_outages_display_time = time.monotonic()

            current_idx = (current_idx + 1) % len(active_rotation)
            is_repeated_screen = False
            last_rotation_time = time.monotonic()
        else:
            # If we were already sitting here and time ran out, it's a repeat
            is_repeated_screen = not btn_result 
