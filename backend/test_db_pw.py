import sqlite3
from werkzeug.security import check_password_hash

conn = sqlite3.connect('backend/interviewer.db')
cursor = conn.cursor()
cursor.execute('SELECT password_hash FROM users WHERE email="admin@interview.ai"')
row = cursor.fetchone()
if row:
    h = row[0]
    print('Stored Hash:', h)
    print('Match admin123:', check_password_hash(h, 'admin123'))
else:
    print('Admin user not found')
conn.close()
