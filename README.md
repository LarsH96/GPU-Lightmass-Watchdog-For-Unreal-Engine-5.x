![Watchdog UI Preview](images/watchdog_ui.png)

Click the image to watch the full tutorial on YouTube.
[![Watch the tutorial](https://img.youtube.com/vi/SL1CY5qfMGU/hqdefault.jpg)](https://www.youtube.com/watch?v=SL1CY5qfMGU)


# GPU Lightmass Watchdog

A toolkit for automating and crash-isolating Unreal Engine lightmass builds using chunk isolation and CPU monitoring.

## Features

- Automatically launches Unreal and triggers builds
- Monitors for freezes using CPU usage
- Auto reloads maps and continues testing
- Visual GUI with dark theme and live log
- Fully configurable and open source

## Requirements

- Python 3.8+
- Unreal Engine 4 or 5
- PyInstaller (optional, for building .exe)
- Modules: `tkinter`, `pyautogui`, `psutil`

## Setup

1. Clone the repository
2. Install dependencies:
3. Run `watchdog.py`
4. Configure paths in the GUI

## Build EXE (Optional)

pyinstaller --onefile --windowed --icon=icon.ico --add-data "auto_runner.py;." --add-data "watchdog_config.json;." watchdog.py


## Disclaimer

⚠️ Use with version control (Git, Perforce) or backups only!

## License

[MIT](LICENSE)




