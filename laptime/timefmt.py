def fmt_time(seconds: float) -> str:
    """88.819 -> '1:28.819'"""
    m, s = divmod(seconds, 60.0)
    return f"{int(m)}:{s:06.3f}"


def parse_time(text: str) -> float:
    """'1:31.694' or '91.694' -> 91.694"""
    text = text.strip()
    if ":" in text:
        m, s = text.split(":", 1)
        return int(m) * 60 + float(s)
    return float(text)
