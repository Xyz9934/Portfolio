import threading


class TaskScheduler:

    def run_async(self, func, *args, **kwargs):

        thread = threading.Thread(
            target=func,
            args=args,
            kwargs=kwargs,
            daemon=True
        )

        thread.start()
