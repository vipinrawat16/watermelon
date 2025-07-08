#!/usr/bin/env python3
"""
Test script to verify database connectivity and sample users
"""
import sqlite3
import os

def test_database():
    db_path = "instance/login_users.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the user table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user';")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ User table not found!")
            return False
        
        print("✅ Database file exists and user table found!")
        
        # Check sample users
        cursor.execute("SELECT id, username FROM user;")
        users = cursor.fetchall()
        
        print(f"📊 Found {len(users)} users in database:")
        for user_id, username in users:
            print(f"  - ID: {user_id}, Username: {username}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing database connectivity...")
    success = test_database()
    
    if success:
        print("\n✅ Database test completed successfully!")
        print("\n🚀 You can now run the Flask app with: python app.py")
        print("📖 Available test users:")
        print("  - admin / admin123")
        print("  - user1 / password1") 
        print("  - testuser / test123")
        print("  - john_doe / john123")
    else:
        print("\n❌ Database test failed!")
