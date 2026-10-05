import asyncio, json, os, tempfile, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from agent.pipeline import graph
from api.index import app

class SystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'SQLITE_PATH':self.tmp.name+'/test.db','ADMIN_TOKEN':'test-admin','CRON_SECRET':'test-cron'},clear=True);self.env.start()
        self.client=TestClient(app)
        self.auth={'Authorization':'Bearer test-admin'}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def fake_collect(self):
        async def fn(state):
            return {'items':[
                {'title':'China trade policy update','description':'Chinese export claim requires verification','url':'https://example.com/a?utm=test','source':'BBC','published':'today'},
                {'title':'China trade policy update','description':'duplicate','url':'https://example.com/b','source':'CNN','published':'today'},
                {'title':'Chinese economy growth','description':'economic market news','url':'https://example.com/c','source':'CNN','published':'today'},
                {'title':'Sports update','description':'unrelated','url':'https://example.com/d','source':'BBC','published':'today'},
                {'title':'Sponsored China deal','description':'advertisement','url':'https://example.com/e','source':'BBC','published':'today'}
            ],'errors':[],'stages':['采集原始内容']}
        return fn
    def test_pipeline_filters_and_preserves_uncertainty(self):
        with patch('agent.pipeline.collect',self.fake_collect()):r=asyncio.run(graph().ainvoke({'items':[],'errors':[],'stages':[]}))
        self.assertEqual(len(r['items']),2)
        self.assertEqual(len(r['stages']),5)
        self.assertTrue(all(i['verdict']=='证据不足' for i in r['items']))
        self.assertTrue(all(i['sentiment']=='待研判' for i in r['items']))
        self.assertNotIn('?',r['items'][0]['url'])
    def test_api_run_history_selection_review(self):
        self.assertEqual(self.client.post('/api/run').status_code,401)
        with patch('agent.pipeline.collect',self.fake_collect()):resp=self.client.post('/api/run',headers=self.auth)
        events=[json.loads(s[6:]) for s in resp.text.splitlines() if s.startswith('data: ')]
        self.assertEqual([e['type'] for e in events],['start']+['progress']*5+['done'])
        report=events[-1]['report'];rid=report['id'];item=report['items'][0]
        self.assertEqual(len(self.client.get('/api/reports').json()),1)
        self.assertEqual(len(self.client.get('/api/report/'+rid).json()['items']),2)
        self.assertEqual(self.client.post('/api/selections',headers=self.auth,json={'id':item['id'],'report_id':rid}).status_code,200)
        self.assertEqual(len(self.client.get('/api/selections',headers=self.auth).json()),1)
        review={'report_id':rid,'item_id':item['id'],'verdict':'已证伪','note':'已比对原始文件，具体内容和报道不一致。','evidence':[]}
        self.assertEqual(self.client.post('/api/review',headers=self.auth,json=review).status_code,400)
        review['evidence']=[{'source':'原始记录','url':'https://example.com/data','relation':'反对','quote':'原始数据的明确摘录'}]
        self.assertEqual(self.client.post('/api/review',headers=self.auth,json=review).status_code,200)
        saved=self.client.get('/api/report/'+rid).json()['items'][0]
        self.assertEqual(saved['verdict'],'已证伪');self.assertEqual(len(saved['review_history']),1)
    def test_cron_and_demo_isolation(self):
        self.assertEqual(self.client.get('/api/cron').status_code,401)
        with patch('agent.pipeline.collect',self.fake_collect()):res=self.client.get('/api/cron',headers={'Authorization':'Bearer test-cron'})
        self.assertEqual(res.status_code,200)
        self.assertTrue(self.client.get('/api/report/demo').json()['demo'])
        self.assertEqual(self.client.post('/api/selections',headers=self.auth,json={'id':'demo-0','report_id':'demo'}).status_code,400)
    def test_source_failure_is_not_successful_report(self):
        async def failed(state):return {'items':[],'errors':[{'source':str(i),'error':'denied'} for i in range(8)],'stages':['采集原始内容']}
        with patch('agent.pipeline.collect',failed):res=self.client.post('/api/run',headers=self.auth)
        self.assertIn('"type": "error"',res.text)
        self.assertEqual(self.client.get('/api/reports').json(),[])

if __name__=='__main__':unittest.main()
