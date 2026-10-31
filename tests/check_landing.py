import json, mimetypes, os, shutil, tempfile
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
# Frontend contract checks use mocked API responses, not a real vault or model.
root=Path(__file__).resolve().parents[1] / 'app' / 'static'
status={'local':{'up':True,'models':['gemma3:4b'],'default':'gemma3:4b'},'cloud':{'allowed':False,'providers':{}},'vault':{'name':'test','inbox':0,'lint_errors':0,'staged_changes':False},'limits':{'max_upload_mb':50},'domains':[],'auto':{'installed':True},'rag':{'chunks':12,'notes':3,'embed_installed':True,'answer_installed':True,'embed_model':'embeddinggemma','answer_model':'gemma3:4b'}}
result={'n':1,'title':'A connected idea','path':'ideas/test.md','snippet':'A note about learning.','sensitivity':'internal','inbox':False,'marks':[]}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 for width,scheme in [(1440,'light'),(390,'light'),(1440,'dark'),(390,'dark')]:
  page=b.new_page(viewport={'width':width,'height':1000},color_scheme=scheme)
  errors=[]; requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  def route(r):
   path=urlparse(r.request.url).path
   if path.startswith('/api/'):
    requests.append((path,r.request.post_data,r.request.url))
    data=status if path=='/api/status' else {'results':[result],'ms':2,'vector':False} if path=='/api/search' else []
    if path=='/api/ask':
     events=[{'type':'results','results':[result],'ms':2,'vector':False},{'type':'done','text':'A connected idea [1].','sent':[1],'model':'test'}]
     r.fulfill(content_type='application/x-ndjson',body='\n'.join(json.dumps(e) for e in events)+'\n'); return
    if path=='/api/drop': data={'id':'test'}
    r.fulfill(content_type='application/json',body=json.dumps(data)); return
   f=root/('index.html' if path=='/' else path.lstrip('/'))
   r.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
  page.route('http://intake.test/**',route)
  page.goto('http://intake.test/#k=test-key'); page.wait_for_timeout(350)
  assert page.locator('.home__mark').is_visible()
  assert not page.locator('#clearSearch').is_visible()
  assert not page.locator('#askClient').is_checked()
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'Overflow at {width}'
  page.screenshot(path=str(Path(tempfile.gettempdir()) / f'intake-{width}-{scheme}.png'),full_page=True)
  page.locator('[data-query]').first.click(); page.wait_for_timeout(400)
  assert page.locator('#askInput').input_value()=='What have I learnt recently?'
  assert page.locator('#askResults').inner_text().find('A connected idea')>=0
  assert not any(x[0] in ('/api/ask','/api/drop') for x in requests)
  page.locator('#askClient').check(); page.wait_for_timeout(350)
  page.locator('#askBtn').click(); page.wait_for_timeout(200)
  assert 'A connected idea' in page.locator('#askAnswer').inner_text()
  body=json.loads(next(x[1] for x in requests if x[0]=='/api/ask'))
  assert body['client'] is True and body['inbox'] is False and body['people'] is False
  page.locator('#clearSearch').click(); assert page.locator('.home__mark').is_visible()
  page.locator('#tellClient').check(); page.locator('#askInput').fill('Remember this thought')
  page.locator('#tellBtn').click(); page.wait_for_timeout(100)
  assert any(x[0]=='/api/drop' and 'client=1' in x[2] for x in requests)
  assert page.locator('#askInput').input_value()==''
  with page.expect_file_chooser(): page.locator('#homeAddFiles').click()
  page.locator('[data-home-tab="tabActivity"]').click(); assert page.locator('#panelActivity').is_visible()
  page.locator('#backHome').click(); assert page.locator('#panelAsk').is_visible()
  assert not errors,errors
  print(f'PASS {width}px {scheme}: layout, suggestions, scope, streamed answer, clear, save, file picker, navigation; no JS errors')
  page.close()
 b.close()
