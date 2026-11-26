import os, json, urllib.request, datetime as dt, collections, re
from pathlib import Path
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1]
token=os.environ['PROFILE_TOKEN']
def api(url, payload=None):
    req=urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None, headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'bytelea-dashboard'})
    with urllib.request.urlopen(req,timeout=45) as response: return json.load(response)
def gql(query, variables):
    result=api('https://api.github.com/graphql',{'query':query,'variables':variables})
    if result.get('errors'): raise RuntimeError('GitHub GraphQL request failed')
    return result['data']['user']
today=dt.datetime.now(dt.timezone.utc).date()
day=dt.timedelta(days=1)
user=gql('query($login:String!){user(login:$login){createdAt pullRequests{totalCount}}}',{'login':'bytelea'})
start=dt.date.fromisoformat(user['createdAt'][:10])
counts={}
cursor=start
while cursor<=today:
    end=min(cursor+dt.timedelta(days=364),today)
    u=gql('query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}',{'login':'bytelea','from':str(cursor)+'T00:00:00Z','to':str(end)+'T23:59:59Z'})
    for week in u['contributionsCollection']['contributionCalendar']['weeks']:
        for d in week['contributionDays']:
            date=dt.date.fromisoformat(d['date'])
            if cursor<=date<=end: counts[date]=d['contributionCount']
    cursor=end+day
repos=[]
page=1
while True:
    batch=api('https://api.github.com/users/bytelea/repos?type=owner&per_page=100&page='+str(page))
    repos.extend(r for r in batch if not r['private'])
    if len(batch)<100: break
    page+=1
langs=collections.Counter()
for r in repos:
    if not r['fork']: langs.update(api(r['languages_url']))
longest=run=0
for d in sorted(counts):
    run=run+1 if counts[d] else 0
    longest=max(longest,run)
d=today if counts.get(today,0) else today-day
current=0
while counts.get(d,0): current+=1; d-=day
year=sum(v for d,v in counts.items() if d>=today-dt.timedelta(days=364))
brown='#302823'; cream='#FAF5EB'; pink='#D9A5AE'; green='#CFD5B9'
def text(x,y,s,size=20,weight=400,anchor='start',mono=False):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" font-family="{"monospace" if mono else "Arial Rounded MT Bold, Trebuchet MS, sans-serif"}" fill="{brown}">{escape(str(s))}</text>'
def rect(x,y,w,h,fill,rx=12,stroke='none'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>'
def panel(h):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 {h}"><defs><pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="10" cy="10" r="1.5" fill="#D9CFC0"/></pattern></defs>'+rect(4,4,632,h-8,cream,26,brown)+rect(8,8,624,h-16,'url(#dots)',22)+rect(35,31,570,h-60,brown,22)+rect(30,25,570,h-60,'#fffdf8',22,brown)
out={}
p=ROOT/'assets/statistics/activity.svg'
s=p.read_text()
# Match stable text coordinates, preserving the approved artwork.
for x,y,v in [(55,170,f'{year:,}'),(55,295,f'{current} days'),(347,295,f'{longest} days'),(55,423,f'{sum(counts.values()):,}'),(347,423,len(repos)),(55,551,sum(r['stargazers_count'] for r in repos)),(347,551,user['pullRequests']['totalCount'])]:
    s=re.sub(r'(<text x="'+str(x)+r'" y="'+str(y)+r'"[^>]*>)[^<]*(</text>)',lambda m:m[1]+str(v)+m[2],s)
s=s.replace('activity snapshot','updated nightly').replace('commits in the last year','contributions in 365 days').replace('— awaiting contribution calendar sync','Available GitHub calendar history').replace('font-size="76"','font-size="58"').replace('font-size="43"','font-size="35"')
out[p]=s
first=today-dt.timedelta(days=181)
weekstart=first-dt.timedelta(days=(first.weekday()+1)%7)
weeks=(today-weekstart).days//7+1
h=165+weeks*43
s=panel(h)+text(54,75,f'{sum(v for d,v in counts.items() if first<=d<=today):,}',42,800)+text(54,105,'contributions in the last 182 days',19,mono=True)
for i,l in enumerate('SMTWTFS'): s+=text(165+i*59,140,l,19,anchor='middle',mono=True)
lastmonth=None
for w in range(weeks):
    for i in range(7):
        d=weekstart+dt.timedelta(days=w*7+i)
        if not first<=d<=today: continue
        if d.month!=lastmonth:
            s+=text(54,170+w*43,d.strftime('%b'),17,mono=True);lastmonth=d.month
        v=counts.get(d,0); color='#eae6e1' if not v else '#e0ead9' if v<5 else '#b8cba8' if v<15 else '#91ae84' if v<30 else '#71976a'
        s+=rect(139+i*59,148+w*43,52,36,color,9)+text(165+i*59,173+w*43,v,19,anchor='middle',mono=True)
out[ROOT/'assets/charts/calendar.svg']=s+'</svg>'
days=[today-dt.timedelta(days=i) for i in reversed(range(30))]
values=[counts.get(d,0) for d in days]; top=max(1,max(values))
s=panel(410)+text(54,75,f'{sum(values):,}',42,800)+text(54,105,'contributions in the last 30 days',19,mono=True)
for i in range(5):
    y=320-i*45;s+=f'<path d="M95 {y}H570" stroke="#D9CFC0" stroke-dasharray="5 5"/>'+text(85,y+5,round(top*i/4,1),14,anchor='end',mono=True)
pts=[(95+i*475/29,320-v/top*180) for i,v in enumerate(values)]
coords=' '.join(f'{x:.2f},{y:.2f}' for x,y in pts)
s+=f'<polygon points="95,320 {coords} 570,320" fill="#F2D5DC"/><polyline points="{coords}" fill="none" stroke="{pink}" stroke-width="4" stroke-linejoin="round"/>'
for i,(x,y) in enumerate(pts):
    s+=f'<circle cx="{x}" cy="{y}" r="3.8" fill="{pink}" stroke="{brown}" stroke-width="1.5"/>'
    if i%6==0 or i==29:s+=text(x,347,days[i].strftime('%d %b'),13,anchor='middle',mono=True)
out[ROOT/'assets/charts/recent.svg']=s+'</svg>'
months=collections.Counter()
for d,v in counts.items(): months[d.strftime('%Y-%m')]+=v
items=sorted(months.items())[-6:];top=max(1,max((v for _,v in items),default=0))
s=panel(370)+text(54,75,'Monthly activity',34,800)+text(54,105,'Calendar months • current month to date',15,mono=True)
for i,(m,v) in enumerate(items):
    x=65+i*85;h=v/top*165;s+=rect(x,290-h,58,h,['#D7E1E5','#F2D5DC','#CFD5B9','#EBD3A5','#D8CDE5','#D9A5AE'][i],7,brown)+text(x+29,280-h,v,17,anchor='middle',mono=True)+text(x+29,315,dt.date.fromisoformat(m+'-01').strftime('%b'),17,anchor='middle',mono=True)
out[ROOT/'assets/charts/monthly.svg']=s+'</svg>'
items=langs.most_common(6); total=sum(langs.values()); other=total-sum(v for _,v in items)
if other:items.append(('Other',other))
h=185+44*len(items)
s=panel(h)+text(54,75,'Languages I use',35,800)+text(54,105,'Public non-fork repositories • code bytes',16,mono=True)
for i,(l,v) in enumerate(items):
    pct=100*v/total;y=132+i*44;s+=text(54,y+21,l,19,700)+rect(218,y,pct/ max(100*items[0][1]/total,1)*275,25,['#D9A5AE','#D7E1E5','#EBD3A5','#D8CDE5','#CFD5B9','#F2D5DC','#eae6e1'][i],7,brown)+text(574,y+20,f'{pct:.2f}%',19,anchor='end',mono=True)
s+=text(54,h-60,'Repository language share, not skill level.',15,mono=True)
out[ROOT/'assets/charts/languages.svg']=s+'</svg>'
# All API requests complete before any assets are replaced.
import xml.etree.ElementTree as ET
for s in out.values(): ET.fromstring(s)
for p,s in out.items(): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
readme=ROOT/'README.md'
s=readme.read_text()
s=re.sub(r'alt="GitHub activity snapshot:[^"]*"', 'alt="GitHub contribution totals, streaks, public repositories, stars and pull requests"',s)
s=re.sub(r'alt="Previous language widget snapshot:[^"]*"', 'alt="Programming language distribution by code bytes"',s)
marker='<img src="assets/charts/calendar.svg"'
if marker not in s:
    block='\n\n'+ '\n\n'.join(f'<img src="assets/charts/{name}.svg" width="100%" alt="{alt}">' for name,alt in [('calendar','Daily contribution calendar'),('recent','Last 30 days of contributions'),('monthly','Monthly contribution totals')])+'\n\n'
    s=s.replace('<img src="assets/charts/languages.svg"',block+'<img src="assets/charts/languages.svg"')
readme.write_text(s)
