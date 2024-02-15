import signal


class timeout:
    def __init__(self, seconds: int = 1, error_message: str = 'Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self, *args, **kwargs):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, *args, **kwargs):
        signal.alarm(0)
