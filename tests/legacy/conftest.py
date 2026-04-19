import sys
import atexit


def cleanup():
    """Clean up resources on exit to avoid Windows access violations"""
    import gc

    gc.collect()


atexit.register(cleanup)
