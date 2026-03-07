# MongoDB 設定指南

## 選項 1: MongoDB Atlas（雲端免費方案）

### 步驟 1: 註冊 MongoDB Atlas

1. 前往 https://www.mongodb.com/cloud/atlas/register
2. 註冊免費帳號
3. 選擇 **FREE** tier（M0 Sandbox）

### 步驟 2: 建立 Cluster

1. 選擇雲端供應商（建議選 AWS）
2. 選擇區域（建議選 Tokyo 或 Singapore，延遲較低）
3. Cluster Name 可以保持預設或改名
4. 點擊 **Create Cluster**

### 步驟 3: 設定資料庫使用者

1. 點擊左側 **Database Access**
2. 點擊 **Add New Database User**
3. 設定：
   - Username: 例如 `taifex_user`
   - Password: 設定強密碼（記下來！）
   - Database User Privileges: 選擇 **Read and write to any database**
4. 點擊 **Add User**

### 步驟 4: 設定網路存取

1. 點擊左側 **Network Access**
2. 點擊 **Add IP Address**
3. 選擇：
   - **本地測試**：點擊 **Add Current IP Address**
   - **GitHub Actions**：點擊 **Allow Access from Anywhere**（輸入 `0.0.0.0/0`）
4. 點擊 **Confirm**

### 步驟 5: 取得連線字串

1. 回到 **Database** 頁面
2. 點擊你的 cluster 的 **Connect** 按鈕
3. 選擇 **Connect your application**
4. 選擇 Driver: **Python** / Version: **3.12 or later**
5. 複製連線字串，類似：
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. 將 `<username>` 和 `<password>` 替換成你的實際帳密

### 步驟 6: 設定 .env

```bash
cp .env.example .env
```

編輯 `.env`：
```env
MONGO_URI=mongodb+srv://taifex_user:your_password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=market_data
MONGO_COLLECTION=taifex_option_daily
TAIFEX_DAY_URL=https://www.taifex.com.tw/cht/3/optDailyMarketExcel
TAIFEX_NIGHT_URL=https://www.taifex.com.tw/cht/3/optDailyMarketExcel?marketCode=1
```

---

## 選項 2: 本地安裝 MongoDB

### macOS 安裝

```bash
# 使用 Homebrew 安裝
brew tap mongodb/brew
brew install mongodb-community@7.0

# 啟動 MongoDB
brew services start mongodb-community@7.0

# 確認運行
mongosh --version
```

### Ubuntu/Debian 安裝

```bash
# 匯入公鑰
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# 新增 MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# 安裝
sudo apt-get update
sudo apt-get install -y mongodb-org

# 啟動
sudo systemctl start mongod
sudo systemctl enable mongod
```

### Docker 安裝（最簡單）

```bash
# 啟動 MongoDB container
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password123 \
  mongo:7.0

# 連線字串
MONGO_URI=mongodb://admin:password123@localhost:27017/
```

### 設定 .env（本地）

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=market_data
MONGO_COLLECTION=taifex_option_daily
TAIFEX_DAY_URL=https://www.taifex.com.tw/cht/3/optDailyMarketExcel
TAIFEX_NIGHT_URL=https://www.taifex.com.tw/cht/3/optDailyMarketExcel?marketCode=1
```

---

## 測試連線

### 方法 1: 使用 mongosh（MongoDB Shell）

```bash
# 連線到 Atlas
mongosh "mongodb+srv://cluster0.xxxxx.mongodb.net/" --username taifex_user

# 或連線到本地
mongosh

# 測試指令
use market_data
show collections
```

### 方法 2: 使用 Python 測試腳本

建立 `test_mongo_connection.py`：

```python
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

mongo_uri = os.getenv("MONGO_URI")
print(f"Connecting to: {mongo_uri}")

try:
    client = MongoClient(mongo_uri)
    # 測試連線
    client.admin.command('ping')
    print("✅ MongoDB connection successful!")

    # 列出所有資料庫
    print("\nAvailable databases:")
    for db_name in client.list_database_names():
        print(f"  - {db_name}")

    client.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

執行：
```bash
python test_mongo_connection.py
```

---

## 執行爬蟲

設定完成後，直接執行：

```bash
python main.py
```

## 查看資料

### 使用 mongosh

```bash
mongosh "your_connection_string"

use market_data
db.taifex_option_daily.find().limit(1).pretty()
db.taifex_option_daily.countDocuments()
```

### 使用 MongoDB Compass（GUI 工具）

1. 下載：https://www.mongodb.com/products/compass
2. 貼上連線字串
3. 連線後瀏覽 `market_data` → `taifex_option_daily`

---

## 常見問題

### Q: 需要手動建立 database 或 collection 嗎？

**A: 不需要！** MongoDB 會在第一次寫入時自動建立。

### Q: 索引會自動建立嗎？

**A: 是的！** 程式碼中的 `repository.py` 會自動建立：
```python
collection.create_index(
    [("trade_date", ASCENDING), ("session", ASCENDING)],
    unique=True,
    name="trade_date_session_unique",
)
```

### Q: 如何確認索引已建立？

```bash
mongosh "your_connection_string"
use market_data
db.taifex_option_daily.getIndexes()
```

應該會看到：
```json
[
  { "v": 2, "key": { "_id": 1 }, "name": "_id_" },
  {
    "v": 2,
    "key": { "trade_date": 1, "session": 1 },
    "name": "trade_date_session_unique",
    "unique": true
  }
]
```

### Q: Atlas 免費方案有什麼限制？

- 512 MB 儲存空間
- 共享 RAM
- 沒有備份功能
- 對於這個專案綽綽有餘！

### Q: 連線逾時怎麼辦？

檢查：
1. Network Access 是否允許你的 IP
2. 連線字串是否正確
3. 帳號密碼是否正確
4. 防火牆是否阻擋
