"""Build crawlable localized static pages from the retained landing-page template.
Override SITE_URL when moving to a public/custom domain, then rebuild.
"""
from pathlib import Path
from html import escape, unescape
import json, os, re, zipfile
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'dist'
BASE=os.environ.get('SITE_URL','https://waymark-darya-career.shrewdstork3.chatgpt.site').rstrip('/')+'/'
s=(ROOT/'src/site.html').read_text()
m=re.search(r'const pages=(\{.*?\});',s,re.S);pages=json.loads(m[1])
meta={
'ru':{'title':'Карьерный консультант в Алматы и онлайн — Дарья Хамидуллина','description':'Карьерные консультации, резюме и LinkedIn, подготовка к интервью. HR-консалтинг, IT-рекрутинг и Executive Search для бизнеса. Дарья Хамидуллина — Алматы и онлайн.','h1':'Карьерный консультант<br>и HR-консалтинг<br><em>в Алматы и онлайн.</em>','services':'Карьерные консультации,<br>резюме и подготовка к интервью','business':'HR-консалтинг, IT-рекрутинг<br>и Executive Search для бизнеса','name':'Дарья Хамидуллина','job':'Карьерный консультант и HR-консультант','locale':'ru_KZ'},
'en':{'title':'Career Consultant in Almaty & Online — Darya Khamidullina','description':'Career consulting, CV and LinkedIn reviews, interview preparation. HR consulting, IT recruitment and Executive Search for businesses. Almaty and online worldwide.','h1':'Career consulting<br>and HR consulting<br><em>in Almaty and online.</em>','services':'Career consulting,<br>CV reviews and interview preparation','business':'HR consulting, IT recruitment<br>and Executive Search for business','name':'Darya Khamidullina','job':'Career consultant and HR consultant','locale':'en_KZ'},
'kk':{'title':'Алматыда және онлайн мансап кеңесшісі — Дарья Хамидуллина','description':'Мансаптық кеңес, түйіндеме мен LinkedIn профилін талдау, сұхбатқа дайындық. Бизнеске HR-консалтинг, IT-рекрутинг және Executive Search. Алматы және онлайн.','h1':'Мансап кеңесі<br>және HR-консалтинг<br><em>Алматыда және онлайн.</em>','services':'Мансап кеңесі, түйіндеме<br>және сұхбатқа дайындық','business':'Бизнеске HR-консалтинг,<br>IT-рекрутинг және Executive Search','name':'Дарья Хамидуллина','job':'Мансап және HR кеңесшісі','locale':'kk_KZ'}}
paths={'ru':'','en':'en/','kk':'kk/'}
def text(h):return re.sub(r'\s+',' ',unescape(re.sub('<[^>]+>',' ',h))).strip()
def schema(lang,html):
 c=meta[lang];url=BASE+paths[lang];person=BASE+'#person'
 services=[]
 for article in re.findall(r'<article class="offer\b.*?</article>',html,re.S):
  name=text(re.search(r'<h3[^>]*>(.*?)</h3>',article,re.S)[1]);sid=re.search(r'id="([^"]+)"',article)[1]
  item={'@type':'Service','@id':url+'#'+sid,'name':name,'url':url+'#'+sid,'provider':{'@id':person},'areaServed':{'@type':'Place','name':'Online'},'availableChannel':{'@type':'ServiceChannel','serviceUrl':url+'#contact'}}
  amount=re.search(r'<strong>([\d\s]+) ₸</strong>',article)
  if amount:item['offers']={'@type':'Offer','price':re.sub(r'\s','',amount[1]),'priceCurrency':'KZT','url':url+'#'+sid}
  services.append(item)
 business=html.split('<ul class="business-list">')[1].split('</ul>')[0]
 for i,h in enumerate(re.findall(r'<li>(.*?)</li>',business,re.S),1):
  service={'@type':'Service','@id':url+'#business-service-'+str(i),'name':text(re.search(r'<h3>(.*?)</h3>',h,re.S)[1]),'provider':{'@id':person},'url':url+'#business'}
  desc=re.search(r'<p>(.*?)</p>',h,re.S)
  if desc:service['description']=text(desc[1])
  services.append(service)
 return {'@context':'https://schema.org','@graph':[
 {'@type':'Person','@id':person,'name':c['name'],'url':BASE,'jobTitle':c['job'],'email':'darya.kh.alex@gmail.com','sameAs':['https://t.me/DaryaKHnikn'],'workLocation':{'@type':'Place','name':'Almaty, Kazakhstan'},'knowsLanguage':['ru','en','kk']},
 {'@type':'WebSite','@id':BASE+'#website','url':BASE,'name':'Дарья Хамидуллина — карьерная стратегия и HR-консалтинг','inLanguage':['ru','en','kk'],'publisher':{'@id':person}},
 {'@type':'WebPage','@id':url+'#webpage','url':url,'name':c['title'],'description':c['description'],'inLanguage':lang,'isPartOf':{'@id':BASE+'#website'},'about':{'@id':person},'mainEntity':{'@id':url+'#services-catalog'}},
 {'@type':'OfferCatalog','@id':url+'#services-catalog','name':c['services'].replace('<br>',' '),'itemListElement':[{'@type':'Offer','itemOffered':{'@id':v['@id']}} for v in services]},*services]}
css=re.search(r'<style>(.*?)</style>',s,re.S)[1]
css=css.replace('.languages button','.languages a')
css+='\n.languages a{display:inline-flex;align-items:center;justify-content:center;line-height:1.65;text-decoration:none}\n'
(OUT/'site.css').write_text(css)
runtime=re.search(r'<script>const pages=.*?</script>',s,re.S)[0][len('<script>'):-len('</script>')]
runtime=re.sub(r'^const pages=\{.*?\};\s*','',runtime,count=1,flags=re.S)
start=runtime.index('function setMetadata(');end=runtime.index('function bind(',start)
runtime=runtime[:start]+"function setMetadata(lang){document.documentElement.lang=lang}\n"+runtime[end:]
runtime=runtime.replace("button.setAttribute('aria-pressed',String(button.dataset.lang===lang));button.onclick=()=>setLanguage(button.dataset.lang)","if(button.dataset.lang===lang)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current')")
start=runtime.index('function setLanguage(');end=runtime.index('if(location.hash)',start)
runtime=runtime[:start]+"bind(document.documentElement.lang);\n"+runtime[end:]
# Old query-string bookmarks remain usable, while clean static paths are canonical.
runtime="const legacyLanguage=new URLSearchParams(location.search).get('lang');if(['ru','en','kk'].includes(legacyLanguage)){const link=document.querySelector('[data-lang=\"'+legacyLanguage+'\"]');if(link)location.replace(link.href+location.hash)}\n"+runtime
(OUT/'site.js').write_text(runtime)
for lang,html in pages.items():
 c=meta[lang];prefix='./' if lang=='ru' else '../';url=BASE+paths[lang]
 html=re.sub(r'<h1>.*?</h1>','<h1>'+c['h1']+'</h1>',html,count=1,flags=re.S)
 html=re.sub(r'(id="services".*?<h2>).*?</h2>',lambda m:m[1]+c['services']+'</h2>',html,count=1,flags=re.S)
 html=re.sub(r'(<h2 id="business-title">).*?</h2>',lambda m:m[1]+c['business']+'</h2>',html,count=1,flags=re.S)
 def language_link(m):
  code=m[1];href=prefix+paths[code]
  return '<a data-lang="'+code+'" href="'+href+'" hreflang="'+code+'" lang="'+code+'"'+(' class="active" aria-current="page"' if code==lang else '')+'>'+m[2]+'</a>'
 html=re.sub(r'<button data-lang="(ru|kk|en)">(.*?)</button>',language_link,html)
 html=html.replace('src="./hero.jpg"','src="'+prefix+'hero.jpg"')
 data=schema(lang,html)
 head='<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0c213b">'
 head+='<title>'+escape(c['title'])+'</title><meta name="description" content="'+escape(c['description'],quote=True)+'">'
 head+='<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="'+url+'">'
 for code in ['ru','en','kk','x-default']:
  head+='<link rel="alternate" hreflang="'+code+'" href="'+BASE+paths.get(code,'')+'">'
 for prop,val in {'og:type':'website','og:site_name':'Дарья Хамидуллина','og:title':c['title'],'og:description':c['description'],'og:url':url,'og:locale':c['locale'],'og:image':BASE+'hero.jpg','og:image:width':'1122','og:image:height':'1402','og:image:alt':{'ru':'Архитектурная иллюстрация: выбор карьерного пути','en':'Architectural illustration of choosing a career path','kk':'Мансап жолын таңдау туралы сәулеттік иллюстрация'}[lang]}.items():
  head+='<meta property="'+prop+'" content="'+escape(val,quote=True)+'">'
 for other in meta:
  if other!=lang:head+='<meta property="og:locale:alternate" content="'+meta[other]['locale']+'">'
 for name,val in {'twitter:card':'summary_large_image','twitter:title':c['title'],'twitter:description':c['description'],'twitter:image':BASE+'hero.jpg'}.items():head+='<meta name="'+name+'" content="'+escape(val,quote=True)+'">'
 head+='<link rel="icon" href="'+prefix+'favicon.svg" type="image/svg+xml"><link rel="preload" as="image" href="'+prefix+'hero.jpg" fetchpriority="high"><link rel="stylesheet" href="'+prefix+'site.css">'
 head+='<script type="application/ld+json">'+json.dumps(data,ensure_ascii=False).replace('</','<\\/')+'</script><script src="'+prefix+'site.js" defer></script>'
 # Retain progress indicator and all page UI, but deliver real content without JS.
 body_start=s.index('<body>')+len('<body>');site_start=s.index('<div id="site">',body_start)
 body_prefix=s[body_start:site_start]
 output='<!DOCTYPE html><html lang="'+lang+'"><head>'+head+'</head><body>'+body_prefix+'<div id="site">'+html+'</div></body></html>'
 dest=OUT/paths[lang]/'index.html';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(output)
(OUT/'favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 220"><rect width="220" height="220" rx="54" fill="#102b4c"/><rect x="83" y="59" width="97" height="40" rx="20" fill="#79c6ed"/><rect x="39" y="123" width="97" height="40" rx="20" fill="#fff"/></svg>')
(OUT/'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: '+BASE+'sitemap.xml\n')
ET.register_namespace('','http://www.sitemaps.org/schemas/sitemap/0.9');ET.register_namespace('xhtml','http://www.w3.org/1999/xhtml')
ns='{http://www.sitemaps.org/schemas/sitemap/0.9}';xh='{http://www.w3.org/1999/xhtml}'
root=ET.Element(ns+'urlset')
for lang in paths:
 node=ET.SubElement(root,ns+'url');ET.SubElement(node,ns+'loc').text=BASE+paths[lang]
 for code in ['ru','en','kk','x-default']:ET.SubElement(node,xh+'link',{'rel':'alternate','hreflang':code,'href':BASE+paths.get(code,'')})
ET.ElementTree(root).write(OUT/'sitemap.xml',encoding='utf-8',xml_declaration=True)
# Keep the older auxiliary copies accurate too.
for name in ['robots.txt','sitemap.xml']:(ROOT/'deployment-extras'/name).write_bytes((OUT/name).read_bytes())
with zipfile.ZipFile(ROOT/'waymark-production.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted(OUT.rglob('*')):
  if f.is_file():z.write(f,f.relative_to(OUT))
print('Built static RU /, EN /en/, KK /kk/, shared CSS/JS, sitemap, robots and production ZIP.')
