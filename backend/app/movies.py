"""Helpers for keeping every video's movies unique."""
import re


def norm(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"^(the|a|an) ", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()


def parse_line(line: str):
    """'Parasite (2019)' -> ('Parasite', 2019); 'Se7en' -> ('Se7en', None)"""
    line = line.strip().lstrip("-*0123456789. ").strip()
    if not line:
        return None
    m = re.match(r"^(.*?)[\s(\[,-]*((?:19|20)\d{2})[)\]]?\s*$", line)
    if m and m.group(1).strip():
        return m.group(1).strip(), int(m.group(2))
    return line, None


def same_movie(a_title, a_year, b_title, b_year) -> bool:
    if norm(a_title) != norm(b_title) or not norm(a_title):
        return False
    return not (a_year and b_year and int(a_year) != int(b_year))  # a different year means a different film (remakes)


def conflicts(movies, used):
    """movies: [{'title','year'}] from a script. used: [{'title','year'}] already covered. Returns titles that clash,
    including a movie listed twice in the same script."""
    bad, seen = [], []
    for m in movies:
        t, y = m.get("title", ""), m.get("year")
        y = int(y) if str(y or "").isdigit() else None
        if any(same_movie(t, y, u["title"], u.get("year")) for u in used) or \
           any(same_movie(t, y, s[0], s[1]) for s in seen):
            bad.append(t)
        seen.append((t, y))
    return bad
