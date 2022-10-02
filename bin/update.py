#!/usr/bin/env python
import json
import logging
import os
import sys
import bisect
from datetime import datetime, timedelta
from itertools import groupby, chain
import argparse
import copy
import concurrent.futures

import yaml
import requests

# setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(thread)d %(levelname)8s %(message)s')
log = logging.getLogger(__name__)

TIMEOUT = 30
LANGUAGES = {
    'afr': 'Afrikaans',
    'eng': 'English',
}
# two-letter language codes
LANGUAGES_2 = {
    'afr': 'af',
    'eng': 'en',
}

# Indigo's API configuration
INDIGO_URL = 'https://api.laws.africa/v2'
INDIGO_AUTH_TOKEN = os.environ.get('INDIGO_API_AUTH_TOKEN')
if not INDIGO_AUTH_TOKEN:
    log.error("INDIGO_API_AUTH_TOKEN environment variable is not set.")
    sys.exit(1)


class Updater:
    indigo = requests.Session()
    indigo.headers['Authorization'] = 'Token ' + INDIGO_AUTH_TOKEN

    def remove_akn(self, work):
        # remove /akn/
        work['frbr_uri'] = work['frbr_uri'][4:]
        work['expression_frbr_uri'] = work['expression_frbr_uri'][4:]

        if work['repeal']:
            work['repeal']['repealing_uri'] = work['repeal']['repealing_uri'][4:]

        if work['amendments']:
            for info in work['amendments']:
                info['amending_uri'] = info['amending_uri'][4:]

    def update_content(self, place_codes):
        """ Write the place index and work detail pages for all places.
        """
        with open("_data/places.json", "r") as f:
            places = json.load(f)

        for place in places:
            # if we're doing all places, ignore microsites
            if (not place_codes and not place.get('microsite')) or place['code'] in place_codes:
                self.write_place(place)

        with open("_data/places.json", "w") as f:
            json.dump(places, f, indent=2, sort_keys=True)

        log.info("Done, bye")

    def write_place(self, place):
        """ Write the place and work details for this place.
        """
        works = self.list_works(place)
        log.info(f"Got {len(works)} works for {place['code']}")

        with open(f"_data/works/{place['code']}.json", "w") as f:
            json.dump(works, f, indent=2, sort_keys=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.write_work, place, work) for work in works]
            concurrent.futures.wait(futures)

        if place.get('special'):
            return

        self.write_place_index(place, works)

    def write_place_index(self, place, works):
        """ Write the index pages for a place, for each language for which
        it has expressions, eg:

        eng/index.md
        afr/index.md
        """
        # languages for this place
        languages = list(set(chain(*(w['languages'] for w in works))))

        # write listing pages for each language in this place
        for lang in languages:
            # the works applicable to this listing page.
            # use the appropriate language if we have one, otherwise fall back to eng
            expressions = []
            for work in (w for w in works if not w['stub']):
                # find the latest expression with this language
                for expr in (e for p in work['points_in_time'] for e in p['expressions']):
                    if expr['language'] == lang and expr['expression_date'] == work['expression_date']:
                        # copy work, and then replace title with this expression info
                        copied = copy.deepcopy(work)
                        copied.update(expr)
                        expressions.append(copied)
                        break
                else:
                    # use english
                    expressions.append(copy.deepcopy(work))

            # remove some attribs, to make it easier to debug
            for expr in expressions:
                if 'toc' in expr:
                    del expr['toc']

            metadata = {
                'title': f"{place['name']} By-laws",
                'description': f"By-laws for {place['name']}, up-to-date and easy to read and share.",
                'layout': 'place',
                'place_code': place['code'],
                'language': lang,
                'languages': self.language_list(languages),
                'alternates': self.place_alternates(place['code'], languages),
                'expressions': expressions,
            }

            dirname = os.path.join(os.getcwd(), self.place_index_prefix(place['code'], lang))
            os.makedirs(dirname, exist_ok=True)
            fname = os.path.join(dirname, 'index.md')
            log.info(f"Writing {fname}")
            with open(fname, "w") as f:
                f.write("---\n")
                yaml.dump(metadata, f)
                f.write("---\n")

    def language_list(self, codes):
        return sorted([{
            'code': lang,
            'name': LANGUAGES[lang],
        } for lang in codes], key=lambda x: x['name'])

    def work_alternates(self, work, date, languages):
        """ URLs for alternate languages for a work.
        """
        if len(languages) == 1:
            return []

        url = work['frbr_uri'] + '/{0}'
        if date:
            url = url + '@' + date

        return [{
            'lang': LANGUAGES_2[lang],
            'url': url.format(lang),
        } for lang in languages]

    def place_alternates(self, code, languages):
        """ URLs for alternate a place.
        """
        if len(languages) == 1:
            return []

        return [{
            'lang': LANGUAGES_2[lang],
            'url': f'/{code}/{lang}/',
        } for lang in languages]

    def place_index_prefix(self, code, lang):
        return os.path.join(code, lang)

    def list_works(self, place):
        log.info(f"Loading {place['code']} works from Indigo at {INDIGO_URL}")
        works = []

        # walk through everything published on indigo
        url = f"/akn/{place['code']}/.json"
        params = place.get('params', {})
        while url:
            resp = self.indigo.get(INDIGO_URL + url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            works.extend(data['results'])
            url = data['next']

        # only work with commenced works
        works = [w for w in works if w['commenced']]

        # slight tweaks to make templates easier
        for w in works:
            self.process_work(w)

        return works

    def process_work(self, work):
        # strip some info
        KEEP = """
            amendments
            as_at_date
            assent_date
            commencement_date
            expression_date
            expression_frbr_uri
            frbr_uri
            language
            numbered_title
            parent_work
            points_in_time
            publication_date
            publication_document
            publication_name
            publication_number
            repeal
            repealed
            stub
            title
            type_name
            url
        """.split()

        for key in list(work.keys()):
            if key not in KEEP:
                del work[key]

        work['repealed'] = bool(work['repeal'])
        self.remove_akn(work)

        expressions = [exp for pit in work['points_in_time'] for exp in pit['expressions']]
        work['languages'] = list(set([x['language'] for x in expressions]))
        work['multiple_pits'] = len(set(x['expression_date'] for x in expressions)) > 1
        work['full_publication'] = f"{work['publication_name']} no. {work['publication_number']}"
        work['has_parent'] = bool(work['parent_work'])

    def write_work(self, place, work):
        """ Write the various files for this work, including different expressions and languages.

        frbr-uri/eng/index.md
        frbr-uri/afr/index.md

        Additionally, if there are multiple points in time, also write date-specific files:

        frbr-uri/eng@date/index.md
        frbr-uri/afr@date/index.md
        """
        log.info(f"Writing {work['frbr_uri']}")

        if work['stub']:
            self.write_expression(place, work, work, False, [])
        else:
            # all languages and points in time
            expressions = [exp for pit in work['points_in_time'] for exp in pit['expressions']]

            # point-in-time dates
            dates = sorted(list(set(x['date'] for x in work['amendments'])))

            for expr in expressions:
                # only fetch details if it's not the primary work expression
                if expr['expression_frbr_uri'] != work['expression_frbr_uri']:
                    log.info(f"- Fetching {expr['expression_frbr_uri']}")
                    resp = self.indigo.get(expr['url'] + '.json', timeout=TIMEOUT)
                    resp.raise_for_status()
                    expr = resp.json()
                    self.remove_akn(expr)
                else:
                    expr = work

                # detail page for latest expression date
                if expr['expression_date'] == work['expression_date']:
                    self.write_expression(place, work, expr, False, dates)

                # detail pages at historical points in time
                if work['multiple_pits']:
                    self.write_expression(place, work, expr, True, dates)

    def write_expression(self, place, work, expr, use_date, dates):
        """ Write the detail page for an expression.
        If use_date is true, include the date in the filename.
        """
        dirname = expr['frbr_uri'][1:] + '/' + expr['language']
        if use_date:
            dirname += '@' + expr['expression_date']

        os.makedirs(dirname, exist_ok=True)
        fname = os.path.join(dirname, "index.md")
        log.info(f"- Writing {dirname}")

        metadata = {
            "layout": "work",
            "title": expr['title'],
            "frbr_uri": expr['frbr_uri'],
            "language": expr['language'],
            "language2": LANGUAGES_2[expr['language']],
            "languages": self.language_list(work['languages']),
            "alternates": self.work_alternates(expr, expr['expression_date'] if use_date else None, work['languages']),
            "expression_date": expr['expression_date'],
            "place_code": place['code'],
            "toc": self.work_toc(expr),
            "history": self.work_history(work, expr['language']),
            "latest_expression": not dates or expr['expression_date'] == dates[-1],
        }

        if dates:
            # find the next date after in_force_from
            ix = bisect.bisect_right(dates, expr['expression_date'])
            if ix < len(dates):
                # subtract one day
                date = datetime.strptime(dates[ix], '%Y-%m-%d').date() - timedelta(days=1)
                metadata['in_force_to'] = date.strftime('%Y-%m-%d')

        resp = self.indigo.get(expr['url'] + '.html', timeout=TIMEOUT)
        resp.raise_for_status()
        # wrap in DIV tags so that markdown doesn't get confused
        html = "<div>" + resp.text + "</div>"
        # rewrite /akn references
        html = html.replace('href="/akn/', 'href="/')

        with open(fname, "w") as f:
            f.write("---\n")
            yaml.dump(metadata, f)
            f.write("---\n\n")
            f.write(html)

        if not expr['stub']:
            if not self.skip_images:
                self.write_images(place, expr, dirname)

            if not self.skip_archive:
                self.write_archive_formats(place, expr, dirname)

    def write_images(self, place, expr, dirname):
        images = []

        url = expr['url'] + '/media.json'
        while url:
            resp = self.indigo.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            images.extend(x for x in data['results'] if x['mime_type'].startswith('image/'))
            url = data['next']

        if images:
            log.info(f"- Got {len(images)} images for {expr['expression_frbr_uri']}")
            dirname = os.path.join(dirname, 'media')
            os.makedirs(dirname, exist_ok=True)

        for img in images:
            log.info(f"- Fetching and saving image {img['filename']}")
            resp = self.indigo.get(img['url'], timeout=TIMEOUT)
            # this is a binary string
            data = resp.content
            with open(os.path.join(dirname, img['filename']), "wb") as f:
                f.write(data)

    def write_archive_formats(self, place, expr, dirname):
        dirname = os.path.join(dirname, 'resources')
        os.makedirs(dirname, exist_ok=True)

        for fmt, params in [('pdf', {}), ('epub', {}), ('html', {'standalone': '1'})]:
            url = expr['url'] + "." + fmt
            log.info(f"- Fetching {url}")
            resp = self.indigo.get(url, params=params, timeout=TIMEOUT)

            # this is a binary string
            data = resp.content
            with open(os.path.join(dirname, expr['language'] + '.' + fmt), "wb") as f:
                f.write(data)

    def work_toc(self, work):
        if 'toc' not in work:
            toc = []
            if not work['stub']:
                log.info(f"- Fetching TOC")
                resp = self.indigo.get(work['url'] + '/toc.json', timeout=TIMEOUT)
                resp.raise_for_status()
                toc = resp.json()['toc']

            work['toc'] = toc

        return work['toc']

    def work_history(self, work, language):
        events = []

        expressions = {}
        for pit in work['points_in_time']:
            # fallback
            expressions[pit['date']] = pit['expressions'][0]

            # now see if we have a better language
            for expr in pit['expressions']:
                if expr['language'] == language:
                    expressions[pit['date']] = expr
                    break

        if work['assent_date']:
            events.append({
                'date': work['assent_date'],
                'event': 'assent',
            })

        if work['publication_date']:
            events.append({
                'date': work['publication_date'],
                'event': 'publication',
            })

        if work['commencement_date']:
            events.append({
                'date': work['commencement_date'],
                'event': 'commencement',
            })

        events.extend([{
            'date': a['date'],
            'event': 'amendment',
            'amending_title': a['amending_title'],
            'amending_uri': a['amending_uri'],
        } for a in work['amendments']])

        if work['repeal']:
            events.append({
                'date': work['repeal']['date'],
                'event': 'repeal',
                'repealing_title': work['repeal']['repealing_title'],
                'repealing_uri': work['repeal']['repealing_uri'],
            })

        # group by date then unpack
        events.sort(key=lambda e: e['date'])
        events = [{
            'date': date,
            'events': list(group),
        } for date, group in groupby(events, lambda e: e['date'])]

        # link in expressions, remove unneccessary date
        for event in events:
            for e in event['events']:
                del e['date']
            uri = expressions.get(event['date'], {}).get('expression_frbr_uri')
            if uri:
                event['expression_frbr_uri'] = uri[4:]

        # sort groups
        events.sort(key=lambda e: e['date'], reverse=True)

        return events


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true', default=False)
    parser.add_argument('place', nargs='*', help='Place code to load (defaults to all)')
    args = parser.parse_args()

    updater = Updater()
    updater.skip_archive = args.quick
    updater.skip_images = args.quick
    updater.update_content(args.place)
