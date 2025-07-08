# Remohack

Remohack is a cross-platform Python tool that subtly modifies `.insv` video files to bypass protection software while preserving video quality.

## Features

- Automatic OS detection (Windows, macOS, Linux)
- Batch processing of videos in folders `a` and `b`
- Efficient multi-threaded execution
- Minimal video re-encoding with metadata injection
- Outputs processed videos to `outputa` and `outputb`

## Requirements

- Python 3.x
- [FFmpeg](https://ffmpeg.org/) installed and accessible in PATH (bundled in Windows builds)
- Python packages: `tqdm`, `psutil`

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your_username/your_repo.git
   cd your_repo

Usage
Place your .insv video files inside the folders a/ or b/

Run the script:

bash
Copy
python remohack.py
Processed videos will appear in outputa/ and outputb/

License
MIT License

Made with ❤️ by Narbicito

yaml
Copy

