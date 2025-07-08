from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

class DiaryReader:
    def __init__(self, db_name='my_diary.db'):
        self.db_name = db_name
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def get_all_entries(self, limit=None, offset=0):
        """Get all diary entries with optional pagination"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM diary_entries ORDER BY date DESC'
        if limit:
            query += f' LIMIT {limit} OFFSET {offset}'
        
        cursor.execute(query)
        entries = cursor.fetchall()
        conn.close()
        return entries
    
    def get_entry_by_id(self, entry_id):
        """Get a specific entry by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM diary_entries WHERE id = ?', (entry_id,))
        entry = cursor.fetchone()
        conn.close()
        return entry
    
    def search_entries(self, search_term):
        """Search entries by content or title"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM diary_entries 
            WHERE title LIKE ? OR content LIKE ? 
            ORDER BY date DESC
        ''', (f'%{search_term}%', f'%{search_term}%'))
        entries = cursor.fetchall()
        conn.close()
        return entries
    
    def get_entries_by_date_range(self, start_date, end_date):
        """Get entries within a date range"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM diary_entries 
            WHERE date BETWEEN ? AND ? 
            ORDER BY date DESC
        ''', (start_date, end_date))
        entries = cursor.fetchall()
        conn.close()
        return entries

diary_reader = DiaryReader()

@app.route('/')
def index():
    """Main page showing recent entries"""
    entries = diary_reader.get_all_entries(limit=10)
    return render_template('index.html', entries=entries)

@app.route('/entry/<int:entry_id>')
def view_entry(entry_id):
    """View a specific entry"""
    entry = diary_reader.get_entry_by_id(entry_id)
    if entry:
        return render_template('entry.html', entry=entry)
    else:
        return "Entry not found", 404

@app.route('/search')
def search():
    """Search entries"""
    search_term = request.args.get('q', '')
    entries = []
    if search_term:
        entries = diary_reader.search_entries(search_term)
    return render_template('search.html', entries=entries, search_term=search_term)

@app.route('/api/entries')
def api_entries():
    """API endpoint to get entries as JSON"""
    limit = request.args.get('limit', 10, type=int)
    offset = request.args.get('offset', 0, type=int)
    entries = diary_reader.get_all_entries(limit=limit, offset=offset)
    
    # Convert to list of dictionaries
    entries_list = []
    for entry in entries:
        entries_list.append({
            'id': entry[0],
            'entry_id': entry[1],
            'date': entry[2],
            'title': entry[3],
            'content': entry[4],
            'created_at': entry[5],
            'updated_at': entry[6]
        })
    
    return jsonify(entries_list)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("Starting Diary Web Interface...")
    print("Access your diary at: http://localhost:5000")
    app.run(debug=True, host='localhost', port=5000)
