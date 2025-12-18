from threading import Lock, current_thread

lock_print = Lock()
def printt(*args, **kwargs):
    """
    Facilita la identificación de los prints de cada Thread.
    """
    with lock_print:
        print(f"[{current_thread().name}]:",*args, **kwargs)