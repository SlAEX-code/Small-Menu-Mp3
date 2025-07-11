import os
import time
import vlc
import wave

try:
    from mutagen.mp3 import MP3
    from mutagen.wave import WAVE
    from mutagen.flac import FLAC
except ImportError:
    MP3 = None
    WAVE = None
    FLAC = None

class AudioPlayer:
    def __init__(self, folder):
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.folder = folder
        self.audio_files = sorted([f for f in os.listdir(folder) if f.lower().endswith(('.mp3', '.wav', 'flac'))])
        if not self.audio_files:
            raise FileNotFoundError("Keine Audio-Dateien gefunden!")

        # Platzhalter für Metadaten - für "Interpret" und "Album"
        self.metadata = []
        # self._load_metadata() # Diese Funktion kann später implementiert werden

        self.current_index = 0
        self.song_length = 0
        self.start_time = None
        self.paused = False

    def get_audio_length(self, path):
        try:
			# Hinzufügen der Längenabfrage für FLAC-Dateien
            if path.lower().endswith('.flac') and FLAC:
                return FLAC(path).info.length
            if path.lower().endswith('.mp3') and MP3:
                return MP3(path).info.length
            elif path.lower().endswith('.wav') and WAVE:
                return WAVE(path).info.length
        except Exception:
            return 180.0 # Fallback
        return 180.0

    def play_song(self, index):
        self.current_index = index % len(self.audio_files)
        current_file = self.audio_files[self.current_index]
        song_path = os.path.join(self.folder, current_file)
        media = self.vlc_instance.media_new(song_path)
        self.player.set_media(media)
        self.player.play()
        time.sleep(0.2)
        self.song_length = self.get_audio_length(song_path)
        self.start_time = time.time()
        self.paused = False
        return self.current_index

    def pause(self):
        self.player.pause()
        self.paused = not self.paused
        if self.paused:
            self.paused_time = self.player.get_time()
        else:
            # Kleine Korrektur, falls die Zeit beim Fortsetzen nicht perfekt ist
            self.player.set_time(int(self.paused_time))

    def set_volume(self, volume):
        self.player.audio_set_volume(int(volume * 100))

    def get_current_time(self):
        return self.player.get_time() / 1000.0

    def next_song(self):
        return self.play_song((self.current_index + 1) % len(self.audio_files))

    def previous_song(self):
        return self.play_song((self.current_index - 1) % len(self.audio_files))
        
    def is_finished(self):
        # vlc.State.Ended hat den Wert 6
        return self.player.get_state() == vlc.State.Ended

    # --- ZUKüNFTIGE FUNKTION für Interpret/Album ---
    # def _load_metadata(self):
    #     for file in self.audio_files:
    #         # Lade hier Metadaten mit mutagen und speichere sie
    #         pass
