import os
import sys
import re
import argparse
import time
from datetime import datetime
import sqlite3
import shutil

# Backup directory relative to the default EasyWorship path
DEFAULT_BACKUP_DIR = r"C:\Users\Public\Documents\Softouch\Easyworship\backups"

# Ensure the backup directory exists
os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)

def log(message, verbose=False):
    """Logs a message if verbose mode is enabled."""
    if verbose:
        print(message)

def search_for_databases_dir(root_dir, verbose=False):
    """Searches for the Databases folder in all subdirectories under the specified root directory."""
    log(f"Searching for Databases directory starting in: {root_dir}", verbose)
    for root, dirs, files in os.walk(root_dir):
        log(f"Checking directory: {root}", verbose)
        if "Databases" in dirs:
            db_dir = os.path.join(root, "Databases")
            log(f"Found Databases directory at: {db_dir}", verbose)
            return db_dir
    log("Databases directory not found in the specified directory.", verbose)
    return None

def register_utf8_ci_collation(connection):
    """Registers the custom UTF-8 case-insensitive collation sequence."""
    def utf8_ci(x, y):
        return (x.lower() > y.lower()) - (x.lower() < y.lower())
    connection.create_collation("UTF8_U_CI", utf8_ci)

def get_db_paths(input_dir, verbose=False):
    """Returns the expected paths for Songs.db and SongWords.db from the specified input directory."""
    songs_db_path = os.path.join(input_dir, "Songs.db")
    songwords_db_path = os.path.join(input_dir, "SongWords.db")
    log(f"Input Songs.db path: {songs_db_path}", verbose)
    log(f"Input SongWords.db path: {songwords_db_path}", verbose)
    return songs_db_path, songwords_db_path

def is_db_locked(db_path):
    """Checks if the database file is locked by attempting a PRAGMA quick_check."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA quick_check;")  # Basic check for database usability
        conn.close()
        return False  # Not locked
    except sqlite3.OperationalError:
        return True  # Locked


def create_backup(songs_db_path, songwords_db_path, verbose=False):
    """Creates backups for Songs.db and SongWords.db with a timestamped .bak extension."""
    os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)
    log("Preparing to create backups.", verbose)

    timestamp = int(time.time())  # Unix timestamp
    songs_backup_name = f"{timestamp}Songs.db.bak"
    songwords_backup_name = f"{timestamp}SongWords.db.bak"

    songs_backup_path = os.path.join(DEFAULT_BACKUP_DIR, songs_backup_name)
    songwords_backup_path = os.path.join(DEFAULT_BACKUP_DIR, songwords_backup_name)

    try:
        shutil.copy2(songs_db_path, songs_backup_path)
        print(f"Songs.db backup created: {songs_backup_name}")
        log(f"Songs.db successfully backed up to: {songs_backup_path}", verbose)

        shutil.copy2(songwords_db_path, songwords_backup_path)
        print(f"SongWords.db backup created: {songwords_backup_name}")
        log(f"SongWords.db successfully backed up to: {songwords_backup_path}", verbose)

    except FileNotFoundError as e:
        print(f"Error: Could not create one or more backups. {e}")
        log(f"FileNotFoundError during backup creation: {e}", verbose)
        exit(1)
    except PermissionError as e:
        print("Error: Unable to create backups because one or more files are in use.")
        print("Please ensure EasyWorship is closed and try again.")
        log(f"PermissionError during backup creation: {e}", verbose)
        exit(1)

    return {"songs": songs_backup_name, "songwords": songwords_backup_name}
    
def list_backups(verbose=False):
    """Lists all backup files in the DEFAULT_BACKUP_DIR directory, including their human-readable timestamps."""
    print(f"Looking for backups in: {DEFAULT_BACKUP_DIR}")
    if not os.path.exists(DEFAULT_BACKUP_DIR):
        print("No backups found. Backup directory does not exist.")
        return

    backups = [f for f in os.listdir(DEFAULT_BACKUP_DIR) if f.endswith(".bak")]
    if backups:
        print("Available backups:")
        for backup in backups:
            backup_path = os.path.join(DEFAULT_BACKUP_DIR, backup)
            
            # Extract and convert Unix timestamp from the filename
            try:
                timestamp = int(re.search(r"(\d+)", backup).group(1))
                human_readable_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except (AttributeError, ValueError):
                human_readable_time = "Unknown"
            
            # Get last modified time of the file
            modified_time = os.path.getmtime(backup_path)
            formatted_modified_time = datetime.fromtimestamp(modified_time).strftime("%Y-%m-%d %H:%M:%S")

            print(f" - {backup}")
            print(f"      Created: {human_readable_time}")
            print(f"      Last Modified: {formatted_modified_time}")
    else:
        print("No backup files found.")

def restore_backup(databases_dir, backup_file, verbose=False):
    """Restores a backup file to replace Songs.db or SongWords.db."""
    songs_db_path, songwords_db_path = get_db_paths(databases_dir, verbose)

    if "Songs.db" in backup_file:
        restore_path = songs_db_path
    elif "SongWords.db" in backup_file:
        restore_path = songwords_db_path
    else:
        print(f"Error: Backup file '{backup_file}' does not match expected patterns.")
        exit(1)

    backup_path = os.path.join(DEFAULT_BACKUP_DIR, backup_file)
    if not os.path.exists(backup_path):
        print(f"Error: Backup file '{backup_file}' not found in the backups directory.")
        exit(1)

    shutil.copy2(backup_path, restore_path)
    print(f"Backup '{backup_file}' restored to: {restore_path}")
    
def list_txt_files_in_dir(directory, verbose=False):
    """Returns a list of .txt files in the given directory."""
    log(f"Searching for .txt files in directory: {directory}", verbose)
    txt_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".txt")]
    log(f"Found .txt files: {txt_files}", verbose)
    return txt_files

def log_database_state(db_path):
    """Logs the number of entries in the Songs and SongWords database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM song;")
        song_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM word;")
        word_count = cursor.fetchone()[0]
        conn.close()
        print(f"Database {db_path} State: Songs={song_count}, Lyrics={word_count}")
    except sqlite3.Error as e:
        print(f"Error reading database state for {db_path}: {e}")

def validate_database(db_path, verbose=False):
    """Validates the integrity of a database using PRAGMA integrity_check."""
    log(f"Validating database: {db_path}", verbose)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()

        if result and result[0] == "ok":
            log(f"Integrity check passed for {db_path}.", verbose)
            return True
        else:
            log(f"Integrity check failed for {db_path}. Result: {result[0] if result else 'Unknown'}", verbose)
            return False
    except Exception as e:
        log(f"Unexpected error during database validation: {e}", verbose)
        return False

import subprocess

def test_db_connection(db_path, verbose=False):
    """
    Tests if a database file is accessible and not locked using the custom SQLite DLL.
    """
    log(f"Testing database connection for: {db_path}", verbose)

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA integrity_check;")
        conn.close()
        log(f"Database {db_path} integrity check passed.", verbose)
        return True
    except sqlite3.OperationalError as exc:
        log(f"SQLite operational error: {exc}", verbose)
        return False
    except Exception as exc:
        log(f"Unexpected error while testing database: {exc}", verbose)
        return False

def process_txt_files(file_paths, songs_db_path, songwords_db_path, output_dir=None, verbose=False):
    """Processes the provided .txt files and inserts them into Songs.db and SongWords.db."""
    log("Connecting to the SQLite databases.", verbose)
    
    try:
        # Connect to Songs.db
        conn_songs = sqlite3.connect(songs_db_path)
        conn_songs.create_collation("UTF8_U_CI", lambda x, y: (x > y) - (x < y))  # Register dummy collation
        cursor_songs = conn_songs.cursor()

        # Connect to SongWords.db
        conn_songwords = sqlite3.connect(songwords_db_path)
        cursor_songwords = conn_songwords.cursor()

        for file_path in file_paths:
            log(f"Processing file: {file_path}", verbose)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read().strip()

                    # Extract song title from the filename
                    title = os.path.basename(file_path).replace(".txt", "").strip()

                    # Convert lyrics to basic RTF format
                    lyrics = f"{{\\rtf1\\ansi {content.replace('\n', '\\par ')}}}"

                    # Check if the song already exists in Songs.db
                    cursor_songs.execute("SELECT rowid FROM song WHERE title = ?", (title,))
                    song_row = cursor_songs.fetchone()
                    if song_row:
                        song_id = song_row[0]
                        log(f"Song '{title}' already exists in Songs.db. Skipping.", verbose)
                    else:
                        # Insert new song into Songs.db
                        cursor_songs.execute("""
                            INSERT INTO song (song_item_uid, title, author, copyright)
                            VALUES (?, ?, ?, ?)
                        """, (
                            f"UID-{time.time_ns()}",  # Generate a unique ID
                            title,
                            "Unknown",  # Author not provided
                            "Public Domain"
                        ))
                        song_id = cursor_songs.lastrowid
                        log(f"Song '{title}' added to Songs.db successfully.", verbose)

                    # Check if the lyrics already exist in SongWords.db
                    cursor_songwords.execute("SELECT 1 FROM word WHERE song_id = ?", (song_id,))
                    if cursor_songwords.fetchone():
                        log(f"Lyrics for song '{title}' already exist in SongWords.db. Skipping.", verbose)
                        continue

                    # Insert lyrics into SongWords.db
                    cursor_songwords.execute("""
                        INSERT INTO word (song_id, words)
                        VALUES (?, ?)
                    """, (song_id, lyrics))
                    log(f"Lyrics for song '{title}' added to SongWords.db successfully.", verbose)

            except Exception as e:
                log(f"Error processing file {file_path}: {e}", verbose)

        # Commit changes and close connections
        conn_songs.commit()
        conn_songwords.commit()
        conn_songs.close()
        conn_songwords.close()
    except Exception as e:
        print(f"Error: Could not process files. {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage EasyWorship Songs.db and SongWords.db.")
    parser.add_argument("--list-backups", "-l", action="store_true", help="List all backups with modify date/time.")
    parser.add_argument("--restore-backup", "-r", metavar="FILE", help="Restore the specified backup file.")
    parser.add_argument("--input-dir", "-i", metavar="DIR", help="Directory containing Songs.db and SongWords.db to modify.")
    parser.add_argument("--output-dir", "-o", metavar="DIR", help="Directory to save the modified Songs.db and SongWords.db. Defaults to input-dir if not specified.")
    parser.add_argument("--dir", "-d", metavar="DIR", help="Directory containing .txt files to process.")
    parser.add_argument("files", nargs="*", help="List of .txt files to process.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.")
    args = parser.parse_args()

    verbose = args.verbose
    log("Starting EasyWorship Songs and SongWords management tool.", verbose)

    # Check if backups should be listed
    if args.list_backups:
        print(f"Backups are stored in: {DEFAULT_BACKUP_DIR}")
        list_backups(verbose)
        return

    # Determine the input directory
    input_dir = args.input_dir
    if not input_dir:
        # Search for Databases directory and suggest the probable location
        default_search_root = r"C:\Users\Public\Documents\Softouch\Easyworship"
        suggested_dir = search_for_databases_dir(default_search_root, verbose)
        if suggested_dir:
            probable_path = os.path.join(suggested_dir, "Data")
            print(f"Error: --input-dir is required. It seems like the directory you're looking for is at:\n  {probable_path}")
        else:
            print("Error: --input-dir is required. Unable to find the Databases directory automatically.")
        exit(1)

    # Determine the output directory (default to input-dir if not specified)
    output_dir = args.output_dir if args.output_dir else input_dir

    songs_db_path, songwords_db_path = get_db_paths(input_dir, verbose)

    # Check if a backup should be restored
    if args.restore_backup:
        print(f"Restoring backup from: {DEFAULT_BACKUP_DIR}")
        restore_backup(input_dir, args.restore_backup, verbose)
        print("Backup restored successfully.")
        return

    # Process files if specified
    file_paths = args.files
    if args.dir:
        log(f"Searching for .txt files in directory: {args.dir}", verbose)
        file_paths.extend(list_txt_files_in_dir(args.dir, verbose))

    if not file_paths:
        print("Error: No files or directories specified.")
        exit(1)

    # Create backups and inform the user
    print(f"Backups will be stored in: {DEFAULT_BACKUP_DIR}")
    backup_names = create_backup(songs_db_path, songwords_db_path, verbose)

    # Handle the case where backup creation failed
    if not backup_names:
        print("Error: Backups could not be created due to issues with the database.")
        return

    print(f"Backups created:\n - Songs: {backup_names['songs']}\n - SongWords: {backup_names['songwords']}")

    # Process the files
    process_txt_files(file_paths, songs_db_path, songwords_db_path, output_dir, verbose)

    # Final confirmation and backup details
    print("Processing complete.")
    print(f"Backup files are stored in: {DEFAULT_BACKUP_DIR}")
    print(f"Backup names:\n - Songs: {backup_names['songs']}\n - SongWords: {backup_names['songwords']}")

if __name__ == "__main__":
    main()
