import os, json, sqlite3, time, uuid
from datetime import datetime, timezone

def connect():
    if os.getenv('DATABASE_URL'):
        import psycopg
        return psycopg.connect(os.environ['DATABASE_URL'])
    if os.getenv('VERCEL'):
        raise RuntimeError('正式部署必须配置 DATABASE_URL；演示模式不写入临时文件系统。')
    return sqlite3.connect(os.getenv('SQLITE_PATH', '/tmp/truthseeker.db'))

def query(sql, args=(), fetch=False):
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS selections (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS job_leases (id TEXT PRIMARY KEY, token TEXT NOT NULL, expires DOUBLE PRECISION NOT NULL)')
        cur=db.execute(sql.replace('?', '%s') if os.getenv('DATABASE_URL') else sql,args)
        rows=cur.fetchall() if fetch else None
        db.commit()
        return rows

def save_report(report):
    query('INSERT INTO reports(id,payload) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(report['id'],json.dumps(report,ensure_ascii=False)))

def reports():
    return [json.loads(row[0]) for row in query('SELECT payload FROM reports ORDER BY id DESC',fetch=True)]

def selections():
    return [json.loads(row[0]) for row in query('SELECT payload FROM selections',fetch=True)]

def select(item):
    item['selected_at']=datetime.now(timezone.utc).isoformat()
    query('INSERT INTO selections(id,payload) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(item['id'],json.dumps(item,ensure_ascii=False)))

def acquire_lease():
    token=uuid.uuid4().hex
    query('INSERT INTO job_leases(id,token,expires) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET token=excluded.token,expires=excluded.expires WHERE job_leases.expires < ?',('monitor',token,time.time()+600,time.time()))
    rows=query('SELECT token FROM job_leases WHERE id=?',('monitor',),fetch=True)
    return token if rows and rows[0][0]==token else None

def release_lease(token):
    query('DELETE FROM job_leases WHERE id=? AND token=?',('monitor',token))
