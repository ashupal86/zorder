import wave
import struct
import os

# Create a silent WAV file
def create_silent_wav(filename, duration_ms=100):
    """Creates a silent WAV file of specified duration."""
    # Parameters
    sample_rate = 44100  # samples per second
    duration_samples = int(duration_ms * sample_rate / 1000)
    
    # Create silent data (all zeros)
    data = struct.pack('<' + ('h' * duration_samples), *([0] * duration_samples))
    
    # Create and write WAV file
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(data)
        
    print(f"Created silent WAV file: {filename}")

# Create silent WAV file
sounds_dir = "static/sounds"
os.makedirs(sounds_dir, exist_ok=True)

silent_wav = os.path.join(sounds_dir, "silent.wav")
create_silent_wav(silent_wav)

# Convert to MP3 if FFMPEG is available
try:
    mp3_output = os.path.join(sounds_dir, "silent.mp3")
    import subprocess
    cmd = ["ffmpeg", "-y", "-i", silent_wav, "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_output]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Converted to MP3: {mp3_output}")
    os.remove(silent_wav)  # Remove the WAV file
except Exception as e:
    print(f"Could not convert to MP3 (you may need to install ffmpeg): {e}")
    print("Using WAV file instead. Please rename it to silent.mp3 if needed.") 