import time

def wait_for_motion_complete(rtde_c, poll_interval: float = 0.01):
    """
    Blocks execution until the current asynchronous motion on the UR robot controller completes.
    Uses getAsyncOperationProgress() to query progress status.
    """
    while rtde_c.getAsyncOperationProgress() >= 0:
        time.sleep(poll_interval)
