import os, sys, json, time, psutil, tkinter as tk, threading, subprocess, pyautogui, shutil
from tkinter import filedialog, scrolledtext

pyautogui.FAILSAFE = False

# ---------- RESOURCE PATH FOR BUNDLED FILES ----------
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
config_path = os.path.join(exe_dir, "watchdog_config.json")
autorunner_bundle_path = resource_path("auto_runner.py")

# ---------- INITIAL CONFIG ----------
default_config = {
    "unreal_path":         "",
    "project_path":        "",
    "map_name":            "",
    "autorunner_path":     os.path.join(exe_dir, "auto_runner.py"),
    "click_pos":           (0, 0),
    "console_pos":         (0, 0),
    "initial_delay":       30,
    "autorunner_delay":    15,
    "post_reload_delay":   5,
    "log_check_interval":  10,
    "cpu_freeze_threshold": 5,
    "max_bake_time_without_freeze": 60
}

# ---------- WRITE EMBEDDED FILES TO LOCAL DIR IF MISSING ----------
if not os.path.exists(config_path):
    try:
        shutil.copy(resource_path("watchdog_config.json"), config_path)
    except Exception:
        pass

if not os.path.exists(default_config["autorunner_path"]):
    try:
        shutil.copy(autorunner_bundle_path, default_config["autorunner_path"])
    except Exception:
        pass

# ---------- LOAD CONFIG ----------
config = default_config.copy()
if os.path.exists(config_path):
    try:
        with open(config_path, "r") as f:
            config.update(json.load(f))
    except Exception:
        pass

config["autorunner_path"] = os.path.join(exe_dir, "auto_runner.py")
def save_cfg(): open(config_path, "w").write(json.dumps(config, indent=2))

# ---------- FLAGS ----------
stop_requested = False
watchdog_running = False

# ---------- UTILITIES ----------

def log(msg, tag=None):
    print(msg)
    log_text.config(state="normal")

    # Insert ABOVE the countdown line, keeping countdown at bottom
    log_text.insert("countdown_mark linestart", msg + "\n", tag)

    log_text.config(state="disabled")
    log_text.see("end")



def countdown(msg: str, secs: int):
    for s in range(secs, 0, -1):
        countdown_msg = f"{msg}… {s}s"

        log_text.config(state="normal")

        # Clear entire line first
        log_text.delete("countdown_mark linestart", "countdown_mark lineend")

        # Insert new countdown text
        log_text.insert("countdown_mark linestart", countdown_msg, "countdown")

        log_text.config(state="disabled")
        log_text.see("end")
        time.sleep(1)

    # Clear countdown after it's done
    log_text.config(state="normal")
    log_text.delete("countdown_mark linestart", "countdown_mark lineend")
    log_text.config(state="disabled")







def to_unreal(path: str) -> str:
    p = path.replace("\\", "/")
    if p.endswith(".umap"):
        p = p[:-5]
    if "/Content/" in p:
        p = "/Game/" + p.split("/Content/")[-1]
    return p if p.startswith("/Game/") else p

def close_crash_reporter():
    for proc in psutil.process_iter():
        if "CrashReportClient" in proc.name():
            log("🛑 Closing CrashReporter …")
            try:
                proc.terminate()
                proc.wait(5)
            except Exception:
                pass

def is_editor_running():
    return any("UnrealEditor" in p.name() for p in psutil.process_iter())

def get_editor_cpu():
    total = 0.0
    cnt = 0
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and "UnrealEditor" in proc.info['name']:
                total += proc.cpu_percent(interval=0.0)
                cnt += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total / cnt if cnt else 0.0

def chunks_finished():
    project_dir = os.path.dirname(config["project_path"])
    path = os.path.join(project_dir, "Saved", "GPUCrashFinder", "crash_isolation_state.json")
    if os.path.exists(path):
        try:
            return bool(json.load(open(path)).get("finished"))
        except Exception:
            return False
    return False

def get_last_crash_status():
    project_dir = os.path.dirname(config["project_path"])
    st = os.path.join(project_dir, "Saved", "GPUCrashFinder", "status.json")
    if os.path.exists(st):
        try:
            return json.load(open(st)).get("crashed", False)
        except Exception:
            return False
    return False

# ---------- EXEC HELPERS ----------
def launch_unreal():
    log("🚀 Launching Unreal …")
    subprocess.Popen([config["unreal_path"], config["project_path"], config["map_name"]])

def exec_runner():
    log("📜 Running autorunner …")
    pyautogui.click(config["console_pos"])
    time.sleep(0.4)
    pyautogui.typewrite(f'exec(open("{config["autorunner_path"].replace("\\", "/")}").read())')
    pyautogui.press("enter")

def click_build():
    log("🖱 Build lighting click")
    pyautogui.moveTo(config["click_pos"], duration=1)
    pyautogui.click()

def log_file():
    log_dir = os.path.join(os.path.dirname(config["project_path"]), "Saved", "Logs")
    return os.path.join(log_dir, os.path.splitext(os.path.basename(config["project_path"]))[0] + ".log")

def write_status(crashed: bool):
    project_dir = os.path.dirname(config["project_path"])
    saved_dir = os.path.join(project_dir, "Saved", "GPUCrashFinder")
    os.makedirs(saved_dir, exist_ok=True)
    st = os.path.join(saved_dir, "status.json")
    json.dump({"crashed": crashed}, open(st, "w"))
    log("📝  Status written → " + st)

# ---------- MONITOR ----------
def bake_cycle():
    lp = log_file()
    try:
        with open(lp, "rb") as f:
            f.seek(0, os.SEEK_END)
            last = f.tell()
    except Exception as e:
        log("❌ Failed to open log file: " + str(e))
        return False

    click_build()
    log("🔎 Monitoring lightbuild log …")
    freeze_th = config["cpu_freeze_threshold"]
    max_no_free = config["max_bake_time_without_freeze"]
    timer_start = time.time()

    while True:
        if not is_editor_running():
            close_crash_reporter()
            log("🛑 Editor exited prematurely.")
            return False

        try:
            with open(lp, "r", errors="ignore") as f:
                f.seek(last)
                new = f.read()
                last = f.tell()
            if "LogGPULightmass: Total lighting time" in new:
                log("✅ Lightbuild finished.")
                return True
        except Exception:
            pass

        cpu = get_editor_cpu()
        log(f"🧠 Unreal CPU usage: {cpu:.1f}%")

        if cpu < freeze_th:
            timer_start = time.time()
            log("⏳ Low CPU detected – timer reset.")
        elif time.time() - timer_start > max_no_free:
            log("🔁 Unreal didn’t freeze – retrying build …")
            if is_editor_running():
                click_build()
            timer_start = time.time()

        countdown("⏳ Next log check", config["log_check_interval"])

# ---------- MAP RELOAD ----------
def reload_map():
    log("⏳ Waiting for map to reload …")
    upath = to_unreal(config["map_name"])
    if not upath.startswith("/Game/"):
        log("❌ Invalid map path: " + upath)
        return False
    pyautogui.click(config["console_pos"])
    time.sleep(0.4)
    pyautogui.typewrite(f'import unreal; unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level("{upath}")')
    pyautogui.press("enter")
    countdown("⏳ Waiting after reload", config["post_reload_delay"])
    log("✅ Map reloaded.")
    return True

def refresh_chunk_info():
    project_dir = os.path.dirname(config["project_path"])
    chk_path = os.path.join(project_dir, "Saved", "GPUCrashFinder", "crash_isolation_state.json")
    bad_path = os.path.join(project_dir, "Saved", "GPUCrashFinder", "crashing_actors_list.txt")

    if not os.path.exists(chk_path):
        chunk_status_var.set("⏳ Waiting for first run …")
        return

    try:
        with open(chk_path, "r") as f:
            s = json.load(f)
    except Exception:
        chunk_status_var.set("❌ JSON read error")
        return

    total = s.get("all_chunks", 0)
    done  = s.get("chunks_completed", 0)
    chunk_status_var.set(f"🧩 Chunks: {done}/{total} (Left: {total - done})")

    if s.get("finished"):
        if os.path.exists(bad_path):
            faulty_actors_var.set(open(bad_path).read().strip() or "✅ No crashing actors found.")
        else:
            faulty_actors_var.set("✅ No crashing actors found.")

# ---------- WATCHDOG ----------
def watchdog():
    global stop_requested, watchdog_running
    watchdog_running = True
    status_var.set("🟢 Watchdog running")
    start_btn.config(state="disabled")
    stop_btn.config(state="normal")

    if chunks_finished():
        log("🏁 Autorunner already finished – stopping Watchdog.")
        status_var.set("⚪ Cycle finished")
        watchdog_running = False
        return

    unreal_crashed = get_last_crash_status()
    skip_launch = not unreal_crashed and is_editor_running()

    while True:
        if stop_requested:
            log("🛑 Stop requested – Watchdog ending after this cycle.")
            stop_requested = False
            break

        if chunks_finished():
            log("🏁 All chunks tested – Watchdog stopping.")
            break

        if not skip_launch:
            launch_unreal()
            countdown("⏳ Initializing", config["initial_delay"])

        exec_runner()
        countdown("⏳ Waiting autorunner", config["autorunner_delay"])

        refresh_chunk_info()

        if chunks_finished():
            log("🏁 All chunks tested – Watchdog stopping.")
            break

        if not bake_cycle():
            write_status(True)
            skip_launch = False
            continue

        write_status(False)

        if chunks_finished():
            log("🏁 All chunks tested – Watchdog stopping.")
            break

        if not reload_map():
            skip_launch = False
            continue

        skip_launch = True

    watchdog_running = False
    status_var.set("🔴 Watchdog stopped")
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")

# ---------- TKINTER UI ----------
root = tk.Tk()
tk.Label(
    root,
    text="⚠️ Use Watchdog only with version control (Git, Perforce) or backups.",
    fg="orange",
    bg="#2b2b2b",
    font=("Segoe UI", 10, "bold")
).pack(pady=5)

root.configure(bg="#2b2b2b")
root.option_add("*Foreground", "#ffffff")
root.option_add("*Background", "#2b2b2b")
root.option_add("*Entry.Background", "#3c3f41")
root.option_add("*Entry.Foreground", "#ffffff")
root.option_add("*Button.Background", "#3c3f41")
root.option_add("*Button.Foreground", "#ffffff")
root.option_add("*Label.Foreground", "#ffffff")
root.option_add("*Label.Background", "#2b2b2b")
root.title("GPU Lightmass Watchdog")

chunk_status_var  = tk.StringVar(value="⏳ No chunk info yet.")
faulty_actors_var = tk.StringVar(value="")
status_var        = tk.StringVar(value="🔴 Watchdog stopped")

def row(lbl, key, is_file=True):
    tk.Label(root, text=lbl).pack()
    e = tk.Entry(root, width=70)
    e.insert(0, str(config[key]))
    e.pack()
    if is_file:
        tk.Button(root, text="Browse", command=lambda: browse(key, e)).pack()
    else:
        def update(_=None):
            try:
                config[key] = int(e.get())
                save_cfg()
            except ValueError:
                pass
        e.bind("<FocusOut>", update)
        e.bind("<Return>",  update)

def pick_pos(key):
    log(f"🖱 Move mouse for {key} – capturing in 5 s …")
    time.sleep(5)
    config[key] = pyautogui.position()
    log("✅ " + str(config[key]))
    save_cfg()

def browse(key, e):
    p = filedialog.askopenfilename()
    e.delete(0, tk.END)
    e.insert(0, p)
    config[key] = p
    save_cfg()

row("Unreal Editor EXE",             "unreal_path")
row(".uproject file",                "project_path")
row("Map (internal OR .umap path)",  "map_name")
row("auto_runner.py",                "autorunner_path")
row("Initial Delay (s)",             "initial_delay",       is_file=False)
row("Autorunner Delay (s)",          "autorunner_delay",    is_file=False)
row("Post-reload Delay (s)",         "post_reload_delay",   is_file=False)
row("Log Check Interval (s)",        "log_check_interval",  is_file=False)
row("CPU Freeze Threshold (%)",      "cpu_freeze_threshold",is_file=False)
row("Max Bake Time without freeze",  "max_bake_time_without_freeze", is_file=False)

tk.Button(root, text="Pick Lightmass Button", command=lambda: pick_pos("click_pos")).pack(pady=3)
tk.Button(root, text="Pick Console Click", command=lambda: pick_pos("console_pos")).pack(pady=3)

tk.Label(root, textvariable=chunk_status_var, fg="blue").pack(pady=2)
tk.Label(root, textvariable=faulty_actors_var, fg="red").pack(pady=2)
tk.Label(root, textvariable=status_var, fg="green").pack(pady=2)

start_btn = tk.Button(root, text="▶ Start / Resume", command=lambda: threading.Thread(target=watchdog, daemon=True).start())
start_btn.pack(pady=8)
stop_btn = tk.Button(root, text="🛑 Stop After Current Cycle", fg="orange", state="disabled", command=lambda: set_stop())
stop_btn.pack(pady=3)

def reset_isolation_progress():
    project_dir = os.path.dirname(config["project_path"])
    state_file = os.path.join(project_dir, "Saved", "GPUCrashFinder", "crash_isolation_state.json")
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
            log("🗑 crash_isolation_state.json deleted.")
        except Exception as e:
            log(f"❌ Failed to delete crash_isolation_state.json: {e}")
    else:
        log("ℹ️ No crash_isolation_state.json found to delete.")

tk.Button(root, text="🗑 Reset Isolation Progress", fg="red", command=reset_isolation_progress).pack(pady=6)


log_text = scrolledtext.ScrolledText(root, height=14, width=100)
log_text.pack(pady=6)

# Tag configs first
log_text.tag_config("error", foreground="red")
log_text.tag_config("warn", foreground="orange")
log_text.tag_config("info", foreground="white")
log_text.tag_config("ok", foreground="lightgreen")
log_text.tag_config("countdown", foreground="cyan")

log_text.insert(tk.END, "📝 Log started.\n", "info")
log_text.insert(tk.END, "\n", "countdown")

log_text.mark_set("countdown_mark", "end -1 line")
log_text.mark_gravity("countdown_mark", tk.RIGHT)





def set_stop():
    global stop_requested
    stop_requested = True
    stop_btn.config(state="disabled")

root.mainloop()
