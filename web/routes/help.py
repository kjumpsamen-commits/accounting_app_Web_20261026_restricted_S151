"""S14：網頁版「說明」頁（公開頁面）。

內容來自 help_content.py（與桌面版同一份，三版逐檔相同）：
  ・/help（完整版）：網頁相關的主題（兩個網站的差別、更新頻率、各頁說明、管理設定…）
  ・/restricted/help（簡易版）：只有「繳費狀況」「特殊收費」兩個主題
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from web.utils.db import ReadOnlyDB, get_db
from web.services.query import get_app_title
from web.utils.templates import templates as _T

router = APIRouter(tags=["頁面"])


@router.get("/help", response_class=HTMLResponse)
def help_page(request: Request, db: ReadOnlyDB = Depends(get_db)):
    import help_content as hc
    restricted = request.url.path.startswith("/restricted")
    ids = hc.web_topic_ids("restricted" if restricted else "full")
    return _T.TemplateResponse(request, "help.html", {
        "page":      "help",
        "app_title": get_app_title(db),
        "help_body": hc.html_fragment(ids, searchable=not restricted,
                                      search_placeholder="搜尋：例如「繳費」「更新」「特殊收費」"),
        "restricted": restricted,
    })
