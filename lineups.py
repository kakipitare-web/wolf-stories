#!/usr/bin/env python3
"""סטורי הרכבים / אחרי משחק לזאב, מנתוני FotMob.

  python3 lineups.py lineup <matchId>      # ההרכבים (שעה לפני שריקה)
  python3 lineups.py fulltime <matchId>    # נתוני אחרי המשחק
פלט: out/<matchId>_<kind>/story.jpg + post.md (מוכן ל-publish_ig.py --story --no-feed)."""
import calendar, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
WD_UA = {"User-Agent": "wolf-lineups/1.0 (football stats bot)"}
CHROME = (next(Path.home().glob("Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"), None)
          or shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser"))
TEAMS = HERE / "teams_he.json"
LEAGUES = {47: "פרמייר ליג", 87: "לה ליגה", 55: "סרייה A", 54: "בונדסליגה", 53: "ליגה 1", 42: "ליגת האלופות",
           73: "הליגה האירופית", 10216: "הקונפרנס ליג", 127: "ליגת העל", 57: "ארדיביזי", 61: "ליגה פורטוגל",
           209: "גביע גרמניה", 138: "גביע המלך", 141: "גביע איטליה", 132: "גביע האנגלי", 133: "גביע הליגה",
           134: "גביע צרפת", 235: "גביע הולנד", 48: "צ'מפיונשיפ", 71: "סופר ליג", 40: "ליגת העל הבלגית",
           145: "גביע יוון", 242: "גביע דנמרק", 254: "גביע צ'כיה", 171: "גביע שוודיה", 135: "ליגת העל היוונית",
           46: "ליגת העל הדנית", 64: "ליגה סקוטית", 140: "לה ליגה 2", 86: "סרייה B", 146: "בונדסליגה 2",
           110: "ליגה 2 הצרפתית", 38: "בונדסליגה האוסטרית", 69: "ליגת העל השווייצרית", 67: "ליגה שוודית",
           59: "ליגה נורווגית", 196: "ליגה פולנית", 252: "ליגה קרואטית", 122: "ליגה צ'כית", 212: "ליגה הונגרית",
           189: "ליגה רומנית", 536: "ליגה סעודית", 268: "ליגה ברזילאית", 223: "ליגה יפנית", 120: "ליגה סינית",
           113: "ליגה אוסטרלית", 128: "ליגה לאומית", 9097: "גביע המדינה", 9098: "גביע הטוטו", 50: "יורו",
           9806: "ליגת האומות", 186: "גביע פורטוגל", 187: "גביע הליגה הפורטוגלי", 149: "גביע בלגיה",
           137: "גביע סקוטלנד", 180: "גביע הליגה הסקוטי", 278: "גביע אוסטריה", 164: "גביע שווייץ", 198: "גביע פולין",
           190: "גביע רומניה", 213: "גביע הונגריה", 275: "גביע קרואטיה", 9067: "גביע ברזיל", 9011: "גביע הקיסר",
           224: "גביע הליגה היפני", 206: "גביע נורבגיה", 143: "גביע פינלנד", 217: "גביע איסלנד", 174: "גביע סלובניה",
           271: "גביע בולגריה", 330: "גביע קפריסין", 9942: "גביע המלך הסעודי", 11018: "גביע האמיר", 111: "ליגה הולנדית שנייה",
           185: "ליגה פורטוגלית 2", 215: "ליגה איסלנדית", 8983: "ליגה אינדונזית", 51: "ליגה פינית", 173: "ליגה סלובנית",
           270: "ליגה בולגרית", 136: "ליגה קפריסאית", 248: "ליגה אסטונית", 226: "ליגה לטבית", 228: "ליגה ליטאית",
           535: "ליגה קטארית", 164: "גביע שווייץ"}


def get(url, headers=UA):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def load(p):
    return json.loads(p.read_text()) if p.exists() else {}


# ---------- שמות קבוצות בעברית: מילון → ויקידאטה ----------
def wikidata_he(name, hint):
    try:
        r = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            dict(action="wbsearchentities", search=name, language="en", type="item", limit=5, format="json")), WD_UA)
        ids = [x["id"] for x in r.get("search", []) if hint in (x.get("description") or "").lower()]
        if not ids:
            return None
        e = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            dict(action="wbgetentities", ids=ids[0], props="labels", languages="he", format="json")), WD_UA)
        return e["entities"][ids[0]]["labels"].get("he", {}).get("value")
    except Exception:
        return None


def short(p):
    """שם קצר לשחקן כמו באפליקציות (שם משפחה באנגלית)."""
    return (p.get("lastName") or p["name"].split()[-1]).strip()


def he_team(t, cache):
    from teams_seed import HE
    if t["name"] in HE:
        return HE[t["name"]]
    key = str(t["id"])
    if key not in cache or cache[key] == t["name"]:
        cache[key] = wikidata_he(t["name"], "football") or wikidata_he(t["name"] + " FC", "football") or t["name"]
    return cache[key]


# ---------- נתונים ----------
def match_data(mid):
    d = get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}")
    g, c, h = d["general"], d["content"], d["header"]
    teams = load(TEAMS)
    lu = c.get("lineup") or {}
    sides = []
    for i, side in enumerate(("homeTeam", "awayTeam")):
        t = lu.get(side) or {}
        tid = h["teams"][i]["id"]
        team = {"id": tid, "name": h["teams"][i]["name"]}
        starters = [dict(n=short(p), pid=p["id"], pos=p.get("positionId", 0), num=p.get("shirtNumber", ""), x=p["verticalLayout"]["x"],
                         y=p["verticalLayout"]["y"], rating=(p.get("performance") or {}).get("rating"))
                    for p in t.get("starters", []) if p.get("verticalLayout")]
        playing = {p["id"] for p in t.get("starters", []) + t.get("subs", [])}
        out = [dict(n=short(p), why="פציעה" if (p.get("unavailability") or {}).get("type") == "injury" else "הרחקה"
                    if "suspen" in json.dumps(p.get("unavailability") or {}) else "בספק")
               for p in t.get("unavailable", []) if p["id"] not in playing]
        sides.append(dict(id=tid, name=he_team(team, teams), formation=t.get("formation", ""),
                          logo=f"https://images.fotmob.com/image_resources/logo/teamlogo/{tid}.png",
                          color=g.get("teamColors", {}).get("darkMode", {}).get("home" if i == 0 else "away", "#444"),
                          starters=starters, out=out, score=h["teams"][i].get("score")))
    TEAMS.write_text(json.dumps(teams, ensure_ascii=False, indent=0))
    utc = g.get("matchTimeUTCDate") or h.get("status", {}).get("utcTime")
    il = time.localtime(calendar.timegm(time.strptime(utc[:16], "%Y-%m-%dT%H:%M")))  # TZ=Asia/Jerusalem
    stats = {}
    for grp in ((((c.get("stats") or {}).get("Periods") or {}).get("All") or {}).get("stats") or []):
        for s in grp.get("stats", []):
            if s.get("key") and s.get("stats") and None not in s["stats"]:
                stats.setdefault(s["key"], s["stats"])
    ev = h.get("events") or {}
    goals = []
    for i, k in enumerate(("homeTeamGoals", "awayTeamGoals")):
        g_ = []
        for lst in (ev.get(k) or {}).values():
            for e in lst:
                tag = " (ע)" if e.get("ownGoal") else (" (פ)" if "penalty" in (e.get("goalDescriptionKey") or "") else "")
                t_ = f"{e.get('time')}" + (f"+{e['overloadTime']}" if e.get("overloadTime") else "")
                g_.append(dict(n=(e.get("lastName") or e.get("nameStr", "")) + tag, t=t_, sort=e.get("time", 0)))
        goals.append(sorted(g_, key=lambda x: x["sort"]))
    potm = (c.get("matchFacts") or {}).get("playerOfTheMatch") or {}
    potm = dict(n=potm["name"]["lastName"] if potm.get("name") else "", pid=potm.get("id"), r=(potm.get("rating") or {}).get("num"),
                side=0 if potm.get("teamId") == sides[0]["id"] else 1) if potm.get("id") else None
    mom = [x["value"] for x in ((c.get("momentum") or {}).get("main") or {}).get("data", [])]
    return dict(goals=goals, potm=potm, momentum=mom, id=mid, league=LEAGUES.get(g.get("parentLeagueId"), LEAGUES.get(g.get("leagueId"), g.get("leagueName", ""))),
                round=g.get("matchRound", ""), time=time.strftime("%H:%M", il), teams=sides,
                finished=h.get("status", {}).get("finished", False), stats=stats,
                lineup_type=lu.get("lineupType"))


def shoot(page, out_jpg):
    """צילום 1080x1920 בחדות כפולה והקטנה — טקסט ותמונות חדים."""
    png = out_jpg.with_suffix(".png")
    subprocess.run([str(CHROME), "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--window-size=1080,1920",
                    "--force-device-scale-factor=2", "--virtual-time-budget=9000", f"--screenshot={png}", page.as_uri()],
                   capture_output=True, check=True)
    from PIL import Image
    Image.open(png).convert("RGB").resize((1080, 1920), Image.LANCZOS).save(out_jpg, quality=95)
    png.unlink()


def render(kind, data):
    out = HERE / "wolf-stories" / f"{data['id']}_{kind}"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "wolf.jpg", out / "wolf.jpg")
    html = (HERE / f"{kind}.html").read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
    page = out / "page.html"
    page.write_text(html)
    shoot(page, out / "story.jpg")
    a, b = data["teams"]
    cap = {"lineup": f"ההרכבים: {a['name']} – {b['name']} 🐺", "fulltime": f"סיום: {a['name']} {a['score']}-{b['score']} {b['name']} 🐺"}[kind]
    (out / "post.md").write_text(f"## כיתוב לאינסטגרם\n{cap}\n")
    return out


if __name__ == "__main__":
    kind, mid = sys.argv[1], sys.argv[2]
    print(render(kind, match_data(mid)))
