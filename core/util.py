from typing import Union, Dict, List, Set, Tuple


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


def dict_del(obj: Union[Dict, List, None], path: str):
    if "/" not in path:
        if not isinstance(obj, dict):
            raise ValueError(f"{obj} must be a dict")
        if path in obj:
            del obj[path]
        return
    root, field = path.rsplit("/", 1)
    dct = dict_walk(obj, root)
    if dct is None:
        return
    if not isinstance(dct, dict):
        raise ValueError(f"{dct} must be a dict")
    if field in dct:
        del dct[field]


def chunks(lst, n):
    arr = []
    for i in lst:
        arr.append(i)
        if len(arr) == n:
            yield arr
            arr = []
    if arr:
        yield arr


def dict_add(obj: Dict[str, Set], a: str, b: str):
    if a not in obj:
        obj[a] = set()
    obj[a].add(b)


def dict_tuple(obj: Dict[str, Union[Set, List, Tuple]]):
    return {k: tuple(sorted(set(v))) for k, v in obj.items()}
