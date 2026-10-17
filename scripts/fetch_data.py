#!/usr/bin/env python3
"""Builds data/tornadoes.json: tornado-only reports (IEM/NWS LSRs) + NWS DAT surveyed tracks, with a state assigned to each track."""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime

HOURS = 336  # 14 days
NOW = time.time()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'tornadoes.json')
LSR = 'https://mesonet.agron.iastate.edu/geojson/lsr.geojson?hours=%d' % HOURS
DAT = 'https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/1/query'
STATES = 'https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json'
ABBR = dict(x.split(':') for x in ('Alabama:AL,Alaska:AK,Arizona:AZ,Arkansas:AR,California:CA,Colorado:CO,Connecticut:CT,Delaware:DE,District of Columbia:DC,'
 'Florida:FL,Georgia:GA,Hawaii:HI,Idaho:ID,Illinois:IL,Indiana:IN,Iowa:IA,Kansas:KS,Kentucky:KY,Louisiana:LA,Maine:ME,Maryland:MD,Massachusetts:MA,'
 'Michigan:MI,Minnesota:MN,Mississippi:MS,Missouri:MO,Montana:MT,Nebraska:NE,Nevada:NV,New Hampshire:NH,New Jersey:NJ,New Mexico:NM,New York:NY,'
 'North Carolina:NC,North Dakota:ND,Ohio:OH,Oklahoma:OK,Oregon:OR,Pennsylvania:PA,Rhode Island:RI,South Carolina:SC,South Dakota:SD,Tennessee:TN,'
 'Texas:TX,Utah:UT,Vermont:VT,Virginia:VA,Washington:WA,West Virginia:WV,Wisconsin:WI,Wyoming:WY,Puerto Rico:PR').split(','))


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'tornadoes-pwa (github actions)'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def ef_of(s):
    m = re.search(r'EF\s*-?\s*([0-5])', str(s or ''), re.I)
    return int(m.group(1)) if m else None


def inring(x, y, ring):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def load_states():
    try:
        out = []
        for f in get(STATES)['features']:
            ab = ABBR.get(f['properties'].get('name'))
            g = f['geometry']
            polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
            if ab:
                out.append((ab, polys))
        return out
    except Exception as e:
        print('state outlines unavailable:', e)
        return []


def state_at(lat, lon, states):
    for ab, polys in states:
        for poly in polys:
            if inring(lon, lat, poly[0]) and not any(inring(lon, lat, h) for h in poly[1:]):
                return ab
    return None


def pos(v):
    return v if isinstance(v, (int, float)) and v > 0 else None


def tracks(states):
    feats, off = [], 0
    since = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(NOW - HOURS * 3600))
    while True:
        q = urllib.parse.urlencode({'where': "stormdate >= timestamp '%s'" % since, 'outFields': '*', 'outSR': 4326, 'f': 'json',
                                    'orderByFields': 'objectid', 'resultOffset': off, 'resultRecordCount': 1000})
        j = get(DAT + '?' + q)
        fs = j.get('features', [])
        feats += fs
        if not fs or (len(fs) < 1000 and not j.get('exceededTransferLimit')):
            break
        off += len(fs)
    out, seen = [], set()
    for f in feats:
        a = f['attributes']
        if not re.search('EF', a.get('efscale') or '', re.I):
            continue
        paths = [[[round(c[1], 4), round(c[0], 4)] for c in p] for p in (f.get('geometry') or {}).get('paths', []) if p]
        if not paths:
            continue
        tid = str(a.get('event_id') or a.get('objectid'))
        if tid in seen:
            tid += '-%s' % a.get('objectid')
        seen.add(tid)
        sll = [a['startlat'], a['startlon']] if a.get('startlat') and a.get('startlon') else paths[0][0]
        ell = [a['endlat'], a['endlon']] if a.get('endlat') and a.get('endlon') else paths[-1][-1]
        out.append(dict(id=tid, s=a.get('starttime') or a.get('stormdate'), e=a.get('endtime'), len=pos(a.get('length')),
                        width=pos(a.get('width')), inj=a.get('injuries') or 0, fat=a.get('fatalities') or 0, wind=pos(a.get('maxwind')),
                        wfo=a.get('wfo'), ef=ef_of(a.get('efscale')), raw=a.get('efscale'), note=(a.get('comments') or '')[:1000],
                        sll=sll, ell=ell, st=state_at(sll[0], sll[1], states) if states else None, paths=paths))
    return out


def reports():
    out = []
    for f in get(LSR).get('features', []):
        p = f['properties']
        t = p.get('typetext') or ''
        if not re.search('tornado', t, re.I) or re.search('funnel|waterspout', t, re.I):
            continue
        c = (f.get('geometry') or {}).get('coordinates') or [None, None]
        try:
            ts = int(datetime.fromisoformat(p['valid'].replace('Z', '+00:00')).timestamp() * 1000)
        except Exception:
            continue
        out.append(dict(t=ts, city=p.get('city'), county=p.get('county'), st=p.get('state'), ef=ef_of(p.get('remark')),
                        note=(p.get('remark') or '')[:1000], ll=[c[1], c[0]]))
    return out


if __name__ == '__main__':
    data = {'hours': HOURS, 'reports': reports(), 'tracks': tracks(load_states())}
    try:
        old = json.load(open(OUT))
        old.pop('generated', None)
    except Exception:
        old = None
    if old == data:
        print('no change')
    else:
        data['generated'] = datetime.utcnow().isoformat() + 'Z'
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(data, open(OUT, 'w'), separators=(',', ':'))
        print('wrote', len(data['reports']), 'reports,', len(data['tracks']), 'tracks')
