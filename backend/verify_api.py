"""Exercise all API operations using isolated keys and synthetic PDFs.

Local mode uses the real application, worker and configured AI provider in an
isolated temporary database. AWS mode requires PAPERSIGNAL_TEST_ADMIN_TOKEN in
.env (or the process environment). No credentials or customer data enter reports.
Only keys/jobs created in this run may be deleted or revoked.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

import fitz
import httpx
from dotenv import dotenv_values


def make_pdfs():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(60, 60, 540, 700),
            'SYNTHETIC TEST INVOICE\nInvoice number: PS-TEST-042\nCurrency: INR\n'
            'Item: Test service\nQuantity: 1\nTotal amount: 42.50\n'
            'This document contains artificial test data only. No payment is due.', fontsize=16)
        digital = doc.tobytes()
        png = page.get_pixmap(dpi=144).tobytes('png')
        protected = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw='test-owner', user_pw='test-password')
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_image(page.rect, stream=png)
        scan = doc.tobytes()
    return digital, scan, protected


class Verification:
    def __init__(self, client, admin, target, report):
        self.client, self.admin, self.target, self.report_path = client, admin, target, report
        self.keys, self.jobs, self.results = {}, {}, []
        self.prefix = 'Documentation verification ' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.started = datetime.now(timezone.utc).isoformat()
        self.schema = json.dumps({'type':'object','properties':{
            'invoiceNumber':{'type':'string'}, 'totalAmount':{'type':'number'},
            'currency':{'type':'string'}, 'missingField':{'type':'string','description':'A fax number, or null when not present'}}})

    def record(self, name, passed, detail='', operation=None):
        item = dict(name=name, status='passed' if passed else 'failed', detail=detail)
        if operation: item['operation'] = operation
        self.results.append(item)
        print(f"{item['status'].upper()}: {name}" + (f' ({detail})' if detail else ''), flush=True)

    def call(self, method, path, expected, name, key=None, admin=False, **kwargs):
        headers = kwargs.pop('headers', {})
        if key: headers['X-API-Key'] = self.keys[key]['key']
        if admin: headers['X-Admin-Token'] = self.admin
        response = self.client.request(method, path, headers=headers, **kwargs)
        self.record(name, response.status_code == expected, f'HTTP {response.status_code}; expected {expected}', f'{method} {path.split("?")[0]}')
        return response

    def issue(self, label, rate=120, quota=10):
        r = self.call('POST','/api/admin/keys',201,f'Create isolated {label} key',admin=True,
                      json={'name':self.prefix+' '+label,'rate_limit_per_minute':rate,'monthly_document_quota':quota})
        if r.status_code != 201: raise RuntimeError('Cannot create isolated test keys; stopping mutations.')
        self.keys[label] = r.json()

    def upload(self, name, content, key='A', mode='auto', expected=202, template=None):
        r = self.call('POST','/api/jobs',expected,name,key=key,
                      files={'file':('synthetic-test.pdf',content,'application/pdf')},
                      data={'output_template':template if template is not None else self.schema,'ocr_mode':mode})
        if r.status_code == 202:
            job = r.json(); self.jobs[job['id']] = {'key':key,'test':name,'mode':mode}
            return job
        return None

    def run(self):
        health = self.call('GET','/api/health',200,'Public health').json()
        self.record('Service key mode enabled',health.get('require_api_key') is True)
        self.call('GET','/api/openapi.json',200,'OpenAPI contract available')
        self.call('GET','/api/docs',200,'Swagger page available')
        self.call('GET','/api/usage',401,'Missing client key rejected')
        self.call('GET','/api/jobs',401,'Wrong client key rejected',headers={'X-API-Key':'invalid-verification-key'})
        self.call('GET','/api/admin/keys',401,'Missing admin token rejected')
        if not self.admin: raise RuntimeError('A valid test admin token is required for isolated full-suite testing.')
        for label,rate,quota in [('A',120,10),('B',120,1),('R',2,10)]: self.issue(label,rate,quota)
        listed = self.call('GET','/api/admin/keys',200,'Admin key listing',admin=True).json()
        own = {v['api_key']['id'] for v in self.keys.values()}
        self.record('Created keys listed without raw credentials',own.issubset({r['id'] for r in listed}) and all('key' not in r for r in listed))
        self.call('POST','/api/admin/keys',422,'Invalid key settings rejected',admin=True,json={'name':' ','rate_limit_per_minute':0})
        initial=self.call('GET','/api/usage',200,'New client usage',key='A').json()
        self.record('New key starts at zero documents',initial.get('documents_this_month')==0)
        self.call('GET','/api/usage',200,'Bearer authentication',headers={'Authorization':'Bearer '+self.keys['A']['key']})
        self.call('GET','/api/usage',401,'X-API-Key takes precedence over Bearer',headers={'Authorization':'Bearer '+self.keys['A']['key'],'X-API-Key':'invalid'})
        digital,scan,protected=make_pdfs()
        self.upload('Invalid schema rejected',digital,expected=422,template='{bad-json}')
        self.upload('Example object is not a schema',digital,expected=422,template='{"totalAmount":42}')
        self.upload('Unsupported OCR mode rejected',digital,mode='invalid',expected=422)
        self.call('POST','/api/jobs',422,'Missing required schema rejected',key='A',files={'file':('test.pdf',digital,'application/pdf')})
        self.upload('Non-PDF rejected',b'not a pdf',expected=400)
        self.upload('Empty file rejected',b'',expected=400)
        self.upload('Protected PDF rejected',protected,expected=400)
        with fitz.open() as doc:
            for _ in range(health['max_pdf_pages']+1): doc.new_page()
            self.upload('Page limit enforced before processing',doc.tobytes(),expected=400)
        self.call('GET','/api/jobs/batch?ids=',422,'Empty multi-ID query rejected',key='A')
        self.call('GET','/api/jobs/batch',422,'Missing multi-ID query rejected',key='A')
        self.call('GET','/api/jobs/batch',422,'More than 50 IDs rejected',key='A',params={'ids':','.join('test'+str(i) for i in range(51))})
        self.call('POST','/api/jobs/batch',422,'Batch file-count limit',key='A',
                  files=[('files',('invalid.pdf',b'invalid','application/pdf')) for _ in range(health['max_batch_files']+1)],data={'output_template':self.schema})
        empty=self.call('POST','/api/jobs/batch',202,'All-invalid batch returns structured rejection',key='A',
                  files=[('files',('invalid.pdf',b'invalid','application/pdf'))],data={'output_template':self.schema}).json()
        self.record('Zero accepted files are reported',empty.get('accepted_count')==0 and empty.get('rejected_count')==1)
        self.call('GET','/api/batches/'+empty['batch_id'],404,'All-rejected batch has no stored jobs',key='A')

        single=self.upload('Digital PDF with OCR never',digital,mode='never')
        if not single: raise RuntimeError('Single submission did not return a job.')
        r=self.call('GET','/api/jobs/'+single['id'],200,'Read own submitted job',key='A')
        if r.json().get('status')=='processing':
            self.call('DELETE','/api/jobs/'+single['id'],409,'Processing job deletion blocked',key='A')
        self.call('GET','/api/jobs/'+single['id'],404,'Other key cannot read job',key='B')
        self.call('DELETE','/api/jobs/'+single['id'],404,'Other key cannot delete job',key='B')
        hidden=self.call('GET','/api/jobs/batch',200,'Multi-ID ownership filtering',key='B',params={'ids':single['id']}).json()
        self.record('Other-key jobs omitted from multi-ID results',hidden==[])
        batch=self.call('POST','/api/jobs/batch',202,'Batch accepts valid PDFs and rejects invalid PDF',key='A',
            files=[('files',('digital.pdf',digital,'application/pdf')),('files',('scan.pdf',scan,'application/pdf')),('files',('bad.pdf',b'invalid','application/pdf'))],
            data={'output_template':self.schema,'ocr_mode':'auto'}).json()
        self.record('Batch partial acceptance counts',batch.get('accepted_count')==2 and batch.get('rejected_count')==1)
        for j in batch['jobs']: self.jobs[j['id']]={'key':'A','test':'Batch '+j['file_name'],'mode':'auto'}
        self.call('GET','/api/batches/'+batch['batch_id'],200,'Read own batch',key='A')
        self.call('GET','/api/batches/'+batch['batch_id'],404,'Other key cannot read batch',key='B')
        self.upload('Scan with forced OCR',scan,mode='always')
        self.upload('Image-only PDF with OCR never fails clearly',scan,key='B',mode='never')
        self.upload('Monthly quota blocks a second document',digital,key='B',expected=402)
        self.call('GET','/api/usage',200,'Rate-limit first request',key='R')
        self.call('GET','/api/jobs',200,'Rate-limit second request',key='R')
        limited=self.call('GET','/api/usage',429,'Rate-limit third request blocked',key='R')
        self.record('Rate-limit response includes Retry-After',limited.headers.get('retry-after','').isdigit())

        pending=set(self.jobs); deadline=time.monotonic()+300
        while pending and time.monotonic()<deadline:
            for label in ('A','B'):
                ids=[j for j in pending if self.jobs[j]['key']==label]
                if not ids: continue
                r=self.client.get('/api/jobs/batch',params={'ids':','.join(ids)},headers={'X-API-Key':self.keys[label]['key']})
                if r.status_code==429: time.sleep(min(10,int(r.headers.get('retry-after','3')))); continue
                if r.status_code!=200: continue
                for job in r.json():
                    if job['status'] not in ('completed','failed'): continue
                    pending.discard(job['id']); self.jobs[job['id']]['outcome']=job
                    expected='failed' if label=='B' else 'completed'
                    self.record(self.jobs[job['id']]['test']+' final status',job['status']==expected,
                                'status='+job['status']+('; '+str(job.get('failure_code')) if job['status']=='failed' else ''))
                    if job['status']=='completed':
                        data=(job.get('result') or {}).get('data',{})
                        self.record(self.jobs[job['id']]['test']+' extracted values',data=={
                            'invoiceNumber':'PS-TEST-042','totalAmount':42.5,'currency':'INR','missingField':None},json.dumps(data))
                        self.record(self.jobs[job['id']]['test']+' result shape',all(k in job['result'] for k in ('data','evidence','warnings','request','document')))
            if pending: time.sleep(3)
        for j in pending: self.record(self.jobs[j]['test']+' completed within 300 seconds',False,'Polling deadline reached')
        recent=self.call('GET','/api/jobs?limit=100',200,'List own recent jobs',key='A').json()
        expected_ids={j for j,v in self.jobs.items() if v['key']=='A'}
        self.record('Recent jobs contain only this test key documents',{j['id'] for j in recent}==expected_ids)
        queried=self.call('GET','/api/jobs/batch',200,'Multi-ID deduplication and missing-ID behavior',key='A',params={'ids':single['id']+','+single['id']+',missing-test-id'}).json()
        self.record('Multi-ID duplicates removed and unknown ID omitted',[j['id'] for j in queried]==[single['id']])
        usage=self.call('GET','/api/usage',200,'Usage after submissions',key='A').json()
        self.record('Only accepted documents counted',usage.get('documents_this_month')==len(expected_ids))
        self.call('GET','/api/jobs/missing-test-id',404,'Unknown job lookup',key='A')
        self.call('DELETE','/api/jobs/missing-test-id',404,'Unknown job deletion',key='A')
        self.call('GET','/api/batches/missing-test-id',404,'Unknown batch lookup',key='A')
        self.call('DELETE','/api/admin/keys/missing-test-id',404,'Unknown key revocation',admin=True)

    def cleanup(self):
        remaining=[]
        for job_id,meta in self.jobs.items():
            try:
                r=self.client.get('/api/jobs/'+job_id,headers={'X-API-Key':self.keys[meta['key']]['key']})
                if r.status_code==200 and r.json()['status'] in ('completed','failed'):
                    self.call('DELETE','/api/jobs/'+job_id,204,'Delete synthetic test job',key=meta['key'])
                    self.call('GET','/api/jobs/'+job_id,404,'Deleted test job cannot be retrieved',key=meta['key'])
                elif r.status_code!=404: remaining.append(job_id)
            except Exception: remaining.append(job_id)
        for label,key in self.keys.items():
            if any(self.jobs[j]['key']==label for j in remaining): continue
            try:
                self.call('DELETE','/api/admin/keys/'+key['api_key']['id'],204,'Revoke isolated '+label+' key',admin=True)
                self.call('DELETE','/api/admin/keys/'+key['api_key']['id'],409,'Repeated revocation returns conflict',admin=True)
                self.call('GET','/api/usage',401,'Revoked key rejected',key=label)
            except Exception: self.record('Cleanup '+label+' key',False,'Operator reconciliation required')
        return remaining

    def execute(self):
        error=None
        try: self.run()
        except Exception as exc:
            error=type(exc).__name__
            self.record('Test run completed',False,error)
        remaining=self.cleanup()
        report={'started_at':self.started,'finished_at':datetime.now(timezone.utc).isoformat(),
                'target':self.target,'real_ai_provider':True,'synthetic_data_only':True,
                'passed':sum(r['status']=='passed' for r in self.results),
                'failed':sum(r['status']=='failed' for r in self.results),
                'remaining_test_job_ids':remaining,'checks':self.results,
                'job_outcomes':[{'test':m['test'],'status':m.get('outcome',{}).get('status','not_completed'),
                    'failure_code':m.get('outcome',{}).get('failure_code'),
                    'failure_stage':m.get('outcome',{}).get('failure_stage'),
                    'error':m.get('outcome',{}).get('error'),
                    'duration_ms':m.get('outcome',{}).get('duration_ms'),
                    'ocr_pages':m.get('outcome',{}).get('ocr_pages'),
                    'vision_pages':m.get('outcome',{}).get('vision_pages')} for m in self.jobs.values()]}
        # Provider error text can include details; retain a private local report, not public docs.
        self.report_path.parent.mkdir(parents=True,exist_ok=True)
        self.report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:report[k] for k in ('target','passed','failed','remaining_test_job_ids')}),flush=True)
        return 1 if error or report['failed'] or remaining else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',choices=['local','aws'],default='local')
    args=parser.parse_args()
    report=Path('data/verification')/(args.target+'-api-report.json')
    if args.target=='aws':
        values=dotenv_values('.env')
        admin=os.environ.get('PAPERSIGNAL_TEST_ADMIN_TOKEN') or values.get('PAPERSIGNAL_TEST_ADMIN_TOKEN')
        with httpx.Client(base_url='https://papersignal.duckdns.org',timeout=60) as client:
            return Verification(client,admin,args.target,report).execute()
    from pydantic import SecretStr
    from fastapi.testclient import TestClient
    from app import main as service
    from app.config import Settings
    from app.database import JobDatabase
    from app.storage import LocalStorage
    from app.job_service import JobRunner
    from app.api_keys import ApiKeyStore,RateLimiter
    data=Path(tempfile.mkdtemp(prefix='api-check-',dir=Path('data').resolve()))
    admin=secrets.token_urlsafe(32)
    settings=Settings(data_dir=data,require_api_key=True,admin_token=SecretStr(admin),local_worker_count=2)
    settings.prepare_directories()
    service.settings=settings
    service.database=JobDatabase(settings.database_path)
    service.storage=LocalStorage(settings.upload_dir,settings.max_upload_bytes)
    service.runner=JobRunner(settings,service.database)
    service.api_keys=ApiKeyStore(settings.api_keys_database_path)
    service.rate_limiter=RateLimiter()
    with TestClient(service.app) as client:
        return Verification(client,admin,'local FastAPI with real Mistral',report).execute()


if __name__=='__main__': raise SystemExit(main())
