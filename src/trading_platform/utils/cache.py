
import os
import shutil
from pathlib import Path

def clear_numba_cache():
    """
    Clears the Numba cache directories.

    This function removes Numba cache files from the following locations:
    - In-tree caches within `__pycache__` directories in the project's `src` folder.
    - The user-wide Numba cache directory (`~/.cache/numba`).
    """
    project_root = Path(__file__).parent.parent.parent.parent
    src_dir = project_root / "src"
    cleared_files = []
    cleared_dirs = []

    # Clear in-tree caches
    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in dirs:
            pycache_dir = Path(root) / "__pycache__"
            for item in os.listdir(pycache_dir):
                if ".nbi" in item or ".nbc" in item or "numba" in item:
                    file_path = pycache_dir / item
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            cleared_files.append(str(file_path))
                    except OSError as e:
                        print(f"Error removing file {file_path}: {e}")

    # Clear user-wide cache
    home_dir = Path.home()
    user_cache_dir = home_dir / ".cache" / "numba"
    if user_cache_dir.exists() and user_cache_dir.is_dir():
        try:
            shutil.rmtree(user_cache_dir)
            cleared_dirs.append(str(user_cache_dir))
        except OSError as e:
            print(f"Error removing directory {user_cache_dir}: {e}")

    if cleared_files:
        print("Removed Numba cache files:")
        for f in cleared_files:
            print(f"- {f}")

    if cleared_dirs:
        print("Removed Numba cache directories:")
        for d in cleared_dirs:
            print(f"- {d}")

    if not cleared_files and not cleared_dirs:
        print("No Numba cache files or directories found to clear.")
