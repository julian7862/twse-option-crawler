# TAIFEX 台指選擇權爬蟲

自動抓取台灣期貨交易所（TAIFEX）每日選擇權市場資料（日盤/夜盤），並儲存至 MongoDB。支援本地開發與 GitHub Actions 自動排程執行。

## 📋 目錄

- [功能特色](#功能特色)
- [專案架構](#專案架構)
- [系統需求](#系統需求)
- [快速開始](#快速開始)
- [環境變數設定](#環境變數設定)
- [執行測試](#執行測試)
- [GitHub Actions 部署](#github-actions-部署)
- [授權](#授權)

## ✨ 功能特色

- **自動爬取**：抓取 TAIFEX 日盤與夜盤選擇權每日行情表
- **資料清洗**：自動解析 HTML 表格，轉換為結構化資料
- **MongoDB 儲存**：以 `trade_date + session` 為唯一鍵，支援 upsert 更新
- **環境彈性**：支援本地 `.env` 檔案與 CI/CD 環境變數
- **Clean Architecture**：清晰的分層架構，易於維護與測試
- **完整測試**：包含單元測試，確保程式品質

## 🏗️ 專案架構

本專案採用 Clean Architecture 設計，職責分離清楚：

```
twse-option-crawler/
├── main.py                     # 應用程式入口
├── src/                        # 應用程式碼
│   ├── __init__.py
│   ├── models.py              # 領域模型（Domain Layer）
│   ├── config.py              # 配置管理（Interface Layer）
│   ├── fetcher.py             # HTTP 資料抓取（Infrastructure Layer）
│   ├── transformer.py         # 資料轉換（Application Layer）
│   ├── service.py             # 業務服務（Application Layer）
│   └── repository.py          # 資料庫操作（Infrastructure Layer）
├── tests/                      # 單元測試
│   └── test_crawler.py
├── .env.example               # 環境變數範例
├── .github/workflows/         # GitHub Actions 工作流程範例
│   └── crawler.yml.example
├── requirements.txt           # Python 套件依賴
├── LICENSE                    # MIT 授權
└── README.md                  # 專案說明文件
```

### 架構說明

- **Domain Layer（領域層）**
  - `models.py`：定義 `MarketSessionData` 資料模型

- **Application Layer（應用層）**
  - `service.py`：`TaifexCrawlerService` 爬蟲業務邏輯
  - `transformer.py`：`DataTransformer` 資料轉換工具

- **Infrastructure Layer（基礎設施層）**
  - `fetcher.py`：`TaifexTableFetcher` HTTP 請求與 HTML 解析
  - `repository.py`：`MongoMarketRepository` MongoDB 資料持久化

- **Interface Layer（介面層）**
  - `config.py`：`CrawlerConfig` 配置管理
  - `main.py`：應用程式入口與依賴組裝

## 💻 系統需求

- Python 3.11 或以上版本
- MongoDB 資料庫（本地或雲端）
- pip（Python 套件管理工具）

## 🚀 快速開始

### 1. 複製專案

```bash
git clone https://github.com/julian7862/twse-option-crawler.git
cd twse-option-crawler
```

### 2. 建立虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 4. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入您的 MongoDB 連線資訊：

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=market_data
MONGO_COLLECTION=taifex_option_daily
```

### 5. 執行爬蟲

```bash
python main.py
```

執行成功後會顯示：

```
Stored day(XXX) + night(XXX) rows to MongoDB.
```

## ⚙️ 環境變數設定

| 變數名稱 | 必填 | 預設值 | 說明 |
|---------|------|--------|------|
| `MONGO_URI` | ✅ | - | MongoDB 連線字串 |
| `MONGO_DB` | ❌ | `market_data` | 資料庫名稱 |
| `MONGO_COLLECTION` | ❌ | `taifex_option_daily` | Collection 名稱 |
| `TAIFEX_DAY_URL` | ❌ | TAIFEX 官方日盤網址 | 日盤資料來源 URL |
| `TAIFEX_NIGHT_URL` | ❌ | TAIFEX 官方夜盤網址 | 夜盤資料來源 URL |

### MongoDB 連線範例

**本地端：**
```env
MONGO_URI=mongodb://localhost:27017
```

**MongoDB Atlas（雲端）：**
```env
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

## 🧪 執行測試

本專案包含完整的單元測試，涵蓋配置載入、資料轉換、爬蟲服務與資料庫操作。

```bash
# 執行所有測試
python -m unittest tests.test_crawler -v

# 或使用 discover 模式
python -m unittest discover -s tests -p 'test_*.py' -v
```

測試結果範例：

```
test_config_from_env ... ok
test_repository_upsert_payload ... ok
test_service_crawl_returns_day_and_night_sessions ... ok
test_transformer_converts_nan_to_none ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.003s

OK
```

## 🤖 GitHub Actions 部署

### 設定步驟

1. **在 GitHub Repository 設定 Secrets**

   進入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   新增以下 Secrets：
   - `MONGO_URI`（必填）
   - `MONGO_DB`（選填）
   - `MONGO_COLLECTION`（選填）

2. **啟用 Workflow**

   ```bash
   # 將範例檔案改名
   mv .github/workflows/crawler.yml.example .github/workflows/crawler.yml

   # 提交並推送
   git add .github/workflows/crawler.yml
   git commit -m "Enable GitHub Actions workflow"
   git push
   ```

3. **設定排程時間**

   編輯 `.github/workflows/crawler.yml`，調整 `cron` 排程：

   ```yaml
   on:
     schedule:
       # 每天 UTC 10:00（台灣時間 18:00）執行
       - cron: '0 10 * * *'
     workflow_dispatch:  # 允許手動觸發
   ```

4. **手動測試執行**

   前往 `Actions` 標籤 → 選擇 workflow → `Run workflow`

### Cron 時間對照表

| 台灣時間 | UTC 時間 | Cron 表達式 |
|---------|---------|------------|
| 06:00 | 22:00 (前一天) | `0 22 * * *` |
| 14:00 | 06:00 | `0 6 * * *` |
| 18:00 | 10:00 | `0 10 * * *` |

## 📊 資料格式

### MongoDB 儲存結構

```json
{
  "trade_date": "2026/03/06",
  "session": "day",
  "source_url": "https://www.taifex.com.tw/cht/3/optDailyMarketExcel",
  "fetched_at": "2026-03-06T10:30:00.000Z",
  "row_count": 150,
  "rows": [
    {
      "履約價": 23000,
      "買進價": 150.5,
      "賣出價": 151.0,
      "成交價": 150.8,
      "成交量": 1234,
      "交易日": "2026-03-06T00:00:00",
      "市場時段": "日盤"
    }
  ]
}
```

### 唯一索引

系統會自動建立複合索引：`{ trade_date: 1, session: 1 }`，確保同一交易日與時段的資料不會重複。

## 🛠️ 開發建議

### 新增功能

1. Fork 本專案
2. 建立功能分支：`git checkout -b feature/your-feature`
3. 撰寫程式碼與測試
4. 提交變更：`git commit -m "Add your feature"`
5. 推送分支：`git push origin feature/your-feature`
6. 建立 Pull Request

### 程式碼風格

- 遵循 PEP 8 規範
- 使用 type hints
- 撰寫有意義的 docstrings
- 保持函數單一職責

## 📝 授權

本專案採用 [MIT License](LICENSE) 授權。

## 🙋 常見問題

**Q: 為什麼爬蟲失敗？**

A: 請檢查：
1. 網路連線是否正常
2. TAIFEX 網站是否可訪問
3. MongoDB 連線是否正確
4. 環境變數是否正確設定

**Q: 如何修改爬取時間？**

A: 編輯 `.github/workflows/crawler.yml` 中的 `cron` 設定即可。

**Q: 可以爬取歷史資料嗎？**

A: 目前僅支援當日資料。如需歷史資料，請修改 `fetcher.py` 加入日期參數。

**Q: 資料重複怎麼辦？**

A: 系統使用 upsert 機制，相同 `trade_date + session` 會自動覆蓋，不會產生重複資料。

## 📧 聯絡方式

如有問題或建議，歡迎開 [Issue](https://github.com/julian7862/twse-option-crawler/issues)。

---

**Made with ❤️ for Taiwan Financial Market**
