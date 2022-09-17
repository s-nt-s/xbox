import time

# https://stackoverflow.com/a/64030200/5204002


def retry(times, exceptions, sleep=0, skip_in_error=False):
    """
    Retry Decorator
    Retries the wrapped function/method `times` times if the exceptions listed
    in ``exceptions`` are thrown
    :param times: The number of times to repeat the wrapped function/method
    :type times: Int
    :param Exceptions: Lists of exceptions that trigger a retry attempt
    :type Exceptions: Tuple of Exceptions
    """
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            last_exc = None
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    attempt += 1
                    time.sleep(sleep)
            if skip_in_error or isinstance(last_exc, SkipRetryException):
                return None
            return func(*args, **kwargs)
        return newfn
    return decorator


class RetryException(Exception):
    pass


class SkipRetryException(Exception):
    pass
