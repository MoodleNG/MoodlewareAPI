import json
from typing import Any, Dict, List


def parse_list_value(raw_val: Any) -> List[Any]:
    if raw_val is None:
        return []
    if isinstance(raw_val, list):
        return raw_val
    if isinstance(raw_val, (bool, int, float)):
        return [raw_val]
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if s == "":
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            if "," in s:
                return [part.strip() for part in s.split(",") if part.strip() != ""]
            return [s]
    return [raw_val]


def encode_param(params: Dict[str, Any], name: str, value: Any, declared_type: str) -> None:
    dtype = (declared_type or "str").lower()

    if dtype == "bool":
        if isinstance(value, str):
            v = value.strip().lower()
            value = 1 if v in {"1", "true", "on", "yes"} else 0
        else:
            value = 1 if bool(value) else 0
        params[name] = value
        return

    if dtype in {"float", "double"}:
        try:
            params[name] = float(value)
        except Exception:
            params[name] = value
        return

    if dtype == "int":
        try:
            params[name] = int(value)
        except Exception:
            params[name] = value
        return

    if dtype == "list":
        items = parse_list_value(value)
        for idx, item in enumerate(items):
            if isinstance(item, dict):
                for k, v in item.items():
                    if isinstance(v, bool):
                        v = 1 if v else 0
                    params[f"{name}[{idx}][{k}]"] = v
            else:
                params[f"{name}[{idx}]"] = item
        return

    if isinstance(value, dict):
        for k, v in value.items():
            params[f"{name}[{k}]"] = v
        return

    params[name] = value
