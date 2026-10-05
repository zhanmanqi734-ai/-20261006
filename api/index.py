import asyncio, hmac, json, os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from urllib.parse import urlsplit
from agent import store
from agent.demo import demo_report
from agent.pipeline import graph
from agent.sources import SOURCES, UNAVAILABLE

app=FastAPI(title='TruthSeeker 真探',version='0.1.0')
ROOT=Path(__file__).resolve().parent.parent
lock=asyncio.Lock()

class Evidence(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    quote: str = Field(min_length=1, max_length=4000)
    relation: str

class Review(BaseModel):
    report_id: str
    item_id: str
    verdict: str
    note: str = Field(min_length=10, max_length=6000)
    evidence: list[Evidence] = Field(max_length=20)


def authorize(request, cron=False):
    key=os.getenv('CRON_SECRET' if cron else 'ADMIN_TOKEN')
    if not key:
        raise HTTPException(503, '请在环境设置中配置 '+('CRON_SECRET' if cron else 'ADMIN_TOKEN'))
    given=request.headers.get('authorization','').removeprefix('Bearer ')
    if not hmac.compare_digest(given,key):raise HTTPException(401,'需要任务管理员凭据')

def persisted_reports():
    if os.getenv('VERCEL') and not os.getenv('DATABASE_URL'):return []
    return store.reports()

@app.get('/')
def home():return FileResponse(ROOT/'web'/'index.html')

@app.get('/api/status')
def status():
    return {'database':bool(os.getenv('DATABASE_URL')),'storage':'PostgreSQL' if os.getenv('DATABASE_URL') else ('未配置' if os.getenv('VERCEL') else '本机 SQLite'),'ai':bool(os.getenv('LLM_API_KEY')),'x':bool(os.getenv('X_BEARER_TOKEN')),'schedule':'每天 08:00 Asia/Shanghai（UTC 00:00）','sources':[{'name':n,'url':u,'status':'待本轮请求验证'} for n,u in SOURCES]+[{'name':n,'status':'未接入：需确认授权或可靠公开源'} for n in UNAVAILABLE],'auth_required':True}

@app.get('/api/reports')
def reports():
    return [{'id':r['id'],'date':r['date'],'created_at':r['created_at'],'count':len(r['items'])} for r in persisted_reports()]

@app.get('/api/report/{rid}')
def report(rid:str):
    if rid=='demo':return demo_report()
    found=next((r for r in persisted_reports() if r['id']==rid),None)
    if not found:raise HTTPException(404,'报告不存在')
    return found

@app.get('/api/selections')
def selections(request:Request):
    authorize(request)
    return store.selections()

@app.post('/api/selections')
async def select(request:Request):
    authorize(request);body=await request.json()
    report=next((r for r in persisted_reports() if r['id']==body.get('report_id')),None)
    item=next((i for i in report['items'] if i['id']==body.get('id')),None) if report else None
    if not item:raise HTTPException(400,'只能选择已保存报告中的真实条目')
    item=dict(item);item.update(editor_status='待调查',report_id=report['id'],editor_note=str(body.get('note',''))[:2000]);store.select(item)
    return {'ok':True}

@app.post('/api/review')
async def review(body:Review, request:Request):
    authorize(request)
    if body.verdict not in ['证据不足','有证据支持','部分失实','已证伪','观点或预测']:
        raise HTTPException(400,'无效核查结论')
    report=next((r for r in persisted_reports() if r['id']==body.report_id),None)
    item=next((i for i in report['items'] if i['id']==body.item_id),None) if report else None
    if not item:raise HTTPException(404,'报告条目不存在')
    if body.verdict in ['有证据支持','部分失实','已证伪'] and not body.evidence:
        raise HTTPException(400,'实质结论必须附有证据')
    for e in body.evidence:
        if urlsplit(e.url).scheme not in ['http','https'] or not urlsplit(e.url).hostname:
            raise HTTPException(400,'证据必须为 HTTP(S) 链接')
        if e.relation not in ['支持','反对','背景']:raise HTTPException(400,'无效证据关系')
    record={'verdict':body.verdict,'note':body.note,'evidence':[e.model_dump() for e in body.evidence],'reviewed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
    item.setdefault('review_history',[]).append(record)
    item['verdict']=body.verdict
    item['review']=record
    store.save_report(report)
    if any(i['id']==item['id'] for i in store.selections()):store.select({**item,'report_id':body.report_id,'editor_status':'已复核'})
    return {'ok':True,'item':item}

def event(payload):return 'data: '+json.dumps(payload,ensure_ascii=False)+'\n\n'

async def execute():
    state={'items':[],'errors':[],'stages':[]}
    async for step in graph().astream(state,stream_mode='updates'):
        for node,update in step.items():
            state.update(update)
            yield {'type':'progress','step':node,'count':len(state['items']),'errors':state['errors']}
    now=datetime.now(ZoneInfo('Asia/Shanghai'))
    report={'id':now.strftime('%Y%m%d-%H%M%S-%f'),'date':now.strftime('%Y-%m-%d'),'created_at':now.isoformat(),'demo':False,**state}
    if not report['items'] and len(report['errors']) >= len(SOURCES):raise RuntimeError('所有采集源均不可用，本轮未生成报告')
    store.save_report(report)
    yield {'type':'done','report':report}

@app.post('/api/run')
async def run(request:Request):
    authorize(request)
    if lock.locked():raise HTTPException(409,'当前实例已有任务运行中')
    try:lease=store.acquire_lease()
    except Exception:raise HTTPException(503,'无法访问持久化存储，请检查 DATABASE_URL')
    if not lease:raise HTTPException(409,'已有监测任务运行中，请稍后重试')
    async def stream():
        async with lock:
            yield event({'type':'start'})
            try:
                async for payload in execute():yield event(payload)
            except Exception as exc:yield event({'type':'error','message':str(exc)[:300]})
            finally:store.release_lease(lease)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.get('/api/cron')
async def cron(request:Request):
    authorize(request,cron=True)
    if lock.locked():raise HTTPException(409,'任务正在运行')
    try:lease=store.acquire_lease()
    except Exception:raise HTTPException(503,'无法访问持久化存储，请检查 DATABASE_URL')
    if not lease:raise HTTPException(409,'已有监测任务运行中')
    async with lock:
        try:
            final=None
            async for payload in execute():final=payload
        finally:store.release_lease(lease)
    return {'ok':True,'report_id':final['report']['id']}
