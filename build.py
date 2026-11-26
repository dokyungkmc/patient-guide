#!/usr/bin/env python3
"""도경한의원 환자 안내 페이지 생성기.

노션 '근골격 진단·생활관리 콘텐츠 창고'를 읽어 질환별 정적 페이지를 만듭니다.

  NOTION_TOKEN=... python3 build.py              # 노션에서 읽어 site/ 생성
  python3 build.py --from-json data/             # 저장해 둔 JSON으로 생성 (시험용)
  python3 build.py --dump data/                  # 노션 내용을 JSON으로 저장만
  python3 build.py --all-videos                  # 영상 승인·환자 공개 무시 (내부 미리보기 전용, 공개 배포 금지)

URL 규칙: <BASE_URL>/<콘텐츠 ID 소문자>/  예) MSK-DX-2 → /patient-guide/msk-dx-2/
노출 규칙: 질환·생활관리·재활운동은 검수 상태 '사용중'만. 영상 플레이어는 영상 승인='승인' 이고 환자 공개 체크된 것만.
"""
import argparse, html, json, os, re, shutil, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE_URL = os.environ.get("BASE_URL", "https://dokyungkmc.github.io/patient-guide")
CLINIC = "도경한의원"

DS = {  # 노션 data source ID
    "region": "41b9d360-61a2-8175-8f8e-000bf143d68b",
    "dx": "41b9d360-61a2-8174-a5c7-000b26833c32",
    "ls": "41b9d360-61a2-81ea-ad53-000b62fe64ed",
    "rh": "41b9d360-61a2-81a0-95a7-000b0701c79d",
}

REGION_ORDER = ["LUMBAR", "PELVIS", "CERVICAL", "SHOULDER", "KNEE", "WRIST_ANKLE"]

# 질환에 '환자용 위험 신호' 칸이 비어 있을 때 쓰는 부위별 기본 문구 (환자용 쉬운 말)
REGION_RED = {
    "LUMBAR": ["소변이나 대변이 잘 안 나오거나 참기 어려울 때", "엉덩이·사타구니 주변 감각이 둔해질 때",
               "발목이나 발가락에 힘이 점점 빠질 때 (발이 끌림)", "열이 나거나, 이유 없이 살이 빠지면서 밤에 누워 있어도 아플 때"],
    "PELVIS": ["열이 나면서 엉덩이·골반이 아플 때", "다리에 체중을 실을 수 없을 만큼 사타구니가 아플 때",
               "소변·대변 보기가 어렵거나 다리 힘이 빠질 때", "이유 없이 살이 빠지면서 밤에 누워 있어도 아플 때"],
    "CERVICAL": ["갑자기 생애 가장 심한 두통이 올 때", "열이 나면서 목이 뻣뻣해 고개를 숙이기 어려울 때",
                 "팔이나 다리에 힘이 빠지거나, 양손이 함께 저리고 단추 잠그기가 어려울 때",
                 "어지럽거나, 말이 어눌해지거나, 물체가 두 개로 보일 때"],
    "SHOULDER": ["다친 뒤 팔을 전혀 들 수 없을 때", "어깨가 붓고 뜨거우며 열이 날 때",
                 "왼쪽 어깨 통증과 함께 가슴이 답답하거나 식은땀이 날 때", "밤마다 심해지는 통증과 함께 살이 빠질 때"],
    "KNEE": ["무릎이 갑자기 크게 붓고 뜨거우며 열이 날 때", "다친 뒤 다리에 체중을 실을 수 없을 때",
             "무릎이 걸려서 끝까지 펴지지 않을 때", "종아리까지 붓고 아플 때"],
    "WRIST_ANKLE": ["다친 뒤 체중을 싣거나 손을 짚을 수 없을 때", "손발이 저리고 차가우며 색이 창백해질 때",
                    "붓고 붉으며 뜨겁고 열이 날 때", "근육이 마르거나 감각이 아예 없어질 때"],
}

STAGE = {
    "급성기(0~2주)": ("s1", "통증기 0~2주"),
    "아급성기(2~6주)": ("s2", "회복 중 2~6주"),
    "회복기(6주~)": ("s3", "6주 이후"),
    "재발 예방": ("s4", "재발 예방"),
}

# ---------------------------------------------------------------- Notion

def notion(path, body=None):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("NOTION_TOKEN 환경변수가 필요합니다.")
    req = urllib.request.Request("https://api.notion.com/v1/" + path,
                                 data=json.dumps(body or {}).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Notion-Version", "2025-09-03")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"노션 오류 {e.code} ({path}): {e.read().decode()[:500]}")


def fetch_all(ds_id):
    rows, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = notion(f"data_sources/{ds_id}/query", body)
        rows += r["results"]
        if not r.get("has_more"):
            return rows
        cursor = r["next_cursor"]


def val(page, name):
    p = page["properties"].get(name)
    if not p:
        return None
    t = p["type"]
    v = p[t]
    if t in ("title", "rich_text"):
        return "".join(x["plain_text"] for x in v).strip()
    if t in ("select", "status"):
        return v["name"] if v else None
    if t == "multi_select":
        return [x["name"] for x in v]
    if t == "relation":
        return [x["id"].replace("-", "") for x in v]
    if t == "unique_id":
        return f'{v["prefix"]}-{v["number"]}' if v.get("prefix") else str(v["number"])
    if t in ("checkbox", "url", "number"):
        return v
    return None

# ---------------------------------------------------------------- 정리

def load(src=None):
    data = {}
    for k, ds in DS.items():
        if src:
            data[k] = json.loads((Path(src) / f"{k}.json").read_text())
        else:
            data[k] = fetch_all(ds)
    return data


def yt(url):
    if not url:
        return None, 0
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    if not m:
        return None, 0
    t = re.search(r"[?&]t=(\d+)", url)
    return m.group(1), int(t.group(1)) if t else 0


def item(page, kind, all_videos):
    g = lambda n: val(page, n)
    how = g("방법" if kind == "rh" else "실천 방법") or ""
    lines = [re.sub(r"^\s*(\d+[\).]|[-•])\s*", "", x).strip() for x in how.splitlines()]
    vid, start = yt(g("유튜브 URL"))
    show_video = bool(vid) and (all_videos or (g("영상 승인") == "승인" and g("환자 공개") is True))
    return {
        "id": page["id"].replace("-", ""),
        "title": g("항목명"),
        "kind": g("운동 종류") if kind == "rh" else g("분류"),
        "desc": g("환자용 설명") or "",
        "how": [x for x in lines if x],
        "dose": g("횟수·빈도") if kind == "rh" else None,
        "when": g("적용 시점") if kind == "ls" else None,
        "stop": g("주의사항·중단 신호" if kind == "rh" else "주의사항·연락 신호") or "",
        "stages": g("회복 단계") or [],
        "channel": g("채널명") or "",
        "video": vid if show_video else None,
        "start": start,
        "ok": g("검수 상태") == "사용중",
    }


def build_model(data, all_videos=False):
    regions = {p["id"].replace("-", ""): {"code": val(p, "부위 코드"), "name": val(p, "부위명")} for p in data["region"]}
    items = {}
    for kind in ("ls", "rh"):
        for p in data[kind]:
            it = item(p, kind, all_videos)
            items[it["id"]] = (kind, it)
    diseases = []
    for p in data["dx"]:
        if val(p, "검수 상태") != "사용중":
            continue
        g = lambda n: val(p, n)
        reg = next((regions[r] for r in (g("부위") or []) if r in regions), {"code": "", "name": ""})
        ls = [items[i][1] for i in (g("생활관리") or []) if i in items and items[i][1]["ok"]]
        rh = [items[i][1] for i in (g("재활운동") or []) if i in items and items[i][1]["ok"]]
        rh.sort(key=lambda x: (x["kind"] == "따라하기 루틴", min([list(STAGE).index(s) for s in x["stages"] if s in STAGE] or [9])))
        red = g("환자용 위험 신호")
        diseases.append({
            "cid": g("콘텐츠 ID"),
            "slug": g("콘텐츠 ID").lower(),
            "name": g("질환명"),
            "region": reg,
            "desc": g("환자용 설명") or "",
            "course": g("예상 경과") or "",
            "visits": g("주차별 내원 주기") or "",
            "dur": g("예상 치료기간") or "",
            "rank": g("다빈도 순위") or 99,
            "red": [x.strip(" -•") for x in red.splitlines() if x.strip()] if red else REGION_RED.get(reg["code"], []),
            "ls": ls, "rh": rh,
        })
    diseases.sort(key=lambda d: (REGION_ORDER.index(d["region"]["code"]) if d["region"]["code"] in REGION_ORDER else 9, d["rank"]))
    return diseases

# ---------------------------------------------------------------- HTML

e = lambda s: html.escape(s or "", quote=True)


def split_name(name):
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", name)
    return (m.group(1), m.group(2)) if m else (name, "")


def visits_html(text):
    out, group = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            out.append(f'<li class="tl-group">{e(line[1:-1])}</li>')
            continue
        m = re.match(r"^([^:]+):\s*(.*)$", line)
        label, rest = (m.group(1), m.group(2)) if m else (line, "")
        n = re.match(r"^(.*?)\s*\((.*)\)\s*$", rest)
        freq, note = (n.group(1), n.group(2)) if n else (rest, "")
        out.append('<li><span class="dot"></span><div class="tl-body"><div class="tl-head">'
                   f'<h3>{e(label)}</h3>' + (f'<span class="visit">{e(freq)}</span>' if freq else "") +
                   '</div>' + (f'<p class="small muted">{e(note)}</p>' if note else "") + '</div></li>')
    return '<ol class="timeline">' + "".join(out) + "</ol>"


PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l13-7.5z"/></svg>'
YTI = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.6 7.2a2.5 2.5 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4A2.5 2.5 0 0 0 2.4 7.2 26 26 0 0 0 2 12a26 '
       '26 0 0 0 .4 4.8 2.5 2.5 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8A26 26 0 0 0 22 12a26 26 0 0 0-.4-4.8zM10 15V9l5.2 3z"/></svg>')


def mmss(s):
    return f"{s // 60}분 {s % 60}초" if s % 60 else f"{s // 60}분"


def card(it, kind):
    chips = "".join(f'<span class="chip {STAGE[s][0]}">{STAGE[s][1]}</span>' for s in it["stages"] if s in STAGE)
    player = ""
    if it["video"]:
        note = f"영상 {mmss(it['start'])}부터 재생됩니다" if it["start"] else "눌러서 영상 보기"
        player = (f'<div class="player"><button class="poster" type="button" data-id="{it["video"]}" data-start="{it["start"]}" '
                  f'style="background-image:url(https://i.ytimg.com/vi/{it["video"]}/hqdefault.jpg)" aria-label="{e(it["title"])} 영상 재생">'
                  f'<span class="play">{PLAY}</span><span class="pfoot">{e(note)}</span></button></div>')
    how = ""
    if it["how"]:
        how = (f'<details{" open" if kind == "rh" else ""}><summary>{"하는 방법" if kind == "rh" else "실천 방법"}</summary>'
               '<ol class="how small">' + "".join(f"<li>{e(x)}</li>" for x in it["how"]) + "</ol></details>")
    return ('<article class="card">' + player + '<div class="card-body">'
            + (f'<div class="stagechips">{chips}</div>' if chips else "")
            + f'<h3>{e(it["title"].replace("[루틴]", "따라 하기:").strip())}</h3>'
            + (f'<div class="channel">{YTI}<span>{e(it["channel"])}</span></div>' if it["video"] and it["channel"] else "")
            + (f'<p>{e(it["desc"])}</p>' if it["desc"] else "") + how
            + (f'<p class="small"><span class="muted">횟수</span> <b>{e(it["dose"])}</b></p>' if it.get("dose") else "")
            + (f'<p class="small"><span class="muted">언제</span> <b>{e(it["when"])}</b></p>' if it.get("when") else "")
            + (f'<p class="stop"><b>{"멈춰야 할 때" if kind == "rh" else "주의"}</b> {e(it["stop"])}</p>' if it["stop"] else "")
            + "</div></article>")


def figure(d):
    f = ROOT / "figures" / f'{d["slug"]}.svg'
    if f.exists():
        svg = f.read_text()
        cap = (ROOT / "figures" / f'{d["slug"]}.txt')
        cap = cap.read_text().strip() if cap.exists() else ""
    else:
        svg = body_map(d["region"]["code"])
        cap = f'아픈 부위: {d["region"]["name"]}'
    return f'<figure>{svg}' + (f'<figcaption>{e(cap)}</figcaption>' if cap else "") + '</figure>'


def body_map(code):
    """뒤에서 본 사람 모양에 부위를 표시한 그림"""
    spots = {
        "LUMBAR": [(100, 150, 22)], "PELVIS": [(82, 178, 16), (118, 178, 16)], "CERVICAL": [(100, 62, 14)],
        "SHOULDER": [(64, 82, 15), (136, 82, 15)], "KNEE": [(84, 262, 13), (116, 262, 13)],
        "WRIST_ANKLE": [(42, 196, 10), (158, 196, 10), (86, 330, 10), (114, 330, 10)],
    }.get(code, [])
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="{r + 8}" fill="var(--warn)" opacity=".18"/><circle cx="{x}" cy="{y}" r="{r}" fill="var(--warn)" opacity=".55"/>' for x, y, r in spots)
    return ('<svg class="bodymap" viewBox="0 0 200 350" role="img" aria-label="뒤에서 본 사람 모양에 아픈 부위를 표시한 그림">'
            '<g fill="var(--line)" stroke="var(--muted)" stroke-width="1.5">'
            '<circle cx="100" cy="32" r="22"/>'
            '<path d="M88 52 h24 v14 h-24z"/>'
            '<path d="M62 70 Q100 62 138 70 Q148 74 148 86 L140 160 Q138 176 124 180 L76 180 Q62 176 60 160 L52 86 Q52 74 62 70z"/>'
            '<path d="M52 80 Q44 84 42 96 L36 190 Q36 200 44 200 Q50 200 50 190 L60 104z"/>'
            '<path d="M148 80 Q156 84 158 96 L164 190 Q164 200 156 200 Q150 200 150 190 L140 104z"/>'
            '<path d="M72 176 L98 182 L96 330 Q96 340 86 340 Q76 340 76 330 L70 190z"/>'
            '<path d="M128 176 L102 182 L104 330 Q104 340 114 340 Q124 340 124 330 L130 190z"/>'
            '</g><path d="M100 66 V176" stroke="var(--muted)" stroke-width="1.2" stroke-dasharray="3 4" fill="none"/>'
            + dots + '</svg>')


def page(d, css_v):
    main, sub = split_name(d["name"])
    url = f'{BASE_URL}/{d["slug"]}/'
    og = f'{BASE_URL}/og/{d["region"]["code"].lower()}.png'
    sec = []
    sec.append('<section id="what"><span class="eyebrow">어떤 상태인가요</span>'
               f'<div class="panel">{figure(d)}' + "".join(f"<p>{e(s)}</p>" for s in re.split(r"(?<=\.)\s+", d["desc"]) if s) + '</div></section>')
    course = ('<section id="course"><span class="eyebrow">회복 과정과 내원 주기</span>'
              + (f'<h2>보통 {e(d["dur"])} 정도 치료합니다</h2>' if d["dur"] else "<h2>회복 과정</h2>")
              + (f'<p class="muted">{e(d["course"])}</p>' if d["course"] else "")
              + (f'<div class="panel">{visits_html(d["visits"])}</div>' if d["visits"] else "")
              + '<p class="small muted">내원 횟수는 회복 속도에 따라 원장님이 조정합니다.</p></section>')
    sec.append(course)
    if d["ls"]:
        sec.append('<section id="life"><span class="eyebrow">생활 관리</span><h2>생활에서 이렇게 해 주세요</h2>'
                   + "".join(card(x, "ls") for x in d["ls"]) + '</section>')
    if d["rh"]:
        sec.append('<section id="exercise"><span class="eyebrow">재활운동</span><h2>회복 단계에 맞춰 하나씩 늘려 가요</h2>'
                   '<p class="muted small">원장님이 알려 드린 단계의 운동만 해 주세요. 색 표시는 언제 하는 운동인지 알려 줍니다.</p>'
                   + "".join(card(x, "rh") for x in d["rh"]) + '</section>')
    if d["red"]:
        sec.append('<section id="call" class="red"><h2>이럴 땐 바로 연락하거나 병원에 가세요</h2><ul>'
                   + "".join(f"<li>{e(x)}</li>" for x in d["red"]) + '</ul></section>')
    toc = [("what", "어떤 상태인가요"), ("course", "회복 과정·내원")] + \
          ([("life", "생활 관리")] if d["ls"] else []) + ([("exercise", "재활운동")] if d["rh"] else []) + \
          ([("call", "바로 연락할 때")] if d["red"] else [])
    title = f"{main} 안내 | {CLINIC}"
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{e(title)}</title>
<meta property="og:type" content="article">
<meta property="og:title" content="{e(main)} 생활 안내 | {CLINIC}">
<meta property="og:description" content="회복 과정, 내원 주기, 생활 관리, 집에서 하는 재활운동">
<meta property="og:image" content="{og}">
<meta property="og:url" content="{url}">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="../assets/style.css?v={css_v}">
</head><body><div class="wrap">
<header><div class="clinic"><i></i>{CLINIC} · 진료 후 안내</div>
<h1>{e(main)}</h1>{f'<p class="sub">{e(sub)}</p>' if sub else ''}
<p class="lead">오늘 진료에서 말씀드린 내용을 정리했습니다. 집에서 천천히 다시 읽어 보시고, 영상을 보며 따라 해 보세요.</p>
<nav class="toc" aria-label="바로가기">{"".join(f'<a href="#{a}">{b}</a>' for a, b in toc)}</nav></header>
{"".join(sec)}
<footer><p>이 안내문은 진료를 돕기 위한 일반 정보입니다. 증상과 운동 단계는 사람마다 다르니 진료 때 꼭 상의해 주세요.</p>
<p>영상은 각 채널이 유튜브에 공개한 자료를 연결한 것이며, 저작권은 각 채널에 있습니다.</p></footer>
</div><script src="../assets/app.js?v={css_v}"></script></body></html>
"""


def index(diseases, css_v):
    groups = {}
    for d in diseases:
        groups.setdefault(d["region"]["name"], []).append(d)
    body = "".join(f'<section><h2>{e(g)}</h2><div class="list">' +
                   "".join(f'<a href="{d["slug"]}/">{e(split_name(d["name"])[0])}<span>{e(split_name(d["name"])[1])}</span></a>' for d in ds) +
                   '</div></section>' for g, ds in groups.items())
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="robots" content="noindex">
<title>{CLINIC} 진료 후 안내</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="assets/style.css?v={css_v}"></head><body><div class="wrap">
<header><div class="clinic"><i></i>{CLINIC}</div><h1>진료 후 안내</h1>
<p class="lead">원장님께 받은 안내 링크로 들어오시면 됩니다.</p></header>{body}</div></body></html>
"""


def patch(page_id, props):
    token = os.environ.get("NOTION_TOKEN")
    req = urllib.request.Request(f"https://api.notion.com/v1/pages/{page_id}", data=json.dumps({"properties": props}).encode(), method="PATCH")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Notion-Version", "2025-09-03")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()


def write_urls(data, diseases):
    """질환 DB의 '환자 안내 페이지 URL' 칸을 공개 주소로 채움 (값이 다를 때만)"""
    want = {d["cid"]: f'{BASE_URL}/{d["slug"]}/' for d in diseases}
    n = 0
    for p in data["dx"]:
        cid = val(p, "콘텐츠 ID")
        if "환자 안내 페이지 URL" not in p["properties"]:
            sys.exit("질환 DB에 '환자 안내 페이지 URL' 칸이 없습니다.")
        cur = val(p, "환자 안내 페이지 URL")
        new = want.get(cid)  # 사용중이 아니면 비움
        if cur != new:
            patch(p["id"], {"환자 안내 페이지 URL": {"url": new}})
            n += 1
    print(f"노션 URL 칸 갱신 {n}건")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-urls", action="store_true", help="노션 질환 DB에 공개 주소 기록 (공개 배포 후)")
    ap.add_argument("--from-json")
    ap.add_argument("--dump")
    ap.add_argument("--all-videos", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "site"))
    a = ap.parse_args()
    data = load(a.from_json)
    if a.dump:
        Path(a.dump).mkdir(parents=True, exist_ok=True)
        for k, v in data.items():
            (Path(a.dump) / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False))
        print("저장:", a.dump)
        return
    diseases = build_model(data, a.all_videos)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "assets", out / "assets")
    if (ROOT / "og").exists():
        shutil.copytree(ROOT / "og", out / "og")
    css_v = str(int((ROOT / "assets" / "style.css").stat().st_mtime))
    for d in diseases:
        (out / d["slug"]).mkdir(parents=True)
        (out / d["slug"] / "index.html").write_text(page(d, css_v))
    (out / "index.html").write_text(index(diseases, css_v))
    (out / "oauth.html").write_text((ROOT / "assets" / "oauth.html").read_text())
    (out / ".nojekyll").write_text("")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (out / "pages.json").write_text(json.dumps(
        [{"id": d["cid"], "name": d["name"], "url": f'{BASE_URL}/{d["slug"]}/',
          "videos": sum(1 for x in d["ls"] + d["rh"] if x["video"])} for d in diseases], ensure_ascii=False, indent=1))
    n_vid = sum(1 for d in diseases for x in d["ls"] + d["rh"] if x["video"])
    if a.write_urls:
        if a.all_videos or a.from_json:
            sys.exit("--write-urls 는 노션에서 읽은 공개용 빌드에서만 씁니다.")
        write_urls(data, diseases)
    print(f"질환 페이지 {len(diseases)}개, 영상 {n_vid}개 → {out}" + ("  [내부 미리보기: 모든 영상 포함]" if a.all_videos else ""))


if __name__ == "__main__":
    main()
