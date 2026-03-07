#!/usr/bin/env python3
"""Test MongoDB connection."""

import os
from pathlib import Path

from pymongo import MongoClient

# Load .env file
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print("✅ Loaded .env file")
    else:
        print("⚠️  No .env file found, using system environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")

mongo_uri = os.getenv("MONGO_URI")
mongo_db = os.getenv("MONGO_DB")
mongo_collection = os.getenv("MONGO_COLLECTION")

print("\n" + "="*60)
print("MongoDB Connection Test")
print("="*60)

if not mongo_uri:
    print("❌ MONGO_URI not set in environment variables or .env file")
    print("\nPlease set up your .env file:")
    print("  cp .env.example .env")
    print("  # Then edit .env with your MongoDB connection string")
    exit(1)

print(f"\nConnection URI: {mongo_uri[:20]}...{mongo_uri[-20:] if len(mongo_uri) > 40 else mongo_uri[20:]}")
print(f"Database: {mongo_db or 'NOT SET'}")
print(f"Collection: {mongo_collection or 'NOT SET'}")

try:
    print("\n🔗 Connecting to MongoDB...")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    # Test connection with ping
    client.admin.command('ping')
    print("✅ MongoDB connection successful!")

    # List databases
    print("\n📦 Available databases:")
    for db_name in client.list_database_names():
        print(f"  - {db_name}")

    # Check if our database exists
    if mongo_db:
        if mongo_db in client.list_database_names():
            print(f"\n✅ Database '{mongo_db}' exists")
            db = client[mongo_db]

            # List collections
            collections = db.list_collection_names()
            if collections:
                print(f"\n📋 Collections in '{mongo_db}':")
                for coll_name in collections:
                    count = db[coll_name].count_documents({})
                    print(f"  - {coll_name}: {count} documents")

                # If our collection exists, show sample data
                if mongo_collection and mongo_collection in collections:
                    print(f"\n📄 Sample document from '{mongo_collection}':")
                    sample = db[mongo_collection].find_one()
                    if sample:
                        for key, value in sample.items():
                            if key == 'rows':
                                print(f"  {key}: [{len(value)} rows]")
                            elif key == '_id':
                                print(f"  {key}: {value}")
                            else:
                                print(f"  {key}: {value}")
                    else:
                        print("  (empty collection)")
            else:
                print(f"\n⚠️  No collections in '{mongo_db}' yet")
        else:
            print(f"\n⚠️  Database '{mongo_db}' does not exist yet")
            print("   (It will be created automatically when you run the crawler)")

    client.close()
    print("\n" + "="*60)
    print("✅ All checks passed! You're ready to run the crawler.")
    print("="*60)

except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check your MONGO_URI is correct")
    print("2. If using MongoDB Atlas:")
    print("   - Add your IP to Network Access whitelist")
    print("   - Verify username and password")
    print("3. If using local MongoDB:")
    print("   - Make sure MongoDB is running")
    print("   - Try: brew services start mongodb-community")
    exit(1)
