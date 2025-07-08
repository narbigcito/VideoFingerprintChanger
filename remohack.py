import os
import subprocess
import re
from pathlib import Path
from tqdm import tqdm
import time
import datetime
import sys
import platform
import concurrent.futures
import psutil  # Asegúrate de tener instalado con: pip install psutil

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

so = platform.system()
if getattr(sys, 'frozen', False):
    if so == "Windows":
        ffmpeg_path = resource_path("ffmpeg.exe")
    else:
        ffmpeg_path = resource_path("ffmpeg")
else:
    if so == "Windows":
        ffmpeg_path = "ffmpeg.exe"
    else:
        ffmpeg_path = "ffmpeg"

def parse_ffmpeg_duration(line):
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h*3600 + mi*60 + s
    return 0

def parse_ffmpeg_progress(line):
    m = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h*3600 + mi*60 + s
    return 0

def is_stable(path, wait=2):
    try:
        s1 = os.path.getsize(path)
        time.sleep(wait)
        s2 = os.path.getsize(path)
        return s1 == s2
    except OSError:
        return False

def process_file(filename, input_dir, output_dir, pbar=None):
    inp = os.path.join(input_dir, filename)
    parts = filename.split('_')
    if len(parts) < 4 or len(parts[1]) != 8:
        print(f"⚠ Nombre inválido: {filename}")
        return False

    today = datetime.date.today().strftime("%Y%m%d")
    resto = "_".join(parts[2:])
    base = f"VID_{today}_{resto}".rsplit('.',1)[0]
    temp = os.path.join(output_dir, f"{base}.mp4")
    final = os.path.join(output_dir, f"{base}.insv")
    unique_comment = f"procesado_{int(time.time())}"

    cmd = [
        ffmpeg_path,
        "-i", inp,
        "-map_metadata", "-1",
        "-metadata", f"title={base}",
        "-metadata", f"comment={unique_comment}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "30",
        "-threads", "2",  # Limita a 2 hilos para no saturar CPU
        "-c:a", "copy",
        "-y", temp
    ]

    try:
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
        
        # Baja la prioridad del proceso para que la compu no se bloquee
        p = psutil.Process(proc.pid)
        if so == "Windows":
            p.nice(psutil.IDLE_PRIORITY_CLASS)  # Prioridad baja en Windows
        else:
            p.nice(19)  # Prioridad baja en Linux/macOS

        dur = cur = 0
        ffmpeg_log = ""
        while True:
            line = proc.stderr.readline()
            if not line: break
            ffmpeg_log += line
            if "Duration:" in line:
                dur = parse_ffmpeg_duration(line)
                print(f" Duración: {dur:.2f}s", end='\r')
            elif "time=" in line:
                cur = parse_ffmpeg_progress(line)
                if dur > 0:
                    pct = (cur/dur)*100
                    print(f" Progreso: {pct:.1f}% ({cur:.1f}s/{dur:.1f}s)", end='\r')
            if pbar and dur > 0 and cur > 0:
                pbar.n = min(cur, dur)
                pbar.refresh()
        proc.wait()

        while True:
            line = proc.stderr.readline()
            if not line:
                break
            ffmpeg_log += line

        if proc.returncode == 0:
            os.rename(temp, final)
            now = time.time()
            os.utime(final, (now, now))
            try:
                with open(final, "ab") as f:
                    f.write(os.urandom(16))
            except:
                pass
            return True
        else:
            print(f"\n❌ Error FFmpeg en {filename}")
            print("---- LOG FFmpeg ----")
            print(ffmpeg_log)
            print("---------------------")
            return False
    except Exception as e:
        print(f"\n❌ Error crítico en {filename}: {e}")
        return False

def process_file_wrapper(args):
    filename, input_dir, output_dir = args
    return filename, process_file(filename, input_dir, output_dir)

def process_directory(input_dir, output_dir, max_workers=None):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".insv")]
    total = len(files)
    if total == 0:
        print(f"⚠ No hay .insv en '{input_dir}'")
        return 0, 0
    success = 0
    print(f"\n=== Procesando carpeta '{input_dir}' ({total} archivos) ===")

    stable_files = []
    for f in files:
        full = os.path.join(input_dir, f)
        if is_stable(full, wait=2):
            stable_files.append(f)
        else:
            print(f"⚠ '{f}' no está estable, se omite")

    total_stable = len(stable_files)
    print(f"Archivos estables para procesar: {total_stable}")

    args_list = [(f, input_dir, output_dir) for f in stable_files]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file_wrapper, arg): arg[0] for arg in args_list}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            fname = futures[future]
            print(f"\n[{i}/{total_stable}] {fname}")
            try:
                _, result = future.result()
                if result:
                    success += 1
                    print(f"✅ Completado: {fname}")
                else:
                    print(f"❌ Falló: {fname}")
            except Exception as e:
                print(f"❌ Error crítico en {fname}: {e}")

    return success, total_stable

def main():
    start_time = time.time()

    pairs = [("a", "outputa"), ("b", "outputb")]
    overall_ok = overall_tot = 0
    for inp, outp in pairs:
        ok, tot = process_directory(inp, outp, max_workers=2)  # Ajusta hilos aquí
        overall_ok += ok
        overall_tot += tot

    elapsed = time.time() - start_time
    formatted = str(datetime.timedelta(seconds=int(elapsed)))

    print(f"\n=== Resumen total: {overall_ok}/{overall_tot} exitosos ===")
    print(f"Tiempo total de procesamiento: {formatted} ⏳")

if __name__ == "__main__":
    main()
    input("\nPresiona Enter para salir... 😘")
