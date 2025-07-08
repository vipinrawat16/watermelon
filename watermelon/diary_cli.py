#!/usr/bin/env python3
import argparse
import json
import sys
from diary_sync import DiarySync
import logging

def load_config(config_file='config.json'):
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found. Using default settings.")
        return {
            "database": {"name": "my_diary.db"},
            "api": {"url": "", "key": ""},
            "logging": {"level": "INFO"}
        }
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}")
        sys.exit(1)

def setup_logging(config):
    """Setup logging based on configuration"""
    log_level = getattr(logging, config.get('logging', {}).get('level', 'INFO'))
    log_file = config.get('logging', {}).get('file')
    
    if log_file:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    else:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

def sync_command(args, config):
    """Execute sync command"""
    diary_sync = DiarySync(
        db_name=config['database']['name'],
        api_url=config['api']['url'],
        api_key=config['api']['key']
    )
    
    try:
        diary_sync.sync_entries()
        print("Sync completed successfully!")
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(1)
    finally:
        diary_sync.close()

def list_command(args, config):
    """Execute list command"""
    diary_sync = DiarySync(db_name=config['database']['name'])
    
    try:
        if args.date:
            entries = diary_sync.get_entry_by_date(args.date)
            print(f"Entries for {args.date}:")
        else:
            entries = diary_sync.get_all_entries()
            print(f"All entries ({len(entries)} total):")
        
        if not entries:
            print("No entries found.")
            return
        
        # Limit output if requested
        limit = args.limit if args.limit else len(entries)
        for i, entry in enumerate(entries[:limit]):
            print(f"\n--- Entry {i+1} ---")
            print(f"ID: {entry[0]}")
            print(f"Date: {entry[2]}")
            print(f"Title: {entry[3] or 'No title'}")
            print(f"Content: {entry[4][:100]}{'...' if len(entry[4]) > 100 else ''}")
            print(f"Created: {entry[5]}")
            
    except Exception as e:
        print(f"Failed to retrieve entries: {e}")
        sys.exit(1)
    finally:
        diary_sync.close()

def status_command(args, config):
    """Execute status command"""
    diary_sync = DiarySync(db_name=config['database']['name'])
    
    try:
        entries = diary_sync.get_all_entries()
        
        # Get sync log
        diary_sync.cursor.execute('SELECT * FROM sync_log ORDER BY sync_date DESC LIMIT 5')
        sync_logs = diary_sync.cursor.fetchall()
        
        print(f"Database: {config['database']['name']}")
        print(f"Total entries: {len(entries)}")
        
        if entries:
            print(f"Latest entry: {entries[0][2]}")  # Date of most recent entry
        
        print("\nRecent sync history:")
        if sync_logs:
            for log in sync_logs:
                print(f"  {log[1]}: {log[2]} entries ({log[3]})")
        else:
            print("  No sync history found")
            
    except Exception as e:
        print(f"Failed to get status: {e}")
        sys.exit(1)
    finally:
        diary_sync.close()

def main():
    parser = argparse.ArgumentParser(description='Diary Sync Tool')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync entries from website to database')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List diary entries')
    list_parser.add_argument('--date', help='Show entries for specific date (YYYY-MM-DD)')
    list_parser.add_argument('--limit', type=int, help='Limit number of entries to show')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database status and sync history')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Load configuration
    config = load_config(args.config)
    setup_logging(config)
    
    # Execute command
    if args.command == 'sync':
        sync_command(args, config)
    elif args.command == 'list':
        list_command(args, config)
    elif args.command == 'status':
        status_command(args, config)

if __name__ == '__main__':
    main()
