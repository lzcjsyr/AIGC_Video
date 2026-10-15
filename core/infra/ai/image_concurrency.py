"""Provider request ceilings shared by threads, projects and cover/visual job processes."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import tempfile
import time


@contextmanager
def provider_slot(provider):
    provider = "google" if provider in {"google", "google_adc"} else provider
    limit = {"google": 1, "doubao": 5}.get(provider, 1)
    root = Path(os.environ.get("AIGC_IMAGE_CONCURRENCY_DIR") or Path(tempfile.gettempdir()) / "aigc-image-requests")
    root.mkdir(parents=True, exist_ok=True)
    held = None
    while held is None:
        for index in range(limit):
            handle = (root / f"{provider}-{index}.lock").open("a+b")
            try:
                if os.name == "nt":
                    import msvcrt
                    if not handle.seek(0, 2):
                        handle.write(b"0"); handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
            else:
                held = handle
                break
        if held is None:
            time.sleep(.05)
    try:
        yield
    finally:
        # The OS also releases the slot when a cancelled job exits.
        held.close()
