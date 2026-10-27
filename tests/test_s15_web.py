"""
S15 Web：月費逾期、特殊收費繳收期限、已完成排到下方、關於的帳本名稱
  完整版：逾期提示列（可展開明細）、「⚠尚未繳納 N 個月」、過去月份「⚠ 逾期未繳」、首頁逾期人數
  簡易版：只有過去月份「⚠ 逾期未繳」，沒有月數、提示列與明細（你的決定 Q6 A）
  兩版：未完成在上、已完成在下；特殊收費期限欄、提示列、未繳者反色；讀未升級（沒有 due_date）的資料庫也正常
月份都以「今天」往前推算。
"""
import re
from datetime import date, timedelta

import pytest


def ym_add(ym, n):
    y, m = divmod(ym, 100)
    t = y * 12 + (m - 1) + n
    return (t // 12) * 100 + t % 12 + 1


@pytest.fixture
def s15(desktop_db):
    from database import last_overdue_ym
    from special_charge import SpecialChargeManager
    d = desktop_db
    d.add_fee_schedule(202001, 3000)
    L = last_overdue_ym()
    a = d.add_tenant("逾甲", None, grade="三年級", start_ym=ym_add(L, -1))   # L-1、L 未繳 → 2 個月
    b = d.add_tenant("繳乙", None, grade="六年級", start_ym=L)
    y, m = divmod(L, 100)
    d.set_payment_status(b, y, m, "paid", paid_date=f"{y}-{m:02d}-01")
    mgr = SpecialChargeManager(d.conn)
    t = date.today()
    aid = mgr.create_activity("逾期活動", (t - timedelta(days=20)).isoformat(), due_date=(t - timedelta(days=3)).isoformat())
    pa = mgr.add_member(aid, a); mgr.add_item(pa, "報名", 500, 1)
    pb = mgr.add_member(aid, b); mgr.add_item(pb, "報名", 500, 1); mgr.mark_paid(pb, paid_date=t.isoformat())
    d.L, d.aid, d.year = L, aid, str(t - timedelta(days=20))[:4]
    return d


def _get(client, url):
    r = client.get(url)
    if r.status_code == 404:
        pytest.skip(f"{url} 不在這個版本")
    assert r.status_code == 200, url
    return r.text


def _table(h):
    return h[h.find("繳費明細"):]


def test_full_rent_page(client, s15):
    y, m = divmod(s15.L, 100)
    h = _get(client, f"/rent?year={y}&month={m}")
    # S15.1：提示列新寫法、姓名旁寫出月份、明細加本月狀態
    from database import overdue_tag
    assert "⚠ 有 1 人超過繳費期限還沒繳（共 2 個月" in h and "查看明細" in h
    assert "每個月的月費，期限是當月最後一天" in h
    assert overdue_tag([ym_add(s15.L, -1), s15.L]) in h and "本月：" in h
    t = _table(h)
    assert t.find("逾甲") < t.find("繳乙")                          # 未繳在上（雖然年級較低）
    assert "⚠ 逾期未繳</span>" in t and "table-danger" in t
    d = _get(client, "/")
    assert "⚠ 逾期 1 人" in d


def test_restricted_rent_page_only_red_status(client, s15):
    y, m = divmod(s15.L, 100)
    h = _get(client, f"/restricted/rent?year={y}&month={m}")
    assert "⚠ 逾期未繳</span>" in h
    from database import overdue_tag
    assert overdue_tag([ym_add(s15.L, -1), s15.L]) not in h and "超過繳費期限" not in h and "查看明細" not in h
    t = _table(h)
    assert t.find("逾甲") < t.find("繳乙")


def test_current_month_not_overdue(client, s15):
    t = date.today()
    for base in ("/rent", "/restricted/rent"):
        r = client.get(f"{base}?year={t.year}&month={t.month}")
        if r.status_code == 404:
            continue
        assert "⚠ 逾期未繳</span>" not in _table(r.text)


def test_special_charge_due_and_alert_both_editions(client, s15):
    seen = 0
    for base in ("/special-charge", "/restricted/special-charge"):
        r = client.get(f"{base}?year={s15.year}&activity_id={s15.aid}")
        if r.status_code == 404:
            continue
        seen += 1
        h = r.text
        assert "繳收期限" in h and '<span class="text-bg-danger rounded px-2 py-1 small fw-semibold">⚠ 逾期 3 天</span>' in h
        assert "⚠ 已超過繳收期限 3 天" in h and "尚有 1 人未繳、未收 $500" in h
        assert '<span class="text-bg-danger rounded px-2 py-1 text-nowrap" title="已超過繳收期限，尚未繳費">逾甲</span>' in h
        body = h[h.find("<th>明細</th>"):]
        assert body.find("逾甲") < body.find("繳乙")                  # 未繳在上
    assert seen >= 1


def test_about_shows_book_name(client, s15):
    for base in ("/about", "/restricted/about"):
        r = client.get(base)
        if r.status_code == 404:
            continue
        assert ">帳本名稱</th>" in r.text and ">程式名稱</th>" not in r.text and "<td>個人記帳簿</td>" in r.text


def test_old_database_without_due_date(client, s15):
    import sqlite3
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("SQLite 太舊")
    s15.conn.execute("ALTER TABLE special_activity DROP COLUMN due_date")
    s15.conn.commit()
    for base in ("/special-charge", "/restricted/special-charge"):
        r = client.get(f"{base}?year={s15.year}&activity_id={s15.aid}")
        if r.status_code == 404:
            continue
        assert r.status_code == 200 and "逾期活動" in r.text and "已超過繳收期限" not in r.text


def test_rule_setting_is_used_by_web(client, s15):
    """S15.1：網頁讀資料檔的繳費期限設定（與桌面同一個設定）。"""
    s15.set_fee_due_rule("next:28")
    t = date.today()
    from database import fee_month_overdue
    y, m = divmod(s15.L, 100)
    expect = fee_month_overdue(y, m, t, "next:28")
    for base in ("/rent", "/restricted/rent"):
        r = client.get(f"{base}?year={y}&month={m}")
        if r.status_code == 404:
            continue
        assert ("⚠ 逾期未繳</span>" in _table(r.text)) == expect
    r = client.get("/rent")
    if r.status_code == 200:
        assert "每個月的月費，期限是隔月 28 日" in r.text or "超過繳費期限" not in r.text
