#!/usr/bin/env python3
"""Audit the HTTP and server-rendered SEO contract without third-party packages."""
import argparse
import concurrent.futures
import datetime
from html.parser import HTMLParser
import json
import http.client
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta = {}; self.canonicals = []; self.links = []; self.ids = set()
        self.title = ''; self.h1 = []; self.json_ld = []; self.errors = []; self.visible = []
        self.current_h1 = None; self.in_title = False; self.script = None; self.hidden_depth = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'): self.ids.add(attrs['id'])
        if tag == 'html': self.lang = attrs.get('lang')
        if tag == 'title': self.in_title = True
        if tag == 'meta': self.meta[attrs.get('name', attrs.get('property', ''))] = attrs.get('content', '')
        if tag == 'link' and attrs.get('rel') == 'canonical': self.canonicals.append(attrs.get('href'))
        if tag == 'a' and attrs.get('href'): self.links.append(attrs['href'])
        if tag == 'h1': self.current_h1 = ''
        if tag in ('script', 'style'): self.hidden_depth += 1
        if tag == 'script' and attrs.get('type') == 'application/ld+json': self.script = ''
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'h1' and self.current_h1 is not None:
            self.h1.append(self.current_h1.strip()); self.current_h1 = None
        if tag == 'script' and self.script is not None:
            try: self.json_ld.append(json.loads(self.script))
            except ValueError as error: self.errors.append(f'Invalid JSON-LD: {error}')
            self.script = None
        if tag in ('script', 'style'): self.hidden_depth = max(0, self.hidden_depth - 1)
    def handle_data(self, text):
        if self.in_title: self.title += text
        if self.current_h1 is not None: self.current_h1 += text
        if self.script is not None: self.script += text
        if not self.hidden_depth: self.visible.append(text)

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers.items()), response.read(), response.url
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read(), error.url
    except (OSError, http.client.HTTPException) as error:
        return 0, {}, str(error).encode(), url

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('base'); parser.add_argument('--canonical-origin', required=True)
    parser.add_argument('--out', required=True); parser.add_argument('--allow-deployment-noindex', action='store_true'); args = parser.parse_args()
    base = args.base.rstrip('/'); origin = args.canonical_origin.rstrip('/'); problems = []
    status, _, sitemap_body, _ = fetch(base + '/sitemap.xml')
    if status != 200: raise RuntimeError(f'Sitemap HTTP {status}')
    sitemap = ET.fromstring(sitemap_body); locs = [item.text for item in sitemap.findall('.//{*}loc')]
    if not locs or len(locs) != len(set(locs)): problems.append('Empty or duplicate sitemap URLs')
    if any(not url.startswith(origin + '/') for url in locs): problems.append('Sitemap references the wrong origin')
    paths = [urllib.parse.urlparse(url).path or '/' for url in locs]
    _, _, robots_body, _ = fetch(base + '/robots.txt'); robots = robots_body.decode()
    if f'Sitemap: {origin}/sitemap.xml' not in robots: problems.append('robots.txt sitemap URL mismatch')
    if re.search(r'^Disallow:\s*/\s*$', robots, re.M): problems.append('robots.txt blocks the entire site')
    rows = []; documents = {}
    def audit(path):
        status, headers, body, final_url = fetch(base + path); headers = {key.lower(): value for key, value in headers.items()}
        page = Page(); page.feed(body.decode('utf-8')); errors = page.errors[:]
        expected = origin + path
        if status != 200: errors.append(f'HTTP {status}')
        if len(page.canonicals) != 1 or page.canonicals[0].rstrip('/') != expected.rstrip('/'): errors.append('Canonical mismatch')
        if not page.title.strip(): errors.append('Missing title')
        if not page.meta.get('description'): errors.append('Missing description')
        if len(page.h1) != 1: errors.append(f'Expected one H1, got {len(page.h1)}')
        if not getattr(page, 'lang', None): errors.append('Missing HTML language')
        for key in ('robots', 'googlebot'):
            if 'noindex' in page.meta.get(key, '').lower() and not args.allow_deployment_noindex:
                errors.append(f'{key} blocks indexing')
        if 'noindex' in headers.get('x-robots-tag', '').lower() and not args.allow_deployment_noindex: errors.append('HTTP X-Robots-Tag blocks indexing')
        if page.meta.get('og:url', '').rstrip('/') != expected.rstrip('/'): errors.append('Open Graph URL mismatch')
        for key in ('og:title','og:description','twitter:title','twitter:description','og:image','twitter:image'):
            if not page.meta.get(key): errors.append(f'Missing {key}')
        for key in ('og:image', 'twitter:image'):
            if not page.meta.get(key, '').startswith(origin + '/'): errors.append(f'{key} origin mismatch')
        visible = ' '.join(' '.join(page.visible).split())
        for data in page.json_ld:
            if data.get('@type') == 'FAQPage':
                for question in data.get('mainEntity', []):
                    if ' '.join(question['name'].split()) not in visible: errors.append('FAQ question not present in server HTML')
                    if ' '.join(question['acceptedAnswer']['text'].split()) not in visible: errors.append('FAQ answer not present in server HTML')
        return path, page, {'path':path, 'status':status, 'title':page.title.strip(), 'description':page.meta.get('description'), 'canonical':page.canonicals, 'h1':page.h1, 'schema_types':[data.get('@type') for data in page.json_ld], 'errors':errors}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for path, page, row in pool.map(audit, paths): documents[path] = page; rows.append(row)
    for key in ('title','description'):
        seen = {}
        for row in rows:
            value = row[key]
            if value in seen: problems.append(f'Duplicate {key}: {seen[value]} and {row["path"]}')
            seen[value] = row['path']
    internal_targets = set(); incoming = set()
    for path, page in documents.items():
        for href in page.links:
            url = urllib.parse.urlparse(urllib.parse.urljoin(origin + path, href))
            if url.netloc != urllib.parse.urlparse(origin).netloc: continue
            target = url.path or '/'; internal_targets.add(target)
            if target != path: incoming.add(target)
            if url.fragment and target in documents and url.fragment not in documents[target].ids:
                problems.append(f'Broken fragment on {path}: {href}')
    for path in paths:
        if path != '/' and path not in incoming: problems.append(f'No internal incoming link: {path}')
    extra_checks = []
    for path in sorted(internal_targets - set(paths)):
        if path.startswith(('/app','/admin','/auth')): continue
        status, _, _, _ = fetch(base + path)
        extra_checks.append({'path':path,'status':status})
        if status >= 400: problems.append(f'Internal link HTTP {status}: {path}')
    for path in ['/login','/preview','/preview/journey']:
        status, headers, body, _ = fetch(base + path); headers = {key.lower():value for key,value in headers.items()}
        page = Page(); page.feed(body.decode('utf-8'))
        if 'noindex' not in headers.get('x-robots-tag','') and 'noindex' not in page.meta.get('robots',''): problems.append(f'Private/demo route lacks noindex: {path}')
    status, _, verification, _ = fetch(base + '/google9773389826078f2e.html')
    if status != 200 or verification.decode().strip() != 'google-site-verification: google9773389826078f2e.html': problems.append('Google verification file missing or invalid')
    for path in ['/seo-check-missing-page-404','/guides/seo-check-missing-guide-404']:
        status, _, _, _ = fetch(base + path)
        if status != 404: problems.append(f'Missing page must return 404: {path} -> {status}')
    for path in ['/opengraph-image','/icon.svg']:
        status, headers, body, _ = fetch(base + path)
        if status != 200 or not body: problems.append(f'Share asset is unavailable: {path}')
    problems.extend(f'{row["path"]}: {error}' for row in rows for error in row['errors'])
    result = {'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':base,'canonical_origin':origin,'page_count':len(rows),'pages':rows,'extra_internal_links':extra_checks,'errors':problems,'passed':not problems}
    Path(args.out).parent.mkdir(parents=True,exist_ok=True); Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'pages':len(rows),'passed':not problems,'errors':problems,'report':args.out},ensure_ascii=False,indent=2))
    return 0 if not problems else 1
if __name__ == '__main__': sys.exit(main())
