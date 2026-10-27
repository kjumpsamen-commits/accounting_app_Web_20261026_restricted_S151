# 個人記帳簿 Web（唯讀查詢）

> 版本：20261027 V3.12（S15.1）

FastAPI＋Jinja2＋SQLite。從 Google Drive 下載桌面版的 `data.db`，**只讀不寫**。
同一份程式有兩個 zip，差別只在 `web/edition.py`：

| zip | 版本別 | 用途 |
|---|---|---|
| `accounting_app_v996_V2_Web_special_charge_v6_*.zip` | 完整版 | 管帳的人查看所有資料 |
| `accounting_app_v996_V2_Web_special_charge_v6_restricted_*.zip` | 簡易版（受限） | 給成員、家長：整站只開放「繳費狀況」「特殊收費」 |

目前是哪一版：看頁尾「版本 …｜完整版／簡易版（受限）」、「關於」頁或 `/api/health`。

## 本機執行

```bash
pip install -r requirements.txt
AUTO_DOWNLOAD=false DB_LOCAL_PATH=/path/to/data.db uvicorn web.app:app --port 8000
```

打開 http://127.0.0.1:8000/ ；頁尾「說明」是網頁版說明（完整版 11 個主題、簡易版 2 個主題）。

## 部署到 Render

1. 解開 zip，把 `accounting_app_v996_V2_Web/` **裡面的內容**放到該網站的 GitHub repo（私人 repo），repo 根目錄直接看到 `render.yaml`。
2. Render 會依 `render.yaml` 部署（`uvicorn web.app:app`，健康檢查 `/api/health`）。
3. 部署後確認頁尾版本與版本別；簡易版打開網址根目錄應轉到繳費狀況。

## 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `ADMIN_USERNAME`、`ADMIN_PASSWORD_HASH` | 要用管理頁時 | 管理帳號與密碼的 bcrypt 雜湊 |
| `GDRIVE_FILE_ID` | 建議 | Google Drive 上 data.db 的 File ID（公開連結模式，推薦） |
| `GDRIVE_FOLDER_ID`、`GDRIVE_SERVICE_ACCOUNT` | 否 | Service Account 模式（需要 Google Cloud，不建議） |
| `SYNC_INTERVAL_MINUTES` | 否 | 同步間隔，預設 30 |
| `AUTO_DOWNLOAD` | 否 | 啟動時下載，預設 true |
| `DB_LOCAL_PATH` | 否 | 暫存資料庫位置，預設 `/tmp/accounting.db` |
| `RESTRICTED_SITE` | **不要設定** | 只供測試；簡易版沒設定時就是整站受限 |

產生密碼雜湊（本機）：

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'你的密碼', bcrypt.gensalt()).decode())"
```

File ID 的優先順序：環境變數 `GDRIVE_FILE_ID` ＞ `web/config/config.yaml` ＞ `web/config/settings.py` 預設值。
交接換檔案時只要改 Render 的 `GDRIVE_FILE_ID`；登入後管理設定 ›「資料來源說明」有逐步說明。

## 同步流程

```
下載到暫存檔 → 檢查是有效的 SQLite、含記帳資料表 → 取代目前的資料庫（不必重新啟動）
任何一步失敗 → 保留原本的資料庫，記錄在 Log
```

## 測試

```bash
python -m pytest -q tests
```

完整版會自動略過 `/restricted` 相關測試；簡易版全部執行。

## 文件

`docs/` 放 Web 相關的 4 份：01 系統總覽、04 程式架構、07 建置與部署、08 交接手冊。
完整的 10 份文件（含資料庫結構、業務規則、版本紀錄、測試指南、修改流程）在桌面版 zip 的 `docs/`；
這 4 份裡指向其他文件的連結，請到桌面版 zip 查看。
