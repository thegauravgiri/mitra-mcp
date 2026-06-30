import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from mitra.config import get_config_dir

TIMER_FILE = Path.home() / ".config" / "mitra" / "timers.json"

def _ensure_timer_file():
    get_config_dir() # ensures config dir exists
    if not TIMER_FILE.exists():
        with open(TIMER_FILE, "w") as f:
            json.dump({"active": {}}, f, indent=4)

def _load_timers() -> Dict[str, Any]:
    _ensure_timer_file()
    try:
        with open(TIMER_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"active": {}}

def _save_timers(data: Dict[str, Any]) -> None:
    _ensure_timer_file()
    with open(TIMER_FILE, "w") as f:
        json.dump(data, f, indent=4)

def start_timer(
    file_path: str,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """Starts a local timer for a file. If already running, updates it."""
    abs_path = str(Path(file_path).resolve())
    data = _load_timers()
    
    timer_info = {
        "start_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workspace_id": workspace_id,
        "project_id": project_id,
        "description": description
    }
    
    data["active"][abs_path] = timer_info
    _save_timers(data)
    
    timer_info["file_path"] = abs_path
    return timer_info

def stop_timer(file_path: str) -> Dict[str, Any]:
    """Stops the timer for a file, calculates duration, and returns details."""
    abs_path = str(Path(file_path).resolve())
    data = _load_timers()
    
    if abs_path not in data["active"]:
        raise ValueError(f"No active timer found for file: {abs_path}")
        
    timer_info = data["active"].pop(abs_path)
    _save_timers(data)
    
    start_time_str = timer_info["start_time"]
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end_time = datetime.now(timezone.utc)
    end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    duration_seconds = int((end_time - start_time).total_seconds())
    
    return {
        "file_path": abs_path,
        "start_time": start_time_str,
        "end_time": end_time_str,
        "duration_seconds": duration_seconds,
        "workspace_id": timer_info.get("workspace_id"),
        "project_id": timer_info.get("project_id"),
        "description": timer_info.get("description", "")
    }

def get_active_timers() -> List[Dict[str, Any]]:
    """Lists all active local timers."""
    data = _load_timers()
    active_timers = []
    for file_path, info in data.get("active", {}).items():
        timer = info.copy()
        timer["file_path"] = file_path
        
        # Calculate running duration
        start_time = datetime.strptime(info["start_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        timer["duration_seconds"] = int((now - start_time).total_seconds())
        active_timers.append(timer)
        
    return active_timers
