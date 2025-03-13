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
pygame.display.set_caption("MP3/WAV Player")

# Komponenten initialisieren
audio_player = AudioPlayer(mp3_folder)
display_controller = DisplayController(WIDTH, HEIGHT, DC_PIN, RESET_PIN)
seesaw_input = SeesawInput()
ui = UserInterface(WIDTH, HEIGHT)

state = "main"  # "main" = Hauptmenü, "play" = Wiedergabe
selected_index = 0
current_song_index = None
paused = False
clock = pygame.time.Clock()

# Scroll-Variablen
play_scroll_offset = 0
last_play_scroll_time = time.time()
main_scroll_offset = 0
last_main_scroll_time = time.time()
LEFT_MARGIN = 10
RIGHT_MARGIN = 5
EFFECTIVE_WIDTH = WIDTH - LEFT_MARGIN - RIGHT_MARGIN
main_menu_scroll_y = 0

volume = 0.5
audio_player.set_volume(volume)

VOLUME_DISPLAY_DURATION = 1.0
last_volume_change_time = time.time()

# Hauptloop
while True:
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == KEYDOWN:
            if state == "main":
                if event.key == K_DOWN:
                    selected_index = (selected_index + 1) % len(audio_player.audio_files)
                    main_scroll_offset = 0
                elif event.key == K_UP:
                    selected_index = (selected_index - 1) % len(audio_player.audio_files)
                    main_scroll_offset = 0
                elif event.key in (K_RETURN, K_SPACE):
                    if current_song_index is None or selected_index != current_song_index:
                        current_song_index = selected_index
                        audio_player.play_song(selected_index)
                        state = "play"
                    else:
                        state = "play"
                elif event.key == K_s and current_song_index is not None:
                    audio_player.pause()
                    paused = not paused
                    if not paused:
                        audio_player.start_time = time.time() - audio_player.get_current_time()
                elif event.key == K_r and current_song_index is not None:
                    state = "play"
            elif state == "play":
                if event.key == K_r:
                    state = "main"
                elif event.key == K_s:
                    audio_player.pause()
                    paused = not paused
                    if not paused:
                        audio_player.start_time = time.time() - audio_player.get_current_time()
                elif event.key == K_RIGHT:
                    audio_player.next_song()
                    current_song_index = audio_player.current_index
                elif event.key == K_LEFT:
                    audio_player.previous_song()
                    current_song_index = audio_player.current_index
                elif event.key == K_UP:
                    volume = min(volume + 0.1, 1.0)
                    audio_player.set_volume(volume)
                    last_volume_change_time = time.time()
                elif event.key == K_DOWN:
                    volume = max(volume - 0.1, 0.0)
                    audio_player.set_volume(volume)
                    last_volume_change_time = time.time()

    # Encoder-Eingaben
    delta = seesaw_input.get_encoder_delta()
    if delta != 0:
        if state == "main":
            selected_index = (selected_index + delta) % len(audio_player.audio_files)
        elif state == "play":
            volume = max(0.0, min(1.0, volume + (delta * 0.05)))
            audio_player.set_volume(volume)
            last_volume_change_time = time.time()

    # Seesaw-Tastenabfragen
    if seesaw_input.is_select_pressed():
        if state == "main":
            if current_song_index is None or selected_index != current_song_index:
                current_song_index = selected_index
                audio_player.play_song(selected_index)
                state = "play"
            else:
                state = "play"
    if seesaw_input.is_left_pressed() and state == "play":
        audio_player.previous_song()
        current_song_index = audio_player.current_index
    if seesaw_input.is_right_pressed() and state == "play":
        audio_player.next_song()
        current_song_index = audio_player.current_index
    if seesaw_input.is_up_pressed():
        if state == "play":
            state = "main"
        elif state == "main" and current_song_index is not None:
            state = "play"
    if seesaw_input.is_down_pressed():
        audio_player.pause()
        paused = not paused

    # UI-Updates
    if state == "main":
        font_main = ui.font
        line_height = font_main.get_linesize()
        spacing = 2
        selected_y = 5 + selected_index * (line_height + spacing) - main_menu_scroll_y
        if selected_y < 5:
            main_menu_scroll_y = 5 + selected_index * (line_height + spacing) - 5
        elif selected_y > HEIGHT - line_height - 5:
            main_menu_scroll_y = selected_index * (line_height + spacing) - (HEIGHT - line_height - 5)
        current_surface = font_main.render(os.path.splitext(audio_player.audio_files[selected_index])[0], True, (255,255,255))
        if current_surface.get_width() > EFFECTIVE_WIDTH:
            now = time.time()
            if now - last_main_scroll_time > 0.1:
                main_scroll_offset = (main_scroll_offset + 2) % current_surface.get_width()
                last_main_scroll_time = now
        else:
            main_scroll_offset = 0
        ui.draw_main_menu(screen, audio_player.audio_files, selected_index, current_song_index, paused, main_scroll_offset, main_menu_scroll_y)
        if current_song_index is not None:
            elapsed = time.time() - audio_player.start_time if not paused else audio_player.get_current_time()
            progress = min(elapsed / audio_player.song_length, 1.0) if audio_player.song_length else 0
            if progress >= 1.0:
                audio_player.next_song()
                current_song_index = audio_player.current_index
    elif state == "play":
        elapsed = time.time() - audio_player.start_time if not paused else audio_player.get_current_time()
        progress = min(elapsed / audio_player.song_length, 1.0) if audio_player.song_length else 0
        title_text = os.path.splitext(audio_player.audio_files[current_song_index])[0]
        title_width = pygame.font.SysFont(None, 16).size(title_text)[0]
        effective_title_width = WIDTH - 20
        if title_width >= (effective_title_width - 20):
            now = time.time()
            if now - last_play_scroll_time > 0.1:
                play_scroll_offset += 2
                last_play_scroll_time = now
        else:
            play_scroll_offset = 0
        ui.draw_play_menu(screen, os.path.splitext(audio_player.audio_files[current_song_index])[0],
                          progress, elapsed, audio_player.song_length, not paused, play_scroll_offset, volume, last_volume_change_time, VOLUME_DISPLAY_DURATION)
        if progress >= 1.0:
            audio_player.next_song()
            current_song_index = audio_player.current_index

    display_controller.update_display(screen)
    clock.tick(60)

