import os
import subprocess
import re
import time
import datetime
import sys
import platform
from pathlib import Path

def resource_path(relative_path):
    """Get absolute path, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Detect OS and locate ffmpeg
so = platform.system()
if getattr(sys, "frozen", False):
    ffmpeg_path = resource_path("ffmpeg.exe" if so == "Windows" else "ffmpeg")
else:
    ffmpeg_path = "ffmpeg.exe" if so == "Windows" else "ffmpeg"

def parse_duration(line):
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line)
    if not m: return 0
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h*3600 + mi*60 + s

def get_video_duration(path):
    """Invoke ffmpeg to read duration."""
    proc = subprocess.Popen(
        [ffmpeg_path, "-i", str(path)],
        stderr=subprocess.PIPE,
        text=True,
        universal_newlines=True
    )
    for line in proc.stderr:
        if "Duration:" in line:
            return parse_duration(line)
    return 0

def is_stable(path, wait=2):
    """True if file size stable after wait seconds."""
    try:
        s1 = os.path.getsize(path)
        time.sleep(wait)
        s2 = os.path.getsize(path)
        return s1 == s2
    except OSError:
        return False

def process_file(fname, input_dir, output_dir):
    inp = input_dir / fname
    # validate name format
    parts = fname.split("_")
    if len(parts) < 4 or len(parts[1]) != 8:
        print(f"⚠ Invalid filename: {fname}")
        return False

    # build base name
    today = datetime.date.today().strftime("%Y%m%d")
    resto = "_".join(parts[2:])
    base = f"VID_{today}_{resto}".rsplit(".", 1)[0]
    unique_comment = f"procesado_{int(time.time())}"

    duration = get_video_duration(inp)
    if duration <= 0:
        print(f"❌ Could not read duration for {fname}")
        return False

    quarter = duration / 4

    # Step 1: process first quarter with minimal brightness filter
    part1 = output_dir / f"{base}_p1.mp4"
    cmd1 = [
        ffmpeg_path, "-i", str(inp),
        "-vf", "eq=brightness=0.001",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35", "-tune", "zerolatency",
        "-t", str(quarter),
        "-c:a", "copy",
        "-y", str(part1)
    ]
    subprocess.run(cmd1, check=True)

    # Step 2: copy remaining 3/4 without re-encoding
    part2 = output_dir / f"{base}_p2.mp4"
    cmd2 = [
        ffmpeg_path,
        "-ss", str(quarter), "-i", str(inp),
        "-c", "copy",
        "-y", str(part2)
    ]
    subprocess.run(cmd2, check=True)

    # Step 3: concatenate parts
    list_file = output_dir / f"{base}_list.txt"
    with open(list_file, "w") as f:
        f.write(f"file '{part1.name}'\nfile '{part2.name}'\n")
    concat = output_dir / f"{base}_concat.mp4"
    cmd3 = [
        ffmpeg_path,
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-y", str(concat)
    ]
    subprocess.run(cmd3, check=True)

    # Step 4: inject metadata and rename to .insv
    temp_meta = output_dir / f"{base}_meta.mp4"
    cmd4 = [
        ffmpeg_path, "-i", str(concat),
        "-map_metadata", "-1",
        "-metadata", f"title={base}",
        "-metadata", f"comment={unique_comment}",
        "-c", "copy",
        "-y", str(temp_meta)
    ]
    subprocess.run(cmd4, check=True)

    final = output_dir / f"{base}.insv"
    os.replace(temp_meta, final)

    # clean up intermediates
    for p in (part1, part2, concat, list_file):
        try: p.unlink()
        except: pass

    return True

def main():
    input_dirs = [Path("a"), Path("b")]
    output_dirs = [Path("outputa"), Path("outputb")]
    for out in output_dirs:
        out.mkdir(exist_ok=True)

    start = time.time()
    total, done = 0, 0

    for inp, out in zip(input_dirs, output_dirs):
        files = [f for f in os.listdir(inp) if f.lower().endswith(".insv")]
        total += len(files)
        for fname in files:
            if not is_stable(inp / fname, wait=2):
                print(f"⚠ Skipping unstable file: {fname}")
                continue
            print(f"Processing {fname} → {out.name}")
            if process_file(fname, inp, out):
                done += 1
                print(f"✅ Done: {fname}")
            else:
                print(f"❌ Failed: {fname}")

    elapsed = time.time() - start
    print(f"\nSummary: {done}/{total} succeeded")
    print(f"Total time: {str(datetime.timedelta(seconds=int(elapsed)))}")

if __name__ == "__main__":
    main()
    input("\nPress Enter to exit… 😘")
