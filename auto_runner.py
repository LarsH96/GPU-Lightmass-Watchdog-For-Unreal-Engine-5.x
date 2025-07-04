import unreal
import os
import json
import math
import time

PROJECT_DIR = unreal.SystemLibrary.get_project_directory()
SAVED_DIR = os.path.join(PROJECT_DIR, "Saved", "GPUCrashFinder")
os.makedirs(SAVED_DIR, exist_ok=True)

STATE_FILE = os.path.join(SAVED_DIR, "crash_isolation_state.json")
EXPORT_FILE = os.path.join(SAVED_DIR, "crashing_actors_list.txt")
STATUS_FILE = os.path.join(SAVED_DIR, "status.json")
CHUNK_COUNT = 10

def get_relevant_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = subsystem.get_all_level_actors()
    relevant = []
    for actor in all_actors:
        name = actor.get_name()
        if isinstance(actor, (unreal.StaticMeshActor, unreal.Landscape)):
            relevant.append(actor)
        elif actor.get_components_by_class(unreal.SplineMeshComponent):
            relevant.append(actor)
        elif name.startswith("BP_") or "Blueprint" in actor.get_class().get_name():
            relevant.append(actor)
        else:
            relevant.append(actor)
    return relevant

def destroy_actors_not_in(names_to_keep):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = subsystem.get_all_level_actors()
    for actor in all_actors:
        if actor.get_name() not in names_to_keep:
            try:
                subsystem.destroy_actor(actor)
            except Exception as e:
                unreal.log_warning(f"Could not delete {actor.get_name()}: {e}")

def export_crashing_actors(state):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = subsystem.get_all_level_actors()
    name_to_label = {actor.get_name(): actor.get_actor_label() for actor in all_actors}

    with open(EXPORT_FILE, "w") as f:
        f.write("Crashing Actors:\n")
        for name in state["tested_bad"]:
            label = name_to_label.get(name, name)
            f.write(label + "\n")
    unreal.log(f"📝 Exported crashing actors to: {EXPORT_FILE}")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    else:
        return {
            "tested_good": [],
            "tested_bad": [],
            "to_test": [],
            "index_stack": [],
            "initialized": False,
            "last_chunk": [],
            "finished": False
        }

def save_state(state):
    total_chunks = len(state.get("index_stack", [])) + (1 if state.get("last_chunk") else 0)
    completed_chunks = len(state.get("tested_good", [])) + len(state.get("tested_bad", []))
    all_chunks = total_chunks + completed_chunks

    extended_state = state.copy()
    extended_state["chunks_remaining"] = total_chunks
    extended_state["chunks_completed"] = completed_chunks
    extended_state["all_chunks"] = all_chunks
    extended_state["current_chunk_size"] = len(state.get("last_chunk", []))

    with open(STATE_FILE, "w") as f:
        json.dump(extended_state, f, indent=2)

def initialize_chunks(all_names):
    chunks = []
    chunk_size = math.ceil(len(all_names) / CHUNK_COUNT)
    for i in range(0, len(all_names), chunk_size):
        chunks.append([i, min(i + chunk_size, len(all_names))])
    return chunks

def check_previous_crash():
    if not os.path.exists(STATUS_FILE):
        return None
    with open(STATUS_FILE, "r") as f:
        try:
            data = json.load(f)
            return data.get("crashed")
        except json.JSONDecodeError:
            unreal.log_warning("⚠️ Could not parse status.json")
            return None

def clear_crash_flag():
    with open(STATUS_FILE, "w") as f:
        json.dump({"crashed": False}, f)

def get_label_by_name(name):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        if actor.get_name() == name:
            try:
                return actor.get_actor_label()
            except Exception:
                return name
    return name

def main():
    time.sleep(1)
    state = load_state()

    if state["finished"]:
        unreal.log("🏁 All chunks tested. Done.")
        export_crashing_actors(state)
        return

    if not state["initialized"]:
        all_actors = get_relevant_actors()
        actor_names = [a.get_name() for a in all_actors]
        state["to_test"] = actor_names
        state["index_stack"] = initialize_chunks(actor_names)
        state["initialized"] = True
        save_state(state)
        unreal.log("🟢 First run complete. Run lighting and allow Watchdog to continue.")
        return

    crashed = check_previous_crash()
    if crashed is None:
        unreal.log_warning("⚠️ Could not determine crash status.")
        return

    if state["last_chunk"]:
        chunk = state["last_chunk"]
        unreal.log(f"📋 Last tested chunk: {chunk}")
        if crashed:
            if len(chunk) == 1:
                state["tested_bad"].append(chunk[0])
                state["last_chunk"] = []
                unreal.log_warning(f"❌ Crash confirmed: {chunk[0]}")
            else:
                all_names = state["to_test"]
                indices = [all_names.index(n) for n in chunk if n in all_names]
                if not indices:
                    unreal.log_error("⚠️ Index mapping failed. Skipping.")
                    state["last_chunk"] = []
                    return
                start, end = min(indices), max(indices) + 1
                mid = (start + end) // 2
                state["index_stack"].append([mid, end])
                state["index_stack"].append([start, mid])
                state["last_chunk"] = []
                unreal.log_warning("⚠️ Crash detected. Chunk split in two.")
        else:
            state["tested_good"].extend(chunk)
            state["last_chunk"] = []
            unreal.log("✅ Chunk passed. Moving on...")
        save_state(state)
        clear_crash_flag()

    while state["index_stack"]:
        start, end = state["index_stack"].pop()
        chunk = state["to_test"][start:end]
        chunk = [n for n in chunk if n not in state["tested_good"] and n not in state["tested_bad"]]
        if not chunk:
            continue

        state["last_chunk"] = chunk
        save_state(state)

        destroy_actors_not_in(chunk)
        unreal.log(f"🔬 Testing chunk ({len(chunk)} actors):")
        for name in chunk:
            label = get_label_by_name(name)
            unreal.log(f"   ↪ {label}")
        unreal.log("⏳ Ready to build lighting. Watchdog will resume control.")
        return

    state["finished"] = True
    save_state(state)
    export_crashing_actors(state)
    unreal.log("✅ All chunks tested. Crashing actors isolated.")

main()
