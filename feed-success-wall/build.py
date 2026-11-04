#!/usr/bin/env python3
"""Build /tmp/feed-success-wall/index.html from /tmp/collage.json."""
import json, datetime

rows = json.load(open('/tmp/collage.json'))

WAIT_TIER = {
    'Less than one hour': 0,
    '1-2 hours': 1,
    '2-3 hours': 2,
}

items = []
for r in rows:
    pf = json.loads(r['processed_file_path'])
    is_video = 'mp4' in pf
    ts = int(datetime.datetime.strptime(r['created_at'], '%Y-%m-%d %H:%M:%S.%f')
             .replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    poster = None
    if is_video:
        poster = 'https://media.polls.pizza/' + pf['poster']
    item = {
        'id': r['id'],
        'ts': ts,
        'city': r['city'],
        'state': r['state'],
        'addr': r['full_address'],
        'locId': r['location_id'],
        'orderId': r['order_id'],
        'wait': r['wait_time'],
        'waitTier': WAIT_TIER.get(r['wait_time'], 1),
        'rest': r['restaurant'].strip(),
        'qty': r['quantity'],
        'snacks': r['snacks'],
        'cost': round(r['cost'], 2),
        'video': is_video,
        'img': (pf.get('webp') or pf.get('jpeg') or (poster if is_video else None)),
        'mp4': pf.get('mp4'),
        'poster': poster,
    }
    if not item['img']:
        raise SystemExit(f"no image for {r['id']}")
    items.append(item)

items.sort(key=lambda x: x['ts'])

TPL = open('/tmp/feed-success-wall/template.html').read()
html = TPL.replace('__DATA__', json.dumps(items, separators=(',', ':')))
open('/tmp/feed-success-wall/index.html', 'w').write(html)
print('items:', len(items))
print('first:', items[0]['ts'], 'last:', items[-1]['ts'])