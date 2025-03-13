import pygame
import os
import time

class UserInterface:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        pygame.font.init()
        self.font = pygame.font.Font('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)

    VOLUME_DISPLAY_DURATION = 1.0  # Dauer in Sekunden, in der der Indikator sichtbar ist
    last_volume_change_time = 0
    volume = 0.5

    def tint_image(self, image, tint_color):
        tinted_image = image.copy()
        tinted_image.fill((0,0,0,255), special_flags=pygame.BLEND_RGBA_MULT)
        tinted_image.fill(tint_color + (0,), special_flags=pygame.BLEND_RGBA_ADD)
        return tinted_image

    def draw_main_menu(self, screen, files, selected, current_song_index, paused, h_scroll, v_scroll):
        screen.fill((0, 0, 0))
        NORMAL_LEFT_MARGIN = 10
        SELECTED_LEFT_MARGIN = 5
        INDICATOR_SPACE = 5
        RIGHT_MARGIN = 5
        effective_width_normal = self.width - NORMAL_LEFT_MARGIN - RIGHT_MARGIN
        effective_width_selected = self.width  - SELECTED_LEFT_MARGIN - RIGHT_MARGIN
        y = 5 - v_scroll
        spacing = 2
        line_height = self.font.get_linesize()
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
                pygame.draw.rect(screen, (0, 215, 0), (0, y, self.width, line_height + 1))
                text_color = (255, 255, 255)
                left_margin = 5

            text_surface = self.font.render(display_name, True, text_color)

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
                    pygame.draw.rect(screen, indicator_color,
                                     (indicator_x + rect_width + gap, indicator_y, rect_width, rect_height))

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

    def draw_play_menu(self, screen, current_file, progress, elapsed, total, playing, scroll_offset, volume, last_volume_change_time, VOLUME_DISPLAY_DURATION ):
        screen.fill((0, 0, 0))
        font = pygame.font.SysFont(None, 16)
        icon_y = self.height - 40
        icon_spacing = 25
        title_left_margin = 10
        title_right_margin = 10
        title_y = 10
        effective_title_width = self.width - title_left_margin - title_right_margin
        scroll_text = os.path.splitext(current_file)[0] + "   "
        title_surface = font.render(scroll_text, True, (0, 215, 0))
        title_width = title_surface.get_width()
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
            x = title_left_margin + (effective_title_width - title_width) // 2
            screen.blit(title_surface, (x, title_y))
        # Fortschrittsbalken
        bar_y = 25
        bar_height = 10
        pygame.draw.rect(screen, (50, 50, 50), (5, bar_y, self.width - 10, bar_height))
        prog_width = int((self.width - 10) * progress)
        pygame.draw.rect(screen, (0, 215, 0), (5, bar_y, prog_width, bar_height))

        # Zeitanzeige unterhalb des Fortschrittsbalkens
        cur_min, cur_sec = divmod(int(elapsed), 60)
        tot_min, tot_sec = divmod(int(total), 60)
        time_text = f"{cur_min:02d}:{cur_sec:02d}/{tot_min:02d}:{tot_sec:02d}"
        time_surface = font.render(time_text, True, (0, 215, 0))
        screen.blit(time_surface, ((self.width - time_surface.get_width()) // 2, bar_y + bar_height + 2))

        cur_min, cur_sec = divmod(int(elapsed), 60)
        tot_min, tot_sec = divmod(int(total), 60)
        time_text = f"{cur_min:02d}:{cur_sec:02d}/{tot_min:02d}:{tot_sec:02d}"
        time_surface = font.render(time_text, True, (0, 215, 0))
        screen.blit(time_surface, ((self.width - time_surface.get_width()) // 2, bar_y + bar_height + 2))

        # Lautstärkeindikator nur anzeigen, wenn kürzlich die Lautstärke geändert wurde
        if time.time() - last_volume_change_time < VOLUME_DISPLAY_DURATION:
            vol_bar_width = 80
            vol_bar_height = 8
            vol_x = (self.width - vol_bar_width) // 2
            vol_y = bar_y + bar_height + 20
            # Rahmen für den Balken
            pygame.draw.rect(screen, (255, 255, 255), (vol_x, vol_y, vol_bar_width, vol_bar_height), 1)
            # Füllung entsprechend der aktuellen Lautstärke
            filled_width = int(vol_bar_width * volume)
            pygame.draw.rect(screen, (0, 215, 0), (vol_x, vol_y, filled_width, vol_bar_height))
            # Optional: Beschriftung "Vol" neben dem Balken
            vol_text_surface = font.render("Vol:", True, (255, 255, 255))
            screen.blit(vol_text_surface, (vol_x - vol_text_surface.get_width() - 5, vol_y))

        center_x = self.width // 2
        prev_icon = pygame.image.load("assets/fast-backward.png").convert_alpha()
        prev_icon = pygame.transform.scale(prev_icon, (14, 14))
        prev_icon = self.tint_image(prev_icon, (0, 215, 0))
        next_icon = pygame.image.load("assets/fast-forward.png").convert_alpha()
        next_icon = pygame.transform.scale(next_icon, (14, 14))
        next_icon = self.tint_image(next_icon, (0, 215, 0))

        play_icon = pygame.image.load("assets/play.png").convert_alpha()
        play_icon = pygame.transform.scale(play_icon, (14, 14))
        play_icon = self.tint_image(play_icon, (0, 215, 0))

        pause_icon = pygame.image.load("assets/pause.png").convert_alpha()
        pause_icon = pygame.transform.scale(pause_icon, (14, 14))
        pause_icon = self.tint_image(pause_icon, (0, 215, 0))
        play_symbol = play_icon if playing else pause_icon

        screen.blit(prev_icon, (center_x - icon_spacing * 1.3, icon_y))
        screen.blit(play_symbol, (center_x - 4, icon_y))
        screen.blit(next_icon, (center_x + icon_spacing, icon_y))
        pygame.display.update()

