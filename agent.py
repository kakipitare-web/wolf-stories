#!/usr/bin/env python3
"""הסוכן של הזאב — רץ כל 10 דקות ב-GitHub Actions ומעלה סטוריז ל-tip4winner:
  1. הרכבים — ברגע שההרכב הרשמי יוצא ב-FotMob (בערך שעה לפני שריקה)
  2. סיום — נתוני המשחק אחרי שריקת הסיום
  3. ניתוח חדש — סטורי לכל קרוסלה חדשה שגל מעלה
המצב נשמר ב-state.json (נשמר בריפו בין ריצות). הרצה: python3 agent.py [--dry-run]
טוקן: IG_TOKEN / IG_USER_ID ממשתני הסביבה (Secrets), או מ-~/Documents/TUNNEL-il/.secrets/ig_wolf.env במק."""
import calendar, json, os, subprocess, sys, time, traceback, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lineups as L

STATE = HERE / "state.json"
DRY = "--dry-run" in sys.argv
REPO = os.environ.get("GITHUB_REPOSITORY", "kakipitare-web/wolf-stories")
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"
API = "https://graph.instagram.com/v23.0/"
MAX_PER_DAY = {"lineup": 10, "fulltime": 10, "gal": 6}

# הליגות של הזאב (רשימת המועדפים של דניאל ב-Flashscore, 28.10) + הגביעים של כל מדינה. מזהי FotMob.
# 0 = ישראל · 1 = אירופה + 5 הגדולות וגביעיהן · 2 = כל השאר. כשיש הרבה משחקים, התקרה היומית נתפסת לפי הסדר הזה.
TIER = {
    127: 0, 128: 0, 9097: 0, 9098: 0,
    42: 1, 73: 1, 10216: 1, 50: 1, 9806: 1,
    47: 1, 87: 1, 55: 1, 54: 1, 53: 1, 132: 1, 133: 1, 138: 1, 141: 1, 209: 1, 134: 1,
    48: 2, 140: 2, 86: 2, 146: 2, 110: 2, 57: 2, 111: 2, 235: 2, 61: 2, 185: 2, 186: 2, 187: 2, 40: 2, 149: 2,
    64: 2, 137: 2, 180: 2, 38: 2, 278: 2, 135: 2, 145: 2, 212: 2, 213: 2, 215: 2, 217: 2, 8983: 2, 122: 2, 254: 2,
    46: 2, 242: 2, 51: 2, 143: 2, 196: 2, 198: 2, 189: 2, 190: 2, 535: 2, 11018: 2, 536: 2, 9942: 2, 173: 2,
    174: 2, 67: 2, 171: 2, 69: 2, 164: 2, 268: 2, 9067: 2, 270: 2, 271: 2, 120: 2, 9550: 2, 252: 2, 275: 2,
    136: 2, 330: 2, 248: 2, 226: 2, 228: 2, 223: 2, 9011: 2, 224: 2, 113: 2, 9471: 2, 59: 2, 206: 2,
}
INTL = ("euro", "nations league", "libertadores")  # תחרויות נבחרות/יבשתיות לפי שם


def log(*a):
    print(time.strftime("%d.%m %H:%M"), *a, flush=True)


def secrets():
    if not os.environ.get("IG_TOKEN"):
        f = Path.home() / "Documents/TUNNEL-il/.secrets/ig_wolf.env"
        for line in f.read_text().splitlines():
            k, _, v = line.partition("=")
            os.environ[k] = v
    return os.environ["IG_TOKEN"], os.environ["IG_USER_ID"]


def ig(path, params=None, post=False):
    token, _ = secrets()
    data = urllib.parse.urlencode(dict(params or {}, access_token=token)).encode()
    url = API + path
    req = urllib.request.Request(url, data) if post else urllib.request.Request(url + "?" + data.decode())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Instagram {path}: {e.read().decode()[:300]}")


def git(*a):
    subprocess.run(["git", "-C", str(HERE), *a], check=True, capture_output=True)


def host(jpg):
    """מעלה את התמונה לריפו הציבורי ומחזיר כתובת שאינסטגרם יכול למשוך."""
    rel = jpg.relative_to(HERE).as_posix()
    git("add", "-f", rel)
    git("commit", "-qm", f"story {rel}")
    git("pull", "-q", "--rebase")
    git("push", "-q")
    url = RAW + urllib.parse.quote(rel)
    for _ in range(20):
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20)
            return url
        except Exception:
            time.sleep(3)
    return url


def publish_story(folder):
    if DRY:
        log("  [dry-run] היה עולה:", folder.name)
        return
    _, uid = secrets()
    cid = ig(f"{uid}/media", {"image_url": host(folder / "story.jpg"), "media_type": "STORIES"}, post=True)["id"]
    for _ in range(40):
        if ig(cid, {"fields": "status_code"}).get("status_code") in ("FINISHED", None):
            break
        time.sleep(3)
    sid = ig(f"{uid}/media_publish", {"creation_id": cid}, post=True)["id"]
    log("  ✅ עלה סטורי", sid)
    time.sleep(60)  # רווח בין העלאות — לא להיראות כמו ספאם


def utc_ts(s, fmt):
    return calendar.timegm(time.strptime(s, fmt))


def todays_matches():
    day = time.strftime("%Y%m%d")
    d = L.get(f"https://www.fotmob.com/api/data/matches?date={day}&timezone=Asia/Jerusalem")
    out = []
    for lg in d.get("leagues", []):
        pid = lg.get("primaryId")
        tier = TIER.get(pid, 1 if any(k in (lg.get("name") or "").lower() for k in INTL) else None)
        if tier is None:
            continue
        for m in lg.get("matches", []):
            out.append(dict(id=str(m["id"]), ko=utc_ts(m["status"]["utcTime"][:16], "%Y-%m-%dT%H:%M"),
                            name=f'{m["home"]["name"]} - {m["away"]["name"]}', finished=m["status"].get("finished"),
                            cancelled=m["status"].get("cancelled"), prio=tier))
    return sorted(out, key=lambda x: (x["prio"], x["ko"]))


def gal_carousels(st):
    _, uid = secrets()
    data = ig(f"{uid}/media", {"fields": "id,media_type,timestamp,caption,children{media_url}", "limit": 10})["data"]
    new = []
    for m in data:
        if m["id"] in st["seen_media"]:
            continue
        st["seen_media"].append(m["id"])
        if m["media_type"] == "CAROUSEL_ALBUM" and utc_ts(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S") > st["since"]:
            new.append(m)
    return new


def gal_story(m):
    out = HERE / "wolf-stories" / f"gal_{m['id']}"
    out.mkdir(parents=True, exist_ok=True)
    lines = (m.get("caption") or "").splitlines()
    data = dict(img=m["children"]["data"][0]["media_url"], sub=lines[1] if len(lines) > 1 else "")
    import shutil
    shutil.copy(HERE / "wolf.jpg", out / "wolf.jpg")
    (out / "page.html").write_text((HERE / "gal_story.html").read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False)))
    L.shoot(out / "page.html", out / "story.jpg")
    return out


def main():
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    st.setdefault("done", {})          # "<matchId>_<kind>": זמן
    st.setdefault("seen_media", [])
    st.setdefault("since", time.time())
    st.setdefault("count", {})         # "<yyyymmdd>_<kind>": כמה עלו היום
    day, now = time.strftime("%Y%m%d"), time.time()

    def can(kind):
        return st["count"].get(f"{day}_{kind}", 0) < MAX_PER_DAY[kind]

    def mark(key, kind):
        st["done"][key] = now
        st["count"][f"{day}_{kind}"] = st["count"].get(f"{day}_{kind}", 0) + 1
        if not DRY:
            STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))

    try:
        for m in gal_carousels(st):
            if can("gal"):
                log("ניתוח חדש של גל →", m["id"])
                publish_story(gal_story(m))
                mark(f"gal_{m['id']}", "gal")
    except Exception:
        log("שגיאה בקרוסלות:", traceback.format_exc()[-500:])

    for m in todays_matches():
        if m["cancelled"]:
            continue
        try:
            key_l, key_f = f"{m['id']}_lineup", f"{m['id']}_fulltime"
            if key_l not in st["done"] and not m["finished"] and m["ko"] - 80 * 60 <= now <= m["ko"] + 15 * 60 and can("lineup"):
                d = L.match_data(m["id"])
                if d["lineup_type"] not in (None, "predicted") and len(d["teams"][0]["starters"]) == 11:
                    log("הרכבים →", m["name"])
                    publish_story(L.render("lineup", d))
                    mark(key_l, "lineup")
            if key_f not in st["done"] and m["finished"] and now - m["ko"] < 4 * 3600 and can("fulltime"):
                d = L.match_data(m["id"])
                rich = sum(k in d["stats"] for k in ("BallPossesion", "expected_goals", "total_shots", "ShotsOnTarget")) >= 3
                if d["teams"][0]["score"] is not None and rich and d["momentum"]:
                    log("סיום →", m["name"], f'{d["teams"][0]["score"]}-{d["teams"][1]["score"]}')
                    publish_story(L.render("fulltime", d))
                    mark(key_f, "fulltime")
        except Exception:
            log("שגיאה במשחק", m["name"], traceback.format_exc()[-500:])
    if not DRY:
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
