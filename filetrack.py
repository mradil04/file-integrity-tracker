import os
import hashlib
import json
import time
import argparse
import getpass
import shutil
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from colorama import init, Fore, Style

# Initialize colorama for colored terminal output
init(autoreset=True)

# Default Configuration
DIRECTORY_TO_WATCH = "."
LOG_FILE = None
ENABLE_BACKUP = False
HASH_ALGO = "sha256"
IGNORED_EXTENSIONS = {".swp", ".swo", ".tmp", ".~", ".crdownload", ".part", ".goutputstream"}

# File tracking dictionary
file_data = {}

COLUMN_WIDTHS = {
    "file_path": 40,  
    "user": 12,  
    "timestamp": 19,  
    "status": 15,  
}

def is_valid_file(file_path):
    """Check if the file should be tracked (ignores hidden and temporary files)."""
    base_name = os.path.basename(file_path)
    return not base_name.startswith(".") and not any(file_path.endswith(ext) for ext in IGNORED_EXTENSIONS)

def calculate_hash(file_path):
    """Calculate the hash of a file using SHA-256."""
    if not is_valid_file(file_path):
        return None
    hash_func = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except FileNotFoundError:
        return None

def scan_initial_files():
    """Scan and store initial file states when the script starts."""
    for root, _, files in os.walk(DIRECTORY_TO_WATCH):
        for file in files:
            file_path = os.path.join(root, file)
            if is_valid_file(file_path):
                file_hash = calculate_hash(file_path)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                user = getpass.getuser()

                file_data[file_path] = {
                    "timestamp": timestamp,
                    "user": user,
                    "hash": file_hash,
                    "status": "unchanged",
                    "history": [{"timestamp": timestamp, "hash": file_hash, "user": user, "status": "unchanged"}]
                }

def clear_screen():
    """Clears the terminal screen."""
    os.system("clear" if os.name == "posix" else "cls")

def get_colored_status(status):
    """Returns colored text for different file statuses."""
    if status == "created":
        return Fore.GREEN + "🆕 Created" + Style.RESET_ALL
    elif status == "deleted":
        return Fore.RED + "❌ Deleted" + Style.RESET_ALL
    elif status == "modified":
        return Fore.YELLOW + "✏ Modified" + Style.RESET_ALL
    return Fore.BLUE + "Unchanged" + Style.RESET_ALL  

def format_display():
    """Formats and dynamically updates the terminal display like 'top' with colors."""
    try:
        terminal_width = shutil.get_terminal_size().columns
    except:
        terminal_width = 80  

    clear_screen()

    print(Fore.CYAN + f"\n📡 Monitoring: {DIRECTORY_TO_WATCH} (Press Ctrl+C to stop)\n" + Style.RESET_ALL)
    print(Fore.MAGENTA + "=" * terminal_width + Style.RESET_ALL)
    print(
        Fore.YELLOW
        + f"📂 {'File Path'.ljust(COLUMN_WIDTHS['file_path'])} | 👤 {'User'.ljust(COLUMN_WIDTHS['user'])} | 📅 {'Last Modified'.ljust(COLUMN_WIDTHS['timestamp'])} | 🔑 Status"
        + Style.RESET_ALL
    )
    print(Fore.MAGENTA + "=" * terminal_width + Style.RESET_ALL)

    sorted_files = sorted(file_data.items(), key=lambda x: x[1]["timestamp"], reverse=True)

    for file_path, data in sorted_files:
        status = get_colored_status(data["status"])
        file_name_colored = Fore.BLUE + Style.BRIGHT + file_path.ljust(COLUMN_WIDTHS["file_path"]) + Style.RESET_ALL
        user_colored = Fore.GREEN + data["user"].ljust(COLUMN_WIDTHS["user"]) + Style.RESET_ALL
        timestamp_colored = Fore.CYAN + data["timestamp"].ljust(COLUMN_WIDTHS["timestamp"]) + Style.RESET_ALL

        # Display status in the same row
        print(f"{file_name_colored} | {user_colored} | {timestamp_colored} | {status}")

        # Display SHA-256 hashes as a tree structure under "Status"
        if data["history"]:
            for entry in data["history"]:
                hash_colored = Fore.WHITE + Style.BRIGHT + entry["hash"] + Style.RESET_ALL
                timestamp_hash = Fore.LIGHTBLACK_EX + entry["timestamp"] + Style.RESET_ALL
                user_hash = Fore.GREEN + entry["user"] + Style.RESET_ALL
                print(" " * (COLUMN_WIDTHS["file_path"] + COLUMN_WIDTHS["user"] + COLUMN_WIDTHS["timestamp"] + 10) + "↳ " + hash_colored + f" ({user_hash}, {timestamp_hash})")

        print(Fore.MAGENTA + "-" * terminal_width + Style.RESET_ALL)

class FileChangeHandler(FileSystemEventHandler):
    """Watchdog event handler to track file changes in real-time."""
    def on_created(self, event):
        if not event.is_directory and is_valid_file(event.src_path):
            file_path = event.src_path
            file_hash = calculate_hash(file_path)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user = getpass.getuser()

            file_data[file_path] = {
                "timestamp": timestamp,
                "user": user,
                "hash": file_hash,
                "status": "created",
                "history": [{"timestamp": timestamp, "hash": file_hash, "user": user, "status": "created"}]
            }

            format_display()

    def on_modified(self, event):
        if not event.is_directory and is_valid_file(event.src_path):
            file_path = event.src_path
            new_hash = calculate_hash(file_path)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user = getpass.getuser()

            if file_path in file_data and file_data[file_path]["hash"] != new_hash:
                # Store old hash in history before updating
                old_hash = file_data[file_path]["hash"]
                file_data[file_path]["history"].append({
                    "timestamp": file_data[file_path]["timestamp"],
                    "hash": old_hash,
                    "user": file_data[file_path]["user"],
                    "status": "modified"
                })

                # Update file data with new hash
                file_data[file_path].update({
                    "timestamp": timestamp,
                    "user": user,
                    "hash": new_hash,
                    "status": "modified"
                })

                file_data[file_path]["history"].append({
                    "timestamp": timestamp,
                    "hash": new_hash,
                    "user": user,
                    "status": "modified"
                })

            format_display()

def start_monitoring():
    scan_initial_files()  
    format_display()  

    observer = Observer()
    observer.schedule(FileChangeHandler(), DIRECTORY_TO_WATCH, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File Fingerprint Tracker")
    parser.add_argument("command", choices=["start"], help="Start monitoring directory")
    parser.add_argument("--dir", help="Directory to monitor", required=True)
    parser.add_argument("--log", help="Log file for changes")
    parser.add_argument("--backup", action="store_true", help="Enable backup mode")

    args = parser.parse_args()

    DIRECTORY_TO_WATCH = args.dir
    LOG_FILE = args.log
    ENABLE_BACKUP = args.backup

    start_monitoring()
