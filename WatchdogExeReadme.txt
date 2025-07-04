# GPU Lightmass Watchdog

Watchdog automates crash isolation for Unreal Engine's GPU Lightmass by controlling the editor, executing tests, and detecting problematic assets through logging and CPU behavior.

## 🔧 Setup

1. Run `Watchdog.exe`
2. Fill in:
   - Unreal Editor EXE
   - Project `.uproject` path
   - Map to open
3. Pick:
   - Lightmass "Build" button location
   - Console area click location

## 🧪 What It Does

- Launches Unreal Editor
- Executes `auto_runner.py` to test actor chunks
- Watches log and CPU activity to detect freezes/crashes
- Isolates crashing actors automatically

##⚠️ Warning

Only use this tool with:
- Git or Perforce version control
- A full backup of your project

The tool will **delete and reload actors** inside your map!

## ✅ Output

You will find:
- `crashing_actors_list.txt`
- `crash_isolation_state.json`
in your project's `Saved/GPUCrashFinder` directory.

## 🛑 Resetting Progress

Use the **Reset Isolation Progress** button to restart chunk isolation.

## License

MIT License (Free to use, no warranty)
