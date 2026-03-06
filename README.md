# TAIFEX Option Daily Crawler (MongoDB + GitHub Actions)

這個子專案把原本 `backend/shioaji_stream.py` 中「抓台指選擇權日盤/夜盤表格」邏輯拆成獨立腳本，並提供可上 GitHub Actions 的排程與 MongoDB 落地。

## 檔案結構

```text
twse-option-crawler/
├── .env.example
├── crawl_taifex_to_mongo.py
├── requirements.txt
├── tests/
│   └── test_crawler.py
└── .github/
    └── workflows/
        └── taifex-crawler.yml
```

## 設計（Clean Code / SOLID）

`crawl_taifex_to_mongo.py` 已分層：
- `CrawlerConfig`：負責設定讀取（單一職責）
- `TaifexTableFetcher`：負責外部資料抓取與 HTML 解析
- `DataTransformer`：負責 DataFrame -> Records 轉換
- `MongoMarketRepository`：負責資料庫存取
- `TaifexCrawlerService`：組合 fetch + transform 的業務流程
- `run/main`：應用程式入口

## 功能

- 抓取 TAIFEX 日盤 URL：`https://www.taifex.com.tw/cht/3/optDailyMarketExcel`
- 抓取 TAIFEX 夜盤 URL：`https://www.taifex.com.tw/cht/3/optDailyMarketExcel?marketCode=1`
- 解析出 `履約價` 表格
- 寫入 MongoDB（`trade_date + session` 唯一鍵，採 upsert）

## 環境變數

請先複製：

```bash
cp .env.example .env
```

主要變數：
- `MONGO_URI`（必要）
- `MONGO_DB`（選填，預設 `market_data`）
- `MONGO_COLLECTION`（選填，預設 `taifex_option_daily`）
- `TAIFEX_DAY_URL`（選填）
- `TAIFEX_NIGHT_URL`（選填）

## 本機執行

```bash
cd twse-option-crawler
pip install -r requirements.txt
export MONGO_URI='mongodb+srv://...'
python crawl_taifex_to_mongo.py
```

## Unit Test

```bash
cd twse-option-crawler
python -m unittest discover -s tests -p 'test_*.py'
```

## GitHub Actions 設定

Workflow 會先跑 unit tests，再執行爬蟲。


Workflow 已設定每天台灣時間：
- 06:00
- 08:00
- 14:00

> 注意：GitHub Actions `cron` 使用 UTC，設定檔中已換算為 UTC。

請在 GitHub repo Secrets 設定：
- `MONGO_URI`
- `MONGO_DB`（可選）
- `MONGO_COLLECTION`（可選）
- `TAIFEX_DAY_URL`（可選）
- `TAIFEX_NIGHT_URL`（可選）

## 如果你要拆成「全新 repo」

1. 建立新 repository（例如 `taifex-option-crawler`）
2. 複製此資料夾中的檔案到 repo 根目錄
3. 推上 GitHub
4. 設定上述 Secrets
5. 到 Actions 手動執行一次 `workflow_dispatch` 驗證
