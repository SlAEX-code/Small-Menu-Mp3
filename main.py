import os
import sys
import time
import pygame
from pygame.locals import *
import vlc

import spidev
import lgpio
import numpy as np

import board
from adafruit_seesaw import seesaw, rotaryio, digitalio

# ============================
# Seesaw Setup (Buttons & Encoder)
# ============================
i2c = board.I2C()
seesaw_device = seesaw.Seesaw(i2c, addr=0x49)

seesaw_product = (seesaw_device.get_version() >> 16) & 0xFFFF
print(f"Found product {seesaw_product}")
if seesaw_product != 5740:
    print("Wrong firmware loaded?  Expected 5740")

# Pins 1 bis 5 als Input mit Pullup konfigurieren
for pin in range(1, 6):
    seesaw_device.pin_mode(pin, seesaw_device.INPUT_PULLUP)

select = digitalio.DigitalIO(seesaw_device, 1)
up = digitalio.DigitalIO(seesaw_device, 2)
left = digitalio.DigitalIO(seesaw_device, 3)
down = digitalio.DigitalIO(seesaw_device, 4)
right = digitalio.DigitalIO(seesaw_device, 5)

encoder = rotaryio.IncrementalEncoder(seesaw_device)
last_encoder_position = encoder.position

# ============================
# Hardware Display Setup
# ============================
WIDTH, HEIGHT = 160, 128
DC_PIN = 24     # Data/Command-Pin
RESET_PIN = 25  # Reset-Pin

# ST7735 Befehle
SWRESET = 0x01  
SLPOUT  = 0x11  
COLMOD  = 0x3A  
DISPON  = 0x29  
MADCTL  = 0x36
CASET   = 0x2A  
RASET   = 0x2B  
RAMWR   = 0x2C  

# SPI und GPIO initialisieren
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 4000000  
spi.mode = 0b00

h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, DC_PIN)
lgpio.gpio_claim_output(h, RESET_PIN)

def send_command(cmd, data=None):
    lgpio.gpio_write(h, DC_PIN, 0)  # Befehl-Modus
    spi.xfer([cmd])
    if data is not None:
        lgpio.gpio_write(h, DC_PIN, 1)  # Daten-Modus
        spi.xfer(data)

def set_rotation(rotation):
    rotations = [0x00, 0x60, 0xC0, 0xA0]
    send_command(MADCTL, [rotations[rotation % 4]])

def set_window(x0, y0, x1, y1):
    send_command(CASET, [0x00, x0, 0x00, x1])
    send_command(RASET, [0x00, y0, 0x00, y1])
    send_command(RAMWR)

def init_display():
    # Hardware-Reset
    lgpio.gpio_write(h, RESET_PIN, 0)
    time.sleep(0.1)
    lgpio.gpio_write(h, RESET_PIN, 1)
    time.sleep(0.1)

    send_command(SWRESET)
    time.sleep(0.15)
    send_command(SLPOUT)
    time.sleep(0.5)
    send_command(COLMOD, [0x05])  # 16-Bit Farbmodus
    set_rotation(1)
    send_command(DISPON)
    time.sleep(0.1)

def display_image(image):
    set_window(0, 0, WIDTH - 1, HEIGHT - 1)
    lgpio.gpio_write(h, DC_PIN, 1)  # Daten-Modus
    for y in range(HEIGHT):
        chunk = []
        for x in range(WIDTH):
            r, g, b = image.getpixel((x, y))
            color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            chunk.extend([color >> 8, color & 0xFF])
        spi.xfer2(chunk)

def update_hardware_display(screen):
    # Hole die Pixel-Daten als NumPy-Array
    arr = pygame.surfarray.array3d(screen)
    # Transponiere, damit die Dimensionen (Höhe, Breite, 3) stimmen
    arr = np.transpose(arr, (1, 0, 2))

    # Konvertiere in das 16-Bit RGB565-Format:
    r = arr[:, :, 0].astype(np.uint16)
    g = arr[:, :, 1].astype(np.uint16)
    b = arr[:, :, 2].astype(np.uint16)
    color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    # Extrahiere High- und Low-Byte
    high = (color >> 8) & 0xFF
    low = color & 0xFF
    # Kombiniere die Bytes zu einem eindimensionalen Array
    rgb565 = np.dstack((high, low)).flatten().tolist()

    # Setze das Fenster für den Daten-Transfer
    set_window(0, 0, WIDTH - 1, HEIGHT - 1)
    lgpio.gpio_write(h, DC_PIN, 1)  # Daten-Modus

    # Daten in kleineren Chunks senden, z.B. 4096 Bytes pro Paket
    CHUNK_SIZE = 4096
    for i in range(0, len(rgb565), CHUNK_SIZE):
        spi.xfer2(rgb565[i:i+CHUNK_SIZE])


init_display()

# ============================
# Pygame MP3-Player Setup
# ============================
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MP3 Player")

state = "main"  # "main" = Hauptmenü, "play" = Wiedergabe

# ----------------------------
# VLC-Instanz und Media Player erstellen
# ----------------------------
vlc_instance = vlc.Instance()
player = vlc_instance.media_player_new()



mp3_folder = "mp3_files"
audio_files = [f for f in os.listdir(mp3_folder) if f.lower().endswith(('.mp3', '.wav'))]
if not audio_files:
    print("Keine Audio-Dateien gefunden!")
    sys.exit()

selected_index = 0         # Index im Hauptmenü
current_song_index = None  # Aktuell gespielter Song
paused = False             
clock = pygame.time.Clock()

import wave
try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None
    
def get_audio_length(path):
    if path.lower().endswith('.mp3') and MP3:
        return MP3(path).info.length
    elif path.lower().endswith('.wav'):
        with wave.open(path, 'r') as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    else:
        return 180.0
    

start_time = None   
song_length = None  

# Scrollvariablen
play_scroll_offset = 0
last_play_scroll_time = time.time()
main_scroll_offset = 0
last_main_scroll_time = time.time()
LEFT_MARGIN = 10
RIGHT_MARGIN = 5  
EFFECTIVE_WIDTH = WIDTH - LEFT_MARGIN - RIGHT_MARGIN
main_menu_scroll_y = 0

volume = 0.5
pygame.mixer.music.set_volume(volume)

VOLUME_DISPLAY_DURATION = 1.0  # Dauer in Sekunden, in der der Indikator sichtbar ist
last_volume_change_time = 0

# ----------------------------
# Hilfsfunktion zum Abspielen eines Songs
# ----------------------------
def play_song(index, auto_mode=False):
    global current_song_index, start_time, song_length, paused, state
    current_song_index = index
    current_file = audio_files[index]
    song_path = os.path.join(mp3_folder, current_file)
    pygame.mixer.music.load(song_path)
    pygame.mixer.music.play()
    song_length = get_audio_length(song_path)
    start_time = time.time()
    paused = False
    if not auto_mode:
        state = "play"

# ----------------------------
# Zeichenfunktionen für Menüs
# ----------------------------
my_font = pygame.font.Font('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
def draw_main_menu(screen, files, selected, current_song_index, paused, h_scroll, v_scroll):
    screen.fill((0, 0, 0))
    font = my_font
    
    NORMAL_LEFT_MARGIN = 10
    SELECTED_LEFT_MARGIN = 5   # Für ausgewählte Einträge geringerer Abstand links
    INDICATOR_SPACE = 5       # Zusätzlicher Platz für den Indikator
    effective_width_normal = WIDTH - NORMAL_LEFT_MARGIN - RIGHT_MARGIN  
    effective_width_selected = WIDTH - SELECTED_LEFT_MARGIN - RIGHT_MARGIN 
    
    y = 5 - v_scroll
    spacing = 2
    line_height = font.get_linesize()
    
    for i, filename in enumerate(files):
        base_title = os.path.splitext(filename)[0]
        # Wähle den linken Rand, falls der Eintrag ausgewählt ist
        left_margin = SELECTED_LEFT_MARGIN if i == selected else NORMAL_LEFT_MARGIN
        
        # Wenn dieser Song gerade läuft, erweitern wir den linken Rand:
        if current_song_index is not None and i == current_song_index:
            left_margin += INDICATOR_SPACE
        
        effective_width = effective_width_selected if i == selected else effective_width_normal

        display_name = base_title + "   " if i == selected else base_title
        
        # Setze die Textfarbe ? Beispiel: weiß, wenn der Song läuft, sonst grün
        text_color = (0, 215, 0)
        if current_song_index is not None and i == current_song_index:
            text_color = (255, 255, 255)
            
        if i == selected:
            pygame.draw.rect(screen, (0, 215, 0), (0, y, WIDTH, line_height +1))
            text_color = (255, 255, 255)
            left_margin = 5
        
        text_surface = font.render(display_name, True, text_color)
        
        # Zeichne den Indikator, wenn dieser Song gerade läuft
        if current_song_index is not None and i == current_song_index:
            indicator_radius = 3
            indicator_color = (0, 215, 0)  # Farbe des Indikators
            # Positioniere den Kreis z.?B. links bei x = 5, mittig in der Zeile
            indicator_x = 5
            indicator_y = y + line_height // 2
            if paused:
                rect_width = 2
                rect_height = line_height // 2
                gap = 2
                indicator_y = y + (line_height - rect_height) // 2
                pygame.draw.rect(screen, indicator_color, (indicator_x, indicator_y, rect_width, rect_height))
                pygame.draw.rect(screen, indicator_color, (indicator_x + rect_width + gap, indicator_y, rect_width, rect_height))
                
            else:
                pygame.draw.circle(screen, indicator_color, (indicator_x, indicator_y), indicator_radius)
        
        # Falls der Text länger als der verfügbare Platz ist, scrolle ihn
        if i == selected and text_surface.get_width() > effective_width:
            scrolling_surface = pygame.Surface((text_surface.get_width(), line_height))
            scrolling_surface.fill((0, 215, 0))
            scrolling_surface.blit(text_surface, (0, 0))
            effective_offset = h_scroll % text_surface.get_width()
            if effective_offset + effective_width > text_surface.get_width():
                part1_width = text_surface.get_width() - effective_offset
                screen.blit(scrolling_surface, (left_margin, y),
                            area=pygame.Rect(effective_offset, 0, part1_width, line_height))
                part2_width = effective_width - part1_width
                screen.blit(scrolling_surface, (left_margin + part1_width, y),
                            area=pygame.Rect(0, 0, part2_width, line_height))
            else:
                screen.blit(scrolling_surface, (left_margin, y),
                            area=pygame.Rect(effective_offset, 0, effective_width, line_height))
        else:
            screen.blit(text_surface, (left_margin, y))
            
        y += line_height + spacing
    pygame.display.update()
    
def tint_image(image, tint_color):
    """Färbt das übergebene Bild (Surface) mit der tint_color ein."""
    # Erstelle eine Kopie des Bildes, um das Original nicht zu verändern
    tinted_image = image.copy()
    # Fülle das Bild mit der gewünschten Farbe und multipliziere den Farbkanal
    tinted_image.fill((0,0,0,255), special_flags=pygame.BLEND_RGBA_MULT)
    tinted_image.fill(tint_color + (0,), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted_image    

def draw_play_menu(screen, current_file, progress, elapsed, total, playing, scroll_offset):
    screen.fill((0, 0, 0))
    font = pygame.font.SysFont(None, 16)
    
    icon_y = HEIGHT - 40
    icon_spacing = 25
    
    # Konfiguration des Titels im Play-Menu
    title_left_margin = 10   # Mehr Abstand links
    title_right_margin = 10  # Mehr Abstand rechts
    title_y = 10             # Vertikaler Abstand vom oberen Rand
    effective_title_width = WIDTH - title_left_margin - title_right_margin

    # Songtitel rendern
    scroll_text = os.path.splitext(audio_files[current_song_index])[0] + "   "
    title_surface = font.render(scroll_text, True, (0, 215, 0))
    title_width = title_surface.get_width()

    # Wenn der Titel länger als der verfügbare Platz ist, scrolle ihn
    if title_width > (effective_title_width * 0.9):
        scrolling_surface = pygame.Surface((title_width, 20))
        scrolling_surface.fill((0, 0, 0))
        scrolling_surface.blit(title_surface, (0, 0))
        effective_offset = scroll_offset % title_width
        if effective_offset + effective_title_width > title_width:
            part1_width = title_width - effective_offset
            screen.blit(scrolling_surface, (title_left_margin, title_y),
                        area=pygame.Rect(effective_offset, 0, part1_width, 20))
            part2_width = effective_title_width - part1_width
            screen.blit(scrolling_surface, (title_left_margin + part1_width, title_y),
                        area=pygame.Rect(0, 0, part2_width, 20))
        else:
            screen.blit(scrolling_surface, (title_left_margin, title_y),
                        area=pygame.Rect(effective_offset, 0, effective_title_width, 20))
    else:
        # Titel zentriert im Bereich zwischen title_left_margin und title_right_margin
        x = title_left_margin + (effective_title_width - title_width) // 2
        screen.blit(title_surface, (x, title_y))

        
    # Fortschrittsbalken (Bereich: 25-35 Pixel)
    bar_y = 25
    bar_height = 10
    pygame.draw.rect(screen, (50, 50, 50), (5, bar_y, WIDTH - 10, bar_height))
    prog_width = int((WIDTH - 10) * progress)
    pygame.draw.rect(screen, (0, 215, 0), (5, bar_y, prog_width, bar_height))
    
    # Zeitanzeige unterhalb des Fortschrittsbalkens
    cur_min, cur_sec = divmod(int(elapsed), 60)
    tot_min, tot_sec = divmod(int(total), 60)
    time_text = f"{cur_min:02d}:{cur_sec:02d}/{tot_min:02d}:{tot_sec:02d}"
    time_surface = font.render(time_text, True, (0, 215, 0))
    screen.blit(time_surface, ((WIDTH - time_surface.get_width()) // 2, bar_y + bar_height + 2))
    
    # Lautstärkeindikator nur anzeigen, wenn kürzlich die Lautstärke geändert wurde
    if time.time() - last_volume_change_time < VOLUME_DISPLAY_DURATION:
        vol_bar_width = 80
        vol_bar_height = 8
        vol_x = (WIDTH - vol_bar_width) // 2
        vol_y = bar_y + bar_height + 20
        # Rahmen für den Balken
        pygame.draw.rect(screen, (255,255,255), (vol_x, vol_y, vol_bar_width, vol_bar_height), 1 )
        # Füllung entsprechend der aktuellen Lautstärke
        filled_width = int(vol_bar_width * volume)
        filled_width = int(vol_bar_width * volume)  
        pygame.draw.rect(screen, (0,215,0), (vol_x, vol_y, filled_width, vol_bar_height))
        # Optional: Beschriftung "Vol" neben dem Balken
        vol_text_surface = font.render("Vol:", True, (255,255,255))
        screen.blit(vol_text_surface, (vol_x - vol_text_surface.get_width() - 5, vol_y))
    
    
    
    center_x = WIDTH // 2
    prev_icon = pygame.image.load("fast-backward.png").convert_alpha()
    prev_icon = pygame.transform.scale(prev_icon, (14, 14))
    prev_icon = tint_image(prev_icon, (0, 215, 0))
    next_icon = pygame.image.load("fast-forward.png").convert_alpha()
    next_icon = pygame.transform.scale(next_icon, (14, 14))
    next_icon = tint_image(next_icon, (0, 215, 0))

    play_icon = pygame.image.load("play.png").convert_alpha()
    play_icon = pygame.transform.scale(play_icon, (14, 14))
    play_icon = tint_image(play_icon, (0, 215, 0))
    
    pause_icon = pygame.image.load("pause.png").convert_alpha()
    pause_icon = pygame.transform.scale(pause_icon, (14, 14))
    pause_icon = tint_image(pause_icon, (0, 215, 0))
    play_symbol = play_icon if playing else pause_icon

    screen.blit(prev_icon, (center_x - icon_spacing*1.3, icon_y))
    screen.blit(play_symbol, (center_x - 4, icon_y))
    screen.blit(next_icon, (center_x + icon_spacing, icon_y))
    pygame.display.update()

# ============================
# Main Loop & Event Handling
# ============================
while True:
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            lgpio.gpiochip_close(h)
            sys.exit()
        elif event.type == KEYDOWN:
            if state == "main":
                if event.key == K_DOWN:
                    selected_index = (selected_index + 1) % len(audio_files)
                    main_scroll_offset = 0
                elif event.key == K_UP:
                    selected_index = (selected_index - 1) % len(audio_files)
                    main_scroll_offset = 0
                elif event.key in (K_RETURN, K_SPACE):
                    if current_song_index is None or selected_index != current_song_index:
                        play_song(selected_index)
                    else:
                        state = "play"
                elif event.key == K_s and current_song_index is not None:
                    if paused:
                        pygame.mixer.music.unpause()
                        start_time = time.time() - elapsed
                        paused = False
                    else:
                        pygame.mixer.music.pause()
                        paused = True
                elif event.key == K_r and current_song_index is not None:
                    state = "play"
            elif state == "play":
                if event.key == K_r:
                    state = "main"
                elif event.key == K_s:
                    if paused:
                        pygame.mixer.music.unpause()
                        start_time = time.time() - elapsed
                        paused = False
                    else:
                        pygame.mixer.music.pause()
                        paused = True
                elif event.key == K_RIGHT:
                    play_song((current_song_index + 1) % len(audio_files))
                elif event.key == K_LEFT:
                    play_song((current_song_index - 1) % len(audio_files))
                elif event.key == K_UP:
                    volume = min(volume + 0.1, 1.0)
                    pygame.mixer.music.set_volume(volume)
                    last_volume_change_time = time.time()
                elif event.key == K_DOWN:
                    volume = max(volume - 0.1, 0.0)
                    pygame.mixer.music.set_volume(volume)
                    last_volume_change_time = time.time()
    
    # Encoder zur Navigation nutzen
    current_encoder_position = encoder.position
    delta = current_encoder_position - last_encoder_position
    if delta != 0:
        if state == "main":
            selected_index = (selected_index + delta) % len(audio_files)
        elif state == "play":
            volume = max(0.0, min(1.0, volume + (delta * 0.05)))
            pygame.mixer.music.set_volume(volume)
            last_volume_change_time = time.time()
        last_encoder_position = current_encoder_position

    # Button-basierte Steuerung (Seesaw)
    if not select.value:
        if state == "main":
            if current_song_index is None or selected_index != current_song_index:
                play_song(selected_index)
            else:
                state = "play"
    if not left.value and state == "play":
        play_song((current_song_index - 1) % len(audio_files))
    if not right.value and state == "play":
        play_song((current_song_index + 1) % len(audio_files))
    if not up.value and state == "play":
        state = "main"
    elif not up.value and state == "main" and current_song_index is not None:
        state = "play"
    if not down.value and state in ("play", "main"):
        if paused:
            pygame.mixer.music.unpause()
            start_time = time.time() - elapsed
            paused = False
        else:
            pygame.mixer.music.pause()
            paused = True
    
    

    # Menü- und Wiedergabe-Updates
    if state == "main":
        font_main = my_font
        line_height = font_main.get_linesize()
        spacing = 2
        selected_y = 5 + selected_index * (line_height + spacing) - main_menu_scroll_y
        if selected_y < 5:
            main_menu_scroll_y = 5 + selected_index * (line_height + spacing) - 5
        elif selected_y > HEIGHT - line_height - 5:
            main_menu_scroll_y = selected_index * (line_height + spacing) - (HEIGHT - line_height - 5)
        current_surface = font_main.render(os.path.splitext(audio_files[selected_index])[0], True, (255,255,255))
        if current_surface.get_width() > EFFECTIVE_WIDTH:
            now = time.time()
            if now - last_main_scroll_time > 0.1:
                main_scroll_offset = (main_scroll_offset + 2) % current_surface.get_width()
                last_main_scroll_time = now
        else:
            main_scroll_offset = 0
        draw_main_menu(screen, audio_files, selected_index, current_song_index, paused, main_scroll_offset, main_menu_scroll_y)
        if current_song_index is not None:
            elapsed = time.time() - start_time if not paused else pygame.mixer.music.get_pos() / 1000.0
            progress = min(elapsed / song_length, 1.0) if song_length else 0
            if progress >= 1.0:
                play_song((current_song_index + 1) % len(audio_files))
    elif state == "play":
        elapsed = time.time() - start_time if not paused else pygame.mixer.music.get_pos() / 1000.0
        progress = min(elapsed / song_length, 1.0) if song_length else 0

        # Scroll-Offset für Play-Menu kontinuierlich erhöhen
        title_text = os.path.splitext(audio_files[current_song_index])[0]
        title_width = pygame.font.SysFont(None, 16).size(title_text)[0]
        effective_title_width = WIDTH - 20  # 10px Rand links + 10px rechts

        if title_width >= (effective_title_width - 20):  # 20px Puffer
            now = time.time()
            if now - last_play_scroll_time > 0.1:  # Alle 100ms scrollen
                play_scroll_offset += 2
                last_play_scroll_time = now
        else:
            play_scroll_offset = 0  # Reset wenn nicht gescrollt wird

        draw_play_menu(screen, os.path.splitext(audio_files[current_song_index])[0],
                       progress, elapsed, song_length, not paused, play_scroll_offset)
        if progress >= 1.0:
            play_song((current_song_index + 1) % len(audio_files))

    update_hardware_display(screen)
    clock.tick(60)

