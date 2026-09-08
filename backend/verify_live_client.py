"""Test AWS consumer APIs with an existing client key and synthetic documents.

Never revokes the supplied key or touches jobs not created by this run. Requests
are paced below 60/minute. Reads credentials from the environment/.env only.
"""
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone

import fitz
import httpx
from dotenv import dotenv_values
from verify_api import make_pdfs


def main():
    key=os.environ.get('PAPERSIGNAL_TEST_API_KEY') or dotenv_values('.env').get('PAPERSIGNAL_TEST_API_KEY')
    if not key: raise SystemExit('Set PAPERSIGNAL_TEST_API_KEY securely.')
    checks=[]; jobs={}; last=0.; initial=None; outcomes=[]; started=datetime.now(timezone.utc).isoformat()
    schema=json.dumps({'type':'object','properties':{'invoiceNumber':{'type':'string'},'totalAmount':{'type':'number'},'currency':{'type':'string'},'missingField':{'type':'string','description':'Fax number, or null if absent'}}})
    report_path=Path('data/verification/aws-client-report.json')
    def record(name,passed,detail='',operation=None):
        checks.append(dict(name=name,status='passed' if passed else 'failed',detail=detail,operation=operation))
        print(('PASSED' if passed else 'FAILED')+': '+name+(' ('+detail+')' if detail else ''),flush=True)
    with httpx.Client(base_url='https://papersignal.duckdns.org',timeout=60) as client:
        def call(method,path,expected=None,name=None,auth=True,**kwargs):
            nonlocal last
            pause=1.1-(time.monotonic()-last)
            if pause>0: time.sleep(pause)
            headers=kwargs.pop('headers',{})
            if auth: headers['X-API-Key']=key
            last=time.monotonic()
            r=client.request(method,path,headers=headers,**kwargs)
            if expected is not None: record(name or path,r.status_code==expected,f'HTTP {r.status_code}; expected {expected}',method+' '+path.split('?')[0])
            return r
        def upload(name,pdf,mode='auto',expected=202,template=None):
            r=call('POST','/api/jobs',expected,name,files={'file':('papersignal-synthetic-test.pdf',pdf,'application/pdf')},
                   data={'output_template':schema if template is None else template,'ocr_mode':mode})
            if r.status_code==202: jobs[r.json()['id']]={'test':name,'expected':'failed' if name=='Scan without OCR' else 'completed'}
            return r
        try:
            health=call('GET','/api/health',200,'Public health',auth=False).json()
            call('GET','/api/openapi.json',200,'OpenAPI available',auth=False)
            call('GET','/api/docs',200,'Swagger available',auth=False)
            initial_response=call('GET','/api/usage',200,'Supplied client key works')
            if initial_response.status_code!=200: raise RuntimeError('Client credential rejected')
            initial=initial_response.json()['documents_this_month']
            if initial_response.json()['documents_remaining']<5: raise RuntimeError('Insufficient quota for five test documents')
            call('GET','/api/usage',401,'Missing client key rejected',auth=False)
            call('GET','/api/jobs',401,'Wrong key rejected',auth=False,headers={'X-API-Key':'invalid-test-key'})
            call('GET','/api/usage',200,'Bearer authentication',auth=False,headers={'Authorization':'Bearer '+key})
            call('GET','/api/usage',401,'X-API-Key precedence',auth=False,headers={'X-API-Key':'invalid-test-key','Authorization':'Bearer '+key})
            for method,path,kwargs in [('GET','/api/admin/keys',{}),('POST','/api/admin/keys',{'json':{'name':'unauthorized-test'}}),('DELETE','/api/admin/keys/not-a-real-test-id',{})]:
                call(method,path,401,'Client key cannot use admin '+method,**kwargs)
            digital,scan,protected=make_pdfs()
            upload('Invalid JSON rejected',digital,expected=422,template='{bad}')
            upload('Example JSON rejected',digital,expected=422,template='{"totalAmount":42}')
            upload('Unsupported OCR mode rejected',digital,mode='unsupported',expected=422)
            call('POST','/api/jobs',422,'Missing schema rejected',files={'file':('test.pdf',digital,'application/pdf')})
            upload('Invalid PDF rejected',b'not PDF',expected=400)
            upload('Empty PDF rejected',b'',expected=400)
            upload('Protected PDF rejected',protected,expected=400)
            with fitz.open() as doc:
                for _ in range(health['max_pdf_pages']+1): doc.new_page()
                upload('Page limit enforced',doc.tobytes(),expected=400)
            call('GET','/api/jobs/batch?ids=',422,'Empty job-ID list rejected')
            call('GET','/api/jobs/batch',422,'Missing job-ID list rejected')
            call('GET','/api/jobs/batch',422,'More than 50 IDs rejected',params={'ids':','.join(str(i) for i in range(51))})
            call('POST','/api/jobs/batch',422,'Batch file-count limit',files=[('files',('bad.pdf',b'bad','application/pdf')) for _ in range(health['max_batch_files']+1)],data={'output_template':schema})
            empty=call('POST','/api/jobs/batch',202,'All-invalid batch response',files=[('files',('bad.pdf',b'bad','application/pdf'))],data={'output_template':schema}).json()
            record('All-invalid batch counts',empty.get('accepted_count')==0 and empty.get('rejected_count')==1)
            call('GET','/api/batches/'+empty['batch_id'],404,'All-rejected batch lookup')
            single=upload('Digital PDF extraction',digital,mode='never')
            if single.status_code!=202: raise RuntimeError('Upload not accepted')
            single_id=single.json()['id']
            running=call('GET','/api/jobs/'+single_id,200,'Read submitted job').json()
            if running['status']=='processing': call('DELETE','/api/jobs/'+single_id,409,'Processing job cannot be deleted')
            batch=call('POST','/api/jobs/batch',202,'Submit mixed batch',files=[('files',('digital.pdf',digital,'application/pdf')),('files',('scan.pdf',scan,'application/pdf')),('files',('bad.pdf',b'bad','application/pdf'))],data={'output_template':schema,'ocr_mode':'auto'}).json()
            record('Batch accepts two files and rejects one',batch.get('accepted_count')==2 and batch.get('rejected_count')==1)
            for j in batch['jobs']: jobs[j['id']]={'test':'Batch '+j['file_name'],'expected':'completed'}
            call('GET','/api/batches/'+batch['batch_id'],200,'Read submitted batch')
            upload('Scan with forced OCR',scan,mode='always')
            upload('Scan without OCR',scan,mode='never')
            pending=set(jobs); deadline=time.monotonic()+300
            while pending and time.monotonic()<deadline:
                r=call('GET','/api/jobs/batch',params={'ids':','.join(pending)})
                if r.status_code==429:
                    time.sleep(min(60,int(r.headers.get('retry-after','5')))); continue
                if r.status_code!=200: time.sleep(3); continue
                for job in r.json():
                    if job['status'] not in ('completed','failed'): continue
                    pending.discard(job['id'])
                    meta=jobs[job['id']]; meta['outcome']=job
                    record(meta['test']+' final status',job['status']==meta['expected'],job['status']+'; '+str(job.get('failure_code') or 'no failure'))
                    if job['status']=='completed':
                        data=job['result']['data']
                        record(meta['test']+' correct extracted values',data=={'invoiceNumber':'PS-TEST-042','totalAmount':42.5,'currency':'INR','missingField':None},json.dumps(data))
                        record(meta['test']+' complete result fields',all(k in job['result'] for k in ['data','evidence','warnings','request','document']))
                if pending: time.sleep(3)
            for job_id in pending: record(jobs[job_id]['test']+' finished in 300 seconds',False,'Deadline reached')
            recent=call('GET','/api/jobs?limit=100',200,'List recent jobs').json()
            record('Test jobs appear in recent list',set(jobs).issubset({j['id'] for j in recent}))
            selected=call('GET','/api/jobs/batch',200,'Read selected jobs',params={'ids':single_id+','+single_id+',missing-test-id'}).json()
            record('Multi-ID deduplication and missing-ID behavior',[j['id'] for j in selected]==[single_id])
            usage=call('GET','/api/usage',200,'Usage after accepted uploads').json()
            record('Accepted test documents counted',usage['documents_this_month']>=initial+len(jobs))
            call('GET','/api/jobs/missing-test-id',404,'Unknown job lookup')
            call('GET','/api/batches/missing-test-id',404,'Unknown batch lookup')
            call('DELETE','/api/jobs/missing-test-id',404,'Unknown job deletion')
        except Exception as exc: record('Test suite completion',False,type(exc).__name__)
        finally:
            remaining=[]
            for job_id,meta in jobs.items():
                try:
                    r=call('GET','/api/jobs/'+job_id)
                    if r.status_code==200 and r.json()['status'] in ('completed','failed'):
                        meta.setdefault('outcome',r.json())
                        deleted=call('DELETE','/api/jobs/'+job_id,204,'Delete only this run synthetic job')
                        if deleted.status_code==204: call('GET','/api/jobs/'+job_id,404,'Deleted test job no longer available')
                        else: remaining.append(job_id)
                    elif r.status_code!=404: remaining.append(job_id)
                except Exception: remaining.append(job_id)
            for meta in jobs.values():
                job=meta.get('outcome',{})
                outcomes.append({'test':meta['test'],'status':job.get('status','not_completed'),
                    'failure_code':job.get('failure_code'),'failure_stage':job.get('failure_stage'),
                    'error':job.get('error'),'duration_ms':job.get('duration_ms'),
                    'ocr_pages':job.get('ocr_pages'),'vision_pages':job.get('vision_pages')})
            result={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'target':'AWS live service',
                    'passed':sum(c['status']=='passed' for c in checks),'failed':sum(c['status']=='failed' for c in checks),
                    'checks':checks,'job_outcomes':outcomes,'remaining_test_job_ids':remaining,
                    'not_tested':['Admin positive operations: client key cannot manage keys','Cross-key isolation: only one live key available','Quota exhaustion and intentional rate saturation: shared live key preserved','Large-upload proxy capacity and restart/load tests']}
            report_path.parent.mkdir(parents=True,exist_ok=True); report_path.write_text(json.dumps(result,indent=2),encoding='utf8')
            print(json.dumps({k:result[k] for k in ['target','passed','failed','remaining_test_job_ids']}),flush=True)
            return 1 if result['failed'] or remaining else 0

if __name__=='__main__': raise SystemExit(main())
