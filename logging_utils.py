# logging_utils.py
import datetime
import os
import sys


class LoggerTee:
    """Dual output to terminal and log file with buffering."""

    def __init__(self, filename: str, buffer_size: int = 8192):
        self.terminal = sys.stdout
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.log = open(filename, "a", encoding="utf-8", buffering=buffer_size)

    def write(self, message: str):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        if hasattr(self, 'log') and not self.log.closed:
            self.log.close()


def cleanup_old_files(target_dir: str, days_to_keep: int = 7,
                      extensions: tuple = (".txt", ".csv")):
    """Delete files older than `days_to_keep` with given extensions."""
    try:
        if not os.path.exists(target_dir):
            return

        now = datetime.datetime.now()
        cutoff = now - datetime.timedelta(days=days_to_keep)
        deleted_count = 0

        for filename in os.listdir(target_dir):
            if not filename.lower().endswith(extensions):
                continue

            file_path = os.path.join(target_dir, filename)
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

            if file_mtime < cutoff:
                os.remove(file_path)
                deleted_count += 1

        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} old file(s) "
                  f"({', '.join(extensions)}) older than {days_to_keep} days\n")
    except Exception as e:
        print(f"⚠️ File cleanup failed in {target_dir}: {e}")


def setup_logging() -> str:
    """Initialize logging to file and console."""
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Clean old log files
    cleanup_old_files(log_dir, days_to_keep=7, extensions=(".txt",))

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f"audit_log_{timestamp}.txt")

    sys.stdout = LoggerTee(log_path)
    sys.stderr = sys.stdout

    print(f"🪵 Logging started → {log_path}\n")
    return log_path
