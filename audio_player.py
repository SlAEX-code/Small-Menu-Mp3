import os
import time
import vlc
import wave

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

class AudioPlayer:
    def __init__(self, folder):
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.folder = folder
        self.audio_files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp3', '.wav'))]
        if not self.audio_files:
            raise FileNotFoundError("Keine Audio-Dateien gefunden!")
        self.current_index = 0
        self.song_length = 0
        self.start_time = None
        self.paused = False

    def get_audio_length(self, path):
        if path.lower().endswith('.mp3') and MP3:
            return MP3(path).info.length
        elif path.lower().endswith('.wav'):
            with wave.open(path, 'r') as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        else:
            return 180.0

    def play_song(self, index, auto_mode=False):
        self.current_index = index % len(self.audio_files)
        current_file = self.audio_files[self.current_index]
        song_path = os.path.join(self.folder, current_file)
        media = self.vlc_instance.media_new(song_path)
        self.player.set_media(media)
        self.player.play()
        time.sleep(0.2)  # Kurze Wartezeit, damit VLC die Mediendaten laden kann
        self.song_length = self.get_audio_length(song_path)
        self.start_time = time.time()
        self.paused = False
        return current_file

    def pause(self):
        self.player.pause()
        self.paused = not self.paused

    def set_volume(self, volume):
        # volume als Wert zwischen 0 und 1
        self.player.audio_set_volume(int(volume * 100))

    def get_current_time(self):
        return self.player.get_time() / 1000.0

    def next_song(self):
        return self.play_song((self.current_index + 1) % len(self.audio_files))

    def previous_song(self):
        return self.play_song((self.current_index - 1) % len(self.audio_files))

