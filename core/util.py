from typing import Union, Dict, List, Set, Tuple, Type


def dict_walk(obj: Union[Dict, List, None], path: str, instanceof: Union[None, Type, Tuple[Type, ...]] = None):
    raise_if_not_found = False
    if instanceof is not None:
        if isinstance(instanceof, type) and instanceof is not type(None):
            raise_if_not_found = True
        elif isinstance(instanceof, tuple) and type(None) not in instanceof:
            raise_if_not_found = True
    v = _dict_walk(obj, path, raise_if_not_found=raise_if_not_found)
    if isinstance(v, str):
        v = trim(v)
    if instanceof is not None and not isinstance(v, instanceof):
        raise ValueError(f"{path} is {type(v)} instead of {instanceof}")
    return v


def _dict_walk(d: Union[Dict, List, None], path: str, raise_if_not_found=False):
    if d is None:
        if raise_if_not_found:
            raise ValueError(f"{d} must be a list or dict")
        return None
    args = tuple(map(lambda x: int(x) if x.isdigit() else x, path.split("/")))
    not_found = False
    walk = []
    for k in args:
        if d is None or not_found:
            break
        walk.append(str(k))
        if isinstance(k, int):
            if not isinstance(d, list):
                raise ValueError(f"{'/'.join(walk)}: {d} must be a list")
            if k < len(d):
                d = d[k]
            else:
                not_found = True
        elif isinstance(k, str):
            if not isinstance(d, dict):
                raise ValueError(f"{'/'.join(walk)}: {d} must be a dict")
            if k in d:
                d = d[k]
            else:
                not_found = True
        else:
            raise ValueError(f"{'/'.join(walk)}: {d} must be a dict or list")
    if not_found:
        if raise_if_not_found:
            raise ValueError(f"{'/'.join(walk)} NOT FOUND")
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


def dict_add(obj: Dict[str, Set], a: str, b: Union[str, List[str], Set[str], Tuple[str]]):
    if a not in obj:
        obj[a] = set()
    if isinstance(b, str):
        obj[a].add(b)
    else:
        obj[a] = obj[a].union(b)


def dict_tuple(obj: Dict[str, Union[Set, List, Tuple]]):
    return {k: tuple(sorted(set(v))) for k, v in obj.items()}


def trim(s: str):
    if s is None:
        return None
    s = s.strip()
    if len(s) == 0:
        return None
    return s
