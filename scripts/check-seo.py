from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, unquote
import json, urllib.request, xml.etree.ElementTree as ET, zipfile
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'dist';BASE='https://waymark-darya-career.shrewdstork3.chatgpt.site/'
class Page(HTMLParser):
 def __init__(self,html):
  super().__init__();self.tags=[];self.schema=[];self.read_schema=False;self.feed(html)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs);self.tags.append((tag,a));self.read_schema=tag=='script' and a.get('type')=='application/ld+json'
 def handle_data(self,data):
  if self.read_schema:self.schema.append(json.loads(data))
 def handle_endtag(self,tag):
  if tag=='script':self.read_schema=False
for lang,path in [('ru',''),('en','en/'),('kk','kk/')]:
 f=OUT/path/'index.html';html=f.read_text();p=Page(html);tags=p.tags
 assert next(a for t,a in tags if t=='html')['lang']==lang
 assert sum(t=='h1' for t,a in tags)==1
 ids=[a['id'] for t,a in tags if 'id'in a];assert len(ids)==len(set(ids))
 links=[a for t,a in tags if t=='link']
 assert next(a['href'] for a in links if a.get('rel')=='canonical')==BASE+path
 alternates={a['hreflang']:a['href'] for a in links if a.get('rel')=='alternate'}
 assert alternates=={'ru':BASE,'en':BASE+'en/','kk':BASE+'kk/','x-default':BASE}
 assert len(p.schema)==1;graph=p.schema[0]['@graph'];assert sum(v['@type']=='Service' for v in graph)==10
 assert next(v for v in graph if v['@type']=='WebPage')['inLanguage']==lang
 assert sum(t=='meta' and a.get('name')=='description' for t,a in tags)==1
 assert 'noindex' not in html and 'const pages=' not in html
 for tag,a in tags:
  value=a.get('href') if tag in ['a','link'] else a.get('src')
  if not value:continue
  if value.startswith('#'):assert value[1:]in ids,(lang,value)
  elif not urlparse(value).scheme:
   target=(f.parent/unquote(urlparse(value).path)).resolve()
   if target.is_dir():target=target/'index.html'
   assert target.is_file(),(lang,value,target)
 nav=[a for t,a in tags if t=='a' and a.get('data-lang')]
 assert len(nav)==3 and all('href'in a for a in nav)
 assert all('src'in a and 'width'in a and 'height'in a for t,a in tags if t=='img')
 print(lang,': HTML language, H1, metadata, canonical, hreflang, 10 schema services, asset links and anchors passed; HTML',f.stat().st_size,'bytes')
root=ET.parse(OUT/'sitemap.xml').getroot();assert len(root)==3
assert 'Sitemap: '+BASE+'sitemap.xml' in (OUT/'robots.txt').read_text()
for path in ['', 'en/', 'kk/', 'site.css', 'site.js', 'hero.jpg', 'favicon.svg', 'robots.txt', 'sitemap.xml', '?lang=en']:
 with urllib.request.urlopen('http://127.0.0.1:4173/'+path) as r:assert r.status==200
with zipfile.ZipFile(ROOT/'waymark-production.zip') as z:
 assert {'index.html','en/index.html','kk/index.html','robots.txt','sitemap.xml','site.js','site.css','hero.jpg','favicon.svg'}==set(z.namelist())
print('Sitemap, robots, production ZIP and 10 local HTTP routes passed.')
