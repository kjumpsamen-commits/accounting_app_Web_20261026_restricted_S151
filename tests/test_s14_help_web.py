"""
S14 Web：說明頁（完整版 /help、簡易版 /restricted/help），內容來自 help_content.py（與桌面同一份）
  H  完整版說明：網頁相關的主題、頁尾有「說明」連結、可搜尋
  R  簡易版說明：只有「繳費狀況」「特殊收費」兩個主題，所有連結都在頁面內；整站受限時 /help 轉到 /restricted/help
  N  網頁主題中「」內的名稱在網頁樣板中都找得到
"""
import ast
import pathlib
import re
import unicodedata

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _sections(html):
    return re.findall(r'<section class="topic"[^>]*><h2 id="([a-z0-9_]+)"', html)


def _help_body(html):
    return html[html.index('class="card-body help-body"'):html.index("{# S14") if "{# S14" in html else len(html)]


def test_full_help_page(client):
    import help_content as hc
    r = client.get("/help")
    assert r.status_code == 200
    h = r.text
    assert _sections(h) == hc.web_topic_ids("full") and len(_sections(h)) == 11
    assert 'id="help-q"' in h                                     # 可搜尋
    assert "1q9ERU2od" not in h
    assert 'href="/help"' in client.get("/rent").text             # 頁尾連結


def test_restricted_help_page(client):
    if client.get("/restricted/rent").status_code != 200:
        pytest.skip("完整版沒有 /restricted")
    r = client.get("/restricted/help")
    assert r.status_code == 200
    h = r.text
    assert _sections(h) == ["web_simple_rent", "web_simple_sc"]
    body = h[h.index("help-body"):]
    body = body[:body.index("</main>")] if "</main>" in body else body
    for href in re.findall(r'href="([^"]+)"', body):
        assert href.startswith("#"), href                          # 說明內容只連到頁面內
    assert "這個網站只提供查看「繳費狀況」與「特殊收費」" in h
    assert 'href="/restricted/help"' in client.get("/restricted/rent").text


def test_restricted_site_help_whitelist(client, monkeypatch):
    if client.get("/restricted/rent").status_code != 200:
        pytest.skip("完整版沒有 /restricted")
    monkeypatch.setenv("RESTRICTED_SITE", "true")
    r = client.get("/help", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/restricted/help"
    r = client.get("/restricted/help", follow_redirects=False)
    assert r.status_code == 200
    side = r.text[r.text.index('<aside class="sidebar"'):r.text.index("</aside>")]
    labels = [m.strip() for m in re.findall(r'class="nav-link[^"]*"[^>]*>\s*<i[^>]*></i>\s*([^\n<]+)', side)]
    assert labels == ["繳費狀況", "特殊收費"]                      # 說明頁不會多出其他選單
    for p in ("/restricted/helpx", "/restricted/help/../transactions"):
        assert client.get(p, follow_redirects=False).status_code in (303, 404)


def test_web_topic_names_exist_in_templates():
    import help_content as hc
    WILD = "§"

    def nz(s):
        return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))
    texts = []
    for f in sorted((ROOT / "web" / "templates").rglob("*.html")):
        t = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", WILD, f.read_text(encoding="utf-8"), flags=re.S)
        texts += re.split(r"<[^>]+>", t)
    # S15：網頁也顯示 special_charge/manager.py 產生的繳收期限文字（alert_label／alert_banner）
    # S15.1：月費逾期的標示（「⚠ 9月未繳」等）由共用的 database.py 產生
    for f in (ROOT / "web" / "app.py", ROOT / "web" / "edition.py", ROOT / "special_charge" / "manager.py",
              ROOT / "database.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                texts.append(n.value)
            elif isinstance(n, ast.JoinedStr):
                texts.append("".join(v.value if isinstance(v, ast.Constant) else WILD for v in n.values))
    corpus = [nz(t) for t in texts if t.strip()]
    allow = {"版本 20261027 V3.12｜完整版", "簡易版（受限）", "知道連結的任何人都能檢視"}
    split = re.compile(r"(\.\.\.|N|M|X|\d+(?:[,.\-:/]\d+)*)")
    bad = []
    for t in hc.TOPICS:
        if not (t["ch"] == "web" or t["web"]):
            continue
        for m in re.findall(r"「([^「」]+)」", t["body"]):
            if m in allow:
                continue
            parts = split.split(nz(m))
            rx = re.compile("".join(".*" if i % 2 else re.escape(p) for i, p in enumerate(parts)))
            if not any(rx.search(c) for c in corpus):
                bad.append((t["id"], m))
    assert bad == []
