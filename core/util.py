from typing import Union, Dict, List


def dict_walk(d: Union[Dict, List, None], path: str):
    if d is None:
        return None
    args = tuple(map(lambda x: int(x) if x.isdigit() else x, path.split("/")))
    for k in args:
        if isinstance(k, int):
            if not isinstance(d, list):
                raise ValueError(f"{k}: {d} must be a list")
            d = d[k]
        elif isinstance(k, str):
            if not isinstance(d, dict):
                raise ValueError(f"{k}: {d} must be a dict")
            d = d.get(k)
        else:
            raise ValueError(f"{k}: {d} must be a dict or list")
        if d is None:
            return None
    return d


def chunks(lst, n):
    arr = []
    for i in lst:
        arr.append(i)
        if len(arr) == n:
            yield arr
            arr = []
    if arr:
        yield arr
