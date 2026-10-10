"""One Turo at a time. A second copy hears the same hotkeys, draws a second card and talks over the first,
so a second launch (e.g. the desktop shortcut again) only asks the running Turo to show its window."""
import ctypes
import ctypes.wintypes
import threading

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateMutexW.restype = _k32.CreateEventW.restype = _k32.OpenEventW.restype = ctypes.wintypes.HANDLE
_k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
_k32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
_k32.OpenEventW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
_k32.SetEvent.argtypes = _k32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
_k32.WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]

RUNNING, SHOW = "Local\\TuroRunning", "Local\\TuroShowHome"
ERROR_ALREADY_EXISTS, EVENT_MODIFY_STATE, INFINITE = 183, 0x0002, 0xFFFFFFFF
_handles = []   # held for the life of the process; Windows frees them if Turo crashes


def claim():
    """True if this is the only Turo. Otherwise wake the running one's window and return False."""
    _handles.append(_k32.CreateMutexW(None, False, RUNNING))
    if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        return True
    event = _k32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW)
    if event:
        _k32.SetEvent(event)
        _k32.CloseHandle(event)
    return False


def on_show_request(callback):
    """Call `callback` (from a worker thread) whenever another launch asks to show Turo."""
    event = _k32.CreateEventW(None, False, False, SHOW)   # auto-reset
    _handles.append(event)

    def wait():
        while _k32.WaitForSingleObject(event, INFINITE) == 0:
            callback()

    threading.Thread(target=wait, daemon=True).start()


if __name__ == "__main__":
    print("first claim (only copy):", claim())
    print("second claim (already running):", claim())
