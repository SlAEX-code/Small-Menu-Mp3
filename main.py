import os
import sys
import time
import pygame
from pygame.locals import *

# Pygame und Mixer initialisieren
pygame.init()
pygame.mixer.init()

# Fenstergröße fest auf 128x160
WIDTH, HEIGHT = 160, 128
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MP3 Player")

# Zustandsvariable: "main" = Hauptmenü, "play" = Wiedergabemodus
state = "main"

# Lade MP3-Dateien aus dem Ordner "mp3_files"
mp3_folder = "mp3_files"
mp3_files = [f for f in os.listdir(mp3_folder) if f.lower().endswith('.mp3')]
if not mp3_files:
    print("Keine MP3-Dateien gefunden!")
    sys.exit()

selected_index = 0         # Auswahl im Hauptmenü
current_song_index = None  # Index des aktuell abgespielten Songs
paused = False             # Wiedergabestatus

clock = pygame.time.Clock()

# Versuche, mit mutagen die Songlänge zu ermitteln
try:
    from mutagen.mp3 import MP3
    def get_mp3_length(path):
        audio = MP3(path)
        return audio.info.length
except ImportError:
    def get_mp3_length(path):
        return 180.0  # Fallback: 3 Minuten

start_time = None   # Zeitpunkt, zu dem der Song gestartet wurde
song_length = None  # Länge des Songs (in Sekunden)

# Variablen für das horizontale Scrollen (Titel)
play_scroll_offset = 0
last_play_scroll_time = time.time()
main_scroll_offset = 0
last_main_scroll_time = time.time()

# Konstante für linke und rechte Ränder im Hauptmenü
LEFT_MARGIN = 10
RIGHT_MARGIN = 5  # Reservierte Breite am rechten Rand
# Effektive Breite für Text im Hauptmenü:
EFFECTIVE_WIDTH = WIDTH - LEFT_MARGIN - RIGHT_MARGIN

# Variable für vertikales Scrollen im Hauptmenü
main_menu_scroll_y = 0

# Globale Lautstärke (zwischen 0.0 und 1.0)
volume = 0.5
pygame.mixer.music.set_volume(volume)

def draw_main_menu(screen, files, selected, current_song_index, paused, h_scroll, v_scroll):
    screen.fill((0, 0, 0))
    font = pygame.font.SysFont(None, 16)
    y = 5 - v_scroll  # Vertikaler Offset wird berücksichtigt
    spacing = 2
    for i, filename in enumerate(files):
        # Erzeuge den Basis-Titel
        base_title = os.path.splitext(filename)[0]
        # Nur beim ausgewählten Eintrag fügen wir einen Puffer (Gap) hinzu, damit am Ende eine Lücke entsteht
        if i == selected:
            display_name = base_title + "   "  # Gap hinzufügen
        else:
            display_name = base_title
        # Rest wie gehabt:
        text_color = (0, 0, 255) if (current_song_index is not None and i == current_song_index) else (255, 255, 255)
        line_height = font.get_linesize()
        text_surface = font.render(display_name, True, text_color)
        x = LEFT_MARGIN
        if i == selected:
            pygame.draw.rect(screen, (30, 215, 96), (0, y, WIDTH, line_height))
            if text_surface.get_width() > EFFECTIVE_WIDTH:
                scrolling_surface = pygame.Surface((text_surface.get_width(), line_height))
                scrolling_surface.fill((30, 215, 96))
                scrolling_surface.blit(text_surface, (0, 0))
                effective_offset = h_scroll % text_surface.get_width()
                if effective_offset + EFFECTIVE_WIDTH > text_surface.get_width():
                    part1_width = text_surface.get_width() - effective_offset
                    screen.blit(scrolling_surface, (x, y),
                                area=pygame.Rect(effective_offset, 0, part1_width, line_height))
                    part2_width = EFFECTIVE_WIDTH - part1_width
                    screen.blit(scrolling_surface, (x + part1_width, y),
                                area=pygame.Rect(0, 0, part2_width, line_height))
                else:
                    screen.blit(scrolling_surface, (x, y),
                                area=pygame.Rect(effective_offset, 0, EFFECTIVE_WIDTH, line_height))
            else:
                screen.blit(text_surface, (x, y))
        else:
            if text_surface.get_width() > EFFECTIVE_WIDTH:
                clipped = text_surface.subsurface((0, 0, EFFECTIVE_WIDTH, text_surface.get_height()))
                screen.blit(clipped, (x, y))
            else:
                screen.blit(text_surface, (x, y))
        y += line_height + spacing
    pygame.display.update()

def draw_play_menu(screen, current_file, progress, elapsed, total, playing, scroll_offset):
    screen.fill((0, 0, 0))
    font = pygame.font.SysFont(None, 16)
    # Songtitel oben (0 bis 20 Pixel)
    scroll_text = os.path.splitext(mp3_files[current_song_index])[0] + "   "
    title_surface = font.render(scroll_text, True, (255, 255, 255))
    title_width = title_surface.get_width()
    if title_width > WIDTH:
        scrolling_surface = pygame.Surface((title_width, 20))
        scrolling_surface.fill((0, 0, 0))
        scrolling_surface.blit(title_surface, (0, 0))
        effective_offset = scroll_offset % title_width
        if effective_offset + WIDTH > title_width:
            part1_width = title_width - effective_offset
            screen.blit(scrolling_surface, (0, 0), area=pygame.Rect(effective_offset, 0, part1_width, 20))
            part2_width = WIDTH - part1_width
            screen.blit(scrolling_surface, (part1_width, 0), area=pygame.Rect(0, 0, part2_width, 20))
        else:
            screen.blit(scrolling_surface, (0, 0), area=pygame.Rect(effective_offset, 0, WIDTH, 20))
    else:
        x = (WIDTH - title_width) // 2
        screen.blit(title_surface, (x, 0))
    # Fortschrittsbalken (Bereich: 25 bis 35 Pixel)
    bar_y = 25
    bar_height = 10
    pygame.draw.rect(screen, (50, 50, 50), (5, bar_y, WIDTH - 10, bar_height))
    prog_width = int((WIDTH - 10) * progress)
    pygame.draw.rect(screen, (30, 215, 96), (5, bar_y, prog_width, bar_height))
    # Zeitanzeige (unterhalb des Balkens)
    cur_min, cur_sec = divmod(int(elapsed), 60)
    tot_min, tot_sec = divmod(int(total), 60)
    time_text = f"{cur_min:02d}:{cur_sec:02d}/{tot_min:02d}:{tot_sec:02d}"
    time_surface = font.render(time_text, True, (255, 255, 255))
    screen.blit(time_surface, ((WIDTH - time_surface.get_width()) // 2, bar_y + bar_height + 2))
    # Steuerungssymbole: Prev, Play/Pause, Next
    prev_surface = font.render("<<", True, (255, 255, 255))
    next_surface = font.render(">>", True, (255, 255, 255))
    play_symbol = ">" if playing else "||"
    play_surface = font.render(play_symbol, True, (255, 255, 255))
    screen.blit(prev_surface, (5, HEIGHT - 15))
    screen.blit(play_surface, ((WIDTH - play_surface.get_width()) // 2, HEIGHT - 15))
    screen.blit(next_surface, (WIDTH - next_surface.get_width() - 5, HEIGHT - 15))
    pygame.display.update()

# Globaler Lautstärkewert
volume = 0.5
pygame.mixer.music.set_volume(volume)

# Variable für vertikales Scrollen im Hauptmenü
main_menu_scroll_y = 0

running = True
while running:
    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == KEYDOWN:
            if state == "main":
                if event.key == K_DOWN:
                    selected_index = (selected_index + 1) % len(mp3_files)
                    main_scroll_offset = 0  # Horizontales Scrollen zurücksetzen
                elif event.key == K_UP:
                    selected_index = (selected_index - 1) % len(mp3_files)
                    main_scroll_offset = 0
                elif event.key == K_RETURN:
                    if current_song_index is not None and selected_index == current_song_index:
                        state = "play"
                    else:
                        current_song_index = selected_index
                        current_file = mp3_files[current_song_index]
                        song_path = os.path.join(mp3_folder, current_file)
                        pygame.mixer.music.load(song_path)
                        pygame.mixer.music.play()
                        song_length = get_mp3_length(song_path)
                        start_time = time.time()
                        paused = False
                        state = "play"
                elif event.key == K_s:
                    # Im Hauptmenü: Pause/Fortsetzen falls Song läuft
                    if current_song_index is not None:
                        if paused:
                            pygame.mixer.music.unpause()
                            start_time = time.time() - elapsed
                            paused = False
                        else:
                            pygame.mixer.music.pause()
                            paused = True
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
                    current_song_index = (current_song_index + 1) % len(mp3_files)
                    current_file = mp3_files[current_song_index]
                    song_path = os.path.join(mp3_folder, current_file)
                    pygame.mixer.music.load(song_path)
                    pygame.mixer.music.play()
                    song_length = get_mp3_length(song_path)
                    start_time = time.time()
                    paused = False
                elif event.key == K_LEFT:
                    current_song_index = (current_song_index - 1) % len(mp3_files)
                    current_file = mp3_files[current_song_index]
                    song_path = os.path.join(mp3_folder, current_file)
                    pygame.mixer.music.load(song_path)
                    pygame.mixer.music.play()
                    song_length = get_mp3_length(song_path)
                    start_time = time.time()
                    paused = False
                elif event.key == K_UP:
                    # Lautstärke erhöhen (max. 1.0)
                    volume = min(volume + 0.1, 1.0)
                    pygame.mixer.music.set_volume(volume)
                elif event.key == K_DOWN:
                    # Lautstärke verringern (min. 0.0)
                    volume = max(volume - 0.1, 0.0)
                    pygame.mixer.music.set_volume(volume)

    if state == "main":
        # Berechne vertikalen Scrolloffset so, dass der ausgewählte Eintrag sichtbar ist
        font_main = pygame.font.SysFont(None, 16)
        line_height = font_main.get_linesize()
        spacing = 2
        selected_y = 5 + selected_index * (line_height + spacing) - main_menu_scroll_y
        if selected_y < 5:
            main_menu_scroll_y = 5 + selected_index * (line_height + spacing) - 5
        elif selected_y > HEIGHT - line_height - 5:
            main_menu_scroll_y = selected_index * (line_height + spacing) - (HEIGHT - line_height - 5)
        # Aktualisiere horizontales Scrollen für den ausgewählten Eintrag (falls zu lang)
        font_main = pygame.font.SysFont(None, 16)
        current_item = os.path.splitext(mp3_files[selected_index])[0]
        current_surface = font_main.render(current_item, True, (255,255,255))
        if current_surface.get_width() > EFFECTIVE_WIDTH:
            now = time.time()
            if now - last_main_scroll_time > 0.1:  # schneller scrollen
                main_scroll_offset = (main_scroll_offset + 2) % current_surface.get_width()
                last_main_scroll_time = now
        else:
            main_scroll_offset = 0
        draw_main_menu(screen, mp3_files, selected_index, current_song_index, paused, main_scroll_offset, main_menu_scroll_y)
        if current_song_index is not None:
            if not paused:
                elapsed = time.time() - start_time
            else:
                elapsed = pygame.mixer.music.get_pos() / 1000.0
    elif state == "play":
        if not paused:
            elapsed = time.time() - start_time
        else:
            elapsed = pygame.mixer.music.get_pos() / 1000.0
        progress = min(elapsed / song_length, 1.0) if song_length else 0
        font_play = pygame.font.SysFont(None, 16)
        title_surface = font_play.render(os.path.splitext(mp3_files[current_song_index])[0], True, (255,255,255))
        if title_surface.get_width() > WIDTH:
            now = time.time()
            if now - last_play_scroll_time > 0.1:
                play_scroll_offset = (play_scroll_offset + 2) % title_surface.get_width()
                last_play_scroll_time = now
        else:
            play_scroll_offset = 0
        draw_play_menu(screen, os.path.splitext(mp3_files[current_song_index])[0],
                       progress, elapsed, song_length, not paused, play_scroll_offset)
        if progress >= 1.0:
            current_song_index = (current_song_index + 1) % len(mp3_files)
            current_file = mp3_files[current_song_index]
            song_path = os.path.join(mp3_folder, current_file)
            pygame.mixer.music.load(song_path)
            pygame.mixer.music.play()
            song_length = get_mp3_length(song_path)
            start_time = time.time()
            paused = False

    clock.tick(15)

pygame.quit()
sys.exit()
