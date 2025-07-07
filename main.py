import os
import sys
import time
import pygame
from pygame.locals import *

from audio_player import AudioPlayer
from display_controller import DisplayController
from seesaw_input import SeesawInput
from user_interface import UserInterface

# Konstanten
WIDTH, HEIGHT = 160, 128
DC_PIN = 24
RESET_PIN = 25
mp3_folder = "mp3_files"

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Music Player")

# Komponenten initialisieren
audio_player = AudioPlayer(mp3_folder)
display_controller = DisplayController(WIDTH, HEIGHT, DC_PIN, RESET_PIN)
seesaw_input = SeesawInput()
ui = UserInterface(WIDTH, HEIGHT)

# --- ZUSTANDSVERWALTUNG ---
state = "main_menu"
selected_index = 0
main_menu_options = ["Musik", "Einstellungen"]
music_menu_options = ["Alle Songs", "Interpret", "Album"]
settings_menu_options = ["Grün", "Purple", "White"]

current_song_index = None
paused = False
clock = pygame.time.Clock()

# Scroll-Variablen
play_scroll_offset = 0
last_play_scroll_time = time.time()
main_scroll_offset = 0
last_main_scroll_time = time.time()
main_menu_scroll_y = 0

volume = 0.5
audio_player.set_volume(volume)

VOLUME_DISPLAY_DURATION = 1.0
last_volume_change_time = time.time()

# Hauptloop
while True:
    # --- Tastatur-Events (für Debugging am PC) ---
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == KEYDOWN:
            # Globale "Zurück"-Taste
            if event.key == K_r:
                if state == "play":
                    state = "all_songs_menu"
                elif state == "all_songs_menu":
                    state = "music_menu"
                    selected_index = 0 # Setzt den Fokus zurück auf "Alle Songs"
                elif state in ["music_menu", "settings_menu"]:
                    state = "main_menu"
                    selected_index = 0

    # --- KORRIGIERTE ENCODER- UND TASTENSTEUERUNG ---

    # 1. Encoder-Drehung (Navigation)
    delta = seesaw_input.get_encoder_delta()
    if delta != 0:
        if state == "main_menu":
            selected_index = (selected_index + delta) % len(main_menu_options)
        elif state == "music_menu":
            selected_index = (selected_index + delta) % len(music_menu_options)
        elif state == "settings_menu":
            selected_index = (selected_index + delta) % len(settings_menu_options)
        elif state == "all_songs_menu":
            selected_index = (selected_index + delta) % len(audio_player.audio_files)
            main_scroll_offset = 0
        elif state == "play":
            volume = max(0.0, min(1.0, volume + (delta * 0.05)))
            audio_player.set_volume(volume)
            last_volume_change_time = time.time()
            
    # 2. Select-Taste (Auswählen)
    if seesaw_input.is_select_pressed():
        time.sleep(0.2) # Einfaches Debouncing, um doppelte Eingaben zu verhindern
        if state == "main_menu":
            if selected_index == 0: # Musik
                state = "music_menu"
                selected_index = 0
            elif selected_index == 1: # Einstellungen
                state = "settings_menu"
                selected_index = 0
        elif state == "music_menu":
            if selected_index == 0: # Alle Songs
                state = "all_songs_menu"
                selected_index = 0
            # Platzhalter für Interpret/Album - hier passiert noch nichts
        elif state == "settings_menu":
            ui.set_theme(selected_index)
        elif state == "all_songs_menu":
            if current_song_index == selected_index:
                state = "play"
            else:
                current_song_index = selected_index
                audio_player.play_song(selected_index)
                paused = False
                state = "play"
        elif state == "play": # Drücken im Play-Screen pausiert/spielt
            audio_player.pause()
            paused = not paused

    # 3. Up-Taste (Zurück)
    if seesaw_input.is_up_pressed():
        time.sleep(0.2)
        if state == "play":
            state = "all_songs_menu"
        elif state == "all_songs_menu":
            state = "music_menu"
            selected_index = 0
        elif state in ["music_menu", "settings_menu"]:
            state = "main_menu"
            selected_index = 0

    # 4. Down-Taste (Pause/Play)
    if seesaw_input.is_down_pressed():
        time.sleep(0.2)
        if state == "play" or (state == "all_songs_menu" and current_song_index is not None):
            audio_player.pause()
            paused = not paused

    # 5. Links/Rechts-Tasten (Nächster/Vorheriger Song)
    if state == "play":
        if seesaw_input.is_left_pressed():
            time.sleep(0.2)
            current_song_index = audio_player.previous_song()
        if seesaw_input.is_right_pressed():
            time.sleep(0.2)
            current_song_index = audio_player.next_song()
            
    # --- UI-Updates basierend auf dem Zustand ---
    if state == "main_menu":
        if audio_player.is_finished():
            current_song_index = audio_player.next_song()
            paused = False
        ui.draw_generic_menu(screen, main_menu_options, selected_index, "Hauptmenü")
    elif state == "music_menu":
        if audio_player.is_finished():
            current_song_index = audio_player.next_song()
            paused = False
        ui.draw_generic_menu(screen, music_menu_options, selected_index, "Musik")
    elif state == "settings_menu":
        if audio_player.is_finished():
            current_song_index = audio_player.next_song()
            paused = False
        ui.draw_generic_menu(screen, settings_menu_options, selected_index, "Einstellungen")
    elif state == "all_songs_menu":
        if audio_player.is_finished():
            current_song_index = audio_player.next_song()
            paused = False
        # Hier die Logik für das Scrollen beibehalten
        line_height = ui.font.get_linesize() + 2
        selected_y_on_screen = 5 + selected_index * line_height - main_menu_scroll_y
        if selected_y_on_screen + line_height > HEIGHT:
            main_menu_scroll_y = (selected_index + 1) * line_height - HEIGHT + 5
        if selected_y_on_screen < 5:
            main_menu_scroll_y = selected_index * line_height
            
        # Horizontalen Scroll-Offset für lange Titel berechnen
        text_width = ui.font.size(os.path.splitext(audio_player.audio_files[selected_index])[0])[0]
        if text_width > WIDTH - 30:
            now = time.time()
            if now - last_main_scroll_time > 0.1:
                main_scroll_offset = (main_scroll_offset + 2)
                last_main_scroll_time = now
        else:
            main_scroll_offset = 0
        
        ui.draw_all_songs_menu(screen, audio_player.audio_files, selected_index, current_song_index, paused, main_scroll_offset, main_menu_scroll_y)
        
    elif state == "play":
        if audio_player.is_finished():
            current_song_index = audio_player.next_song()
            paused = False
        
        # Zeit immer vom Player holen
        elapsed = audio_player.get_current_time()
        progress = (elapsed / audio_player.song_length) if audio_player.song_length > 0 else 0
        
        if progress >= 1.0 and audio_player.song_length > 0:
            current_song_index = audio_player.next_song()
            paused = False

        # BUGFIX 3: Horizontalen Scroll-Offset für Play-Screen
        title_text = os.path.splitext(audio_player.audio_files[current_song_index])[0]
        title_width = pygame.font.SysFont(None, 18).size(title_text)[0]
        if title_width > WIDTH - 20:
             now = time.time()
             if now - last_play_scroll_time > 0.1:
                 play_scroll_offset = (play_scroll_offset + 2)
                 last_play_scroll_time = now
        else:
            play_scroll_offset = 0
            
        ui.draw_play_menu(screen, title_text, progress, elapsed, audio_player.song_length, not paused, play_scroll_offset, volume, last_volume_change_time, VOLUME_DISPLAY_DURATION)



    display_controller.update_display(screen)
    clock.tick(30)
