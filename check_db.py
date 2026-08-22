import mysql.connector

try:
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='db_ipcr')
    cursor = conn.cursor()
    cursor.execute('SHOW TABLES')
    tables = cursor.fetchall()
    print("Tables:")
    for t in tables:
        print(t[0])
    
    # Also check if tbl_scoring or similar exists and get its columns
    for t in tables:
        if 'score' in t[0].lower() or 'rating' in t[0].lower() or 'scale' in t[0].lower() or 'evid' in t[0].lower():
            cursor.execute(f"SHOW COLUMNS FROM {t[0]}")
            columns = cursor.fetchall()
            print(f"\nColumns for {t[0]}:")
            for c in columns:
                print(c)
                
except Exception as e:
    print("Error:", e)
