CORE_FIELDS = [
    "title",
    "author",
    "publish_time",
    "play_count",
    "like_count",
    "comment_count",
    "favorite_count",
    "share_count",
]


def _missing_fields(data: dict) -> list[str]:
    missing = []
    for field in CORE_FIELDS:
        value = data.get(field)
        if value is None or value == "":
            missing.append(field)
    return missing


def ok(data: dict, source: str, missing_fields: list[str] | None = None) -> dict:
    missing = missing_fields if missing_fields is not None else _missing_fields(data)
    return {
        "status": "partial" if missing else "ok",
        "data": data,
        "missing_fields": missing,
        "error": None,
        "source": source,
    }


def partial(data: dict, source: str, missing_fields: list[str], message: str | None = None) -> dict:
    return {
        "status": "partial",
        "data": data,
        "missing_fields": missing_fields,
        "error": message,
        "source": source,
    }


def error(message: str, source: str = "manual_unavailable", missing_fields: list[str] | None = None) -> dict:
    return {
        "status": "error",
        "data": None,
        "missing_fields": missing_fields or CORE_FIELDS,
        "error": message,
        "source": source,
    }


def normalize(result: dict | None, default_source: str) -> dict:
    if not result:
        return error("无数据返回", default_source)
    if "status" in result and "source" in result:
        return result
    if "error" in result:
        return error(result.get("error") or "抓取失败", result.get("source", default_source))
    return ok(result, default_source)
