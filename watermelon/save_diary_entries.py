import sqlite3
import requests
import json

# Database configuration
DB_NAME = 'diary_entries.db'
TABLE_NAME = 'entries'

# API URL (replace with actual URL)
API_URL = 'https://example.com/api/diary_entries'

# Create a database connection
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute(f'''
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    title TEXT,
    content TEXT
)
''')
conn.commit()

# Fetch diary entries from the API
response = requests.get(API_URL)
entries = response.json() # Assuming JSON response

# Insert entries into the database
for entry in entries:
    cursor.execute(f'''
    INSERT INTO {TABLE_NAME} (date, title, content) 
    VALUES (?, ?, ?)
    ''', (entry['date'], entry.get('title', ''), entry['content']))

conn.commit()

# Close the connection
conn.close()
