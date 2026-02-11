import sqlite3
import os

# Find database file
db_files = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.db') or file.endswith('.sqlite'):
            db_files.append(os.path.join(root, file))

print('Database files found:')
for f in db_files[:5]:
    print(f'  {f}')

if not db_files:
    print('No database files found')
    exit()

db_path = db_files[0]
print(f'\nUsing database: {db_path}')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f'\nTables: {tables[:10]}')
    
    # Look for parsing_runs table
    if 'parsing_runs' in tables:
        cursor.execute('SELECT COUNT(*) FROM parsing_runs')
        count = cursor.fetchone()[0]
        print(f'\nTotal parsing runs: {count}')
        
        # Search for rzhevka-market.ru
        cursor.execute("""
            SELECT id, created_at, status, keyword 
            FROM parsing_runs 
            WHERE keyword LIKE '%rzhevka-market.ru%' 
            LIMIT 5
        """)
        results = cursor.fetchall()
        print(f'\nSearch results for rzhevka-market.ru:')
        for row in results:
            print(f'  ID: {row[0]}, Date: {row[1]}, Status: {row[2]}, Keyword: {row[3]}')
    
    # Also check suppliers table
    if 'suppliers' in tables:
        cursor.execute("""
            SELECT id, created_at, data_status, type, inn, email 
            FROM suppliers 
            WHERE domain LIKE '%rzhevka-market.ru%' 
            LIMIT 5
        """)
        results = cursor.fetchall()
        print(f'\nSuppliers with rzhevka-market.ru:')
        for row in results:
            print(f'  ID: {row[0]}, Date: {row[1]}, Status: {row[2]}, Type: {row[3]}, INN: {row[4]}, Email: {row[5]}')
    
    conn.close()
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
