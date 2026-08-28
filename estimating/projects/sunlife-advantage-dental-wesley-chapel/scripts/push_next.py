#!/usr/bin/env python3
"""Push next geometry batch to JobTread via printing MCP query for CallMcpTool.
Usage: python3 push_next.py fixtures|hvac|ca|v|cw|vac|w|part|light
"""
import json, copy, sys

NORM = json.load(open('/tmp/sunlife_params_norm.json'))
BASE = json.load(open('/tmp/jt_current_base.json'))

# Track which indices already have geometry in BASE (finish batch)
DONE = {14,15,16,20,21,28}

MAP = {
  'fixtures': [7],
  'jbox': [8],
  'hvac': [6],
  'ca': [2],
  'v': [9],
  'cw': [1],
  'vac': [3],
  'w': [0],
  'part': [4],
  'light': [5],
  'reg': [34,35],
}

def shorten(p):
    p = copy.deepcopy(p)
    for m in p.get('measurements') or []:
        if isinstance(m.get('name'), str) and len(m['name']) > 40:
            m['name'] = m['name'][:37] + '...'
        for a in m.get('annotations') or []:
            if a.get('type') == 'point':
                a.pop('strokeWidth', None)
                if 'fillColor' in a:
                    a.pop('strokeColor', None)
    return p

def main(key):
    global BASE
    # Reload base if updated
    try:
        BASE = json.load(open('/tmp/jt_current_base.json'))
    except Exception:
        pass
    b = copy.deepcopy(BASE)
    for i in MAP[key]:
        b[i] = shorten(NORM[i])
    payload = {'updateJob': {'$': {'id': '22PaqftN7Gtd', 'parameters': b}}}
    out = f'/tmp/jt_push_{key}.json'
    json.dump(payload, open(out, 'w'), separators=(',', ':'))
    # Update base file for next
    json.dump(b, open('/tmp/jt_current_base.json', 'w'))
    print(out, len(json.dumps(payload, separators=(',', ':'))))

if __name__ == '__main__':
    main(sys.argv[1])
