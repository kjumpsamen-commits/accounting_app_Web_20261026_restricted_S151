"""
S13 Web：讀取「結轉」之後的資料庫（Web 不改程式，只更新共用的 database.py／manager.py）
  完整版：首頁、記帳、API 只看到新帳本（期初＝轉出、收入支出 0）
  兩版：月費、特殊收費與結轉前相同；被刪除的停用人員在活動裡顯示為臨時人員，金額不變
"""
import re

import pytest


@pytest.fixture
def rolled(desktop_db, monkeypatch, tmp_path):
    import database as database_module
    from special_charge import SpecialChargeManager
    d = desktop_db                                   # 已有：2026-07-01 收入 5000；王小明（已繳）、李小華；活動「校外教學」
    d.add_transaction("expense", 1200, "交通", "", "2026-07-05")
    m = SpecialChargeManager(d.conn)
    aid = m.list_activities()[0]["id"] if hasattr(m, "list_activities") else 1
    before = {"recv": m.get_activity_total_receivable(aid), "coll": m.get_activity_collected(aid)}
    lee = d.conn.execute("SELECT id FROM rent_tenants WHERE name='李小華'").fetchone()[0]
    d.conn.execute("UPDATE rent_tenants SET active=0 WHERE id=?", (lee,))
    d.conn.commit()
    r = d.apply_rollover("2026-07-31", delete_tenant_ids=[lee])
    d.rolled = r
    d.aid, d.before, d.mgr = aid, before, m
    return d


def _ok(client, url):
    r = client.get(url)
    if r.status_code == 404:
        pytest.skip(f"{url} 不在這個版本")
    assert r.status_code == 200, url
    return r


def test_summary_is_new_book(client, rolled):
    r = _ok(client, "/api/transactions/summary").json()
    assert (r["total_opening"], r["total_income"], r["total_expense"], r["balance"], r["count"]) == \
        (3800, 0, 0, 3800, 1)


def test_dashboard_and_transactions_show_opening_only(client, rolled):
    h = _ok(client, "/").text
    assert "另有期初 NT$3,800" in h
    t = _ok(client, "/transactions?date_from=2026-01-01&date_to=2026-12-31").text
    assert "前期轉入（封存帳本 帳本_20260701-20260731）" in t
    assert "交通" not in re.sub(r"<option[^>]*>[^<]*</option>", "", t)       # 舊記帳不在新帳本


def test_special_charge_guest_after_rollover(client, rolled):
    urls = [u for u in ("/special-charge", "/restricted/special-charge") if client.get(u).status_code == 200]
    for base in urls:
        h = _ok(client, f"{base}?year=2026&activity_id={rolled.aid}").text
        assert "李小華" in h and "（臨時）" in h
        assert f"應收：<strong>${rolled.before['recv']:,.0f}</strong>" in h
        assert f"已收：<strong>${rolled.before['coll']:,.0f}</strong>" in h


def test_rent_page_after_rollover(client, rolled):
    urls = [u for u in ("/rent", "/restricted/rent") if client.get(u).status_code == 200]
    for base in urls:
        h = _ok(client, f"{base}?year=2026&month=7").text
        assert "王小明" in h and "李小華" not in h
