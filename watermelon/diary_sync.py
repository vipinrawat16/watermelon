import sqlite3
import requests
import json
import logging
from datetime import datetime
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiarySync:
    def __init__(self, db_name='diary_entries.db', api_url=None, api_key=None):
        self.db_name = db_name
        self.api_url = api_url
        self.api_key = api_key
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database and create tables if they don't exist"""
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            
            # Create diary entries table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT UNIQUE,
                    date TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create sync log table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    entries_synced INTEGER,
                    status TEXT
                )
            ''')
            
            self.conn.commit()
            logger.info("Database initialized successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def fetch_entries_from_api(self):
        """Fetch diary entries from the website API"""
        if not self.api_url:
            logger.error("API URL not configured")
            return []
        
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = requests.get(self.api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            entries = response.json()
            logger.info(f"Successfully fetched {len(entries)} entries from API")
            return entries
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return []
    
    def save_entry_to_db(self, entry):
        """Save a single entry to the database"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO diary_entries 
                (entry_id, date, title, content, updated_at) 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                entry.get('id', ''),
                entry.get('date', ''),
                entry.get('title', ''),
                entry.get('content', '')
            ))
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database insert error: {e}")
            return False
    
    def sync_entries(self):
        """Main sync function to fetch and save entries"""
        logger.info("Starting diary sync...")
        
        # Fetch entries from API
        entries = self.fetch_entries_from_api()
        
        if not entries:
            logger.warning("No entries to sync")
            return
        
        # Save entries to database
        synced_count = 0
        for entry in entries:
            if self.save_entry_to_db(entry):
                synced_count += 1
        
        self.conn.commit()
        
        # Log sync results
        self.cursor.execute('''
            INSERT INTO sync_log (entries_synced, status) 
            VALUES (?, ?)
        ''', (synced_count, 'success' if synced_count > 0 else 'no_new_entries'))
        
        self.conn.commit()
        logger.info(f"Sync completed. {synced_count} entries synced successfully")
    
    def get_all_entries(self):
        """Retrieve all entries from the database"""
        try:
            self.cursor.execute('SELECT * FROM diary_entries ORDER BY date DESC')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Database query error: {e}")
            return []
    
    def get_entry_by_date(self, date):
        """Retrieve entries by specific date"""
        try:
            self.cursor.execute('SELECT * FROM diary_entries WHERE date = ?', (date,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Database query error: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

# Example usage and configuration
def main():
    # Configuration - Update these values for your specific setup
    CONFIG = {
        'db_name': 'my_diary.db',
        'api_url': 'https://your-diary-website.com/api/entries',  # Replace with actual URL
        'api_key': 'your-api-key-here'  # Replace with actual API key if required
    }
    
    # Initialize diary sync
    diary_sync = DiarySync(
        db_name=CONFIG['db_name'],
        api_url=CONFIG['api_url'],
        api_key=CONFIG['api_key']
    )
    
    try:
        # Sync entries from website to database
        diary_sync.sync_entries()
        
        # Optional: Display some entries
        entries = diary_sync.get_all_entries()
        if entries:
            print(f"\nFound {len(entries)} entries in database:")
            for entry in entries[:5]:  # Show first 5 entries
                print(f"Date: {entry[2]}, Title: {entry[3]}")
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
    
    finally:
        diary_sync.close()

if __name__ == "__main__":
    main()
