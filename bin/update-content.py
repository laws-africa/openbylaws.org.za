#!/usr/bin/env python
import json
import logging
import os
import sys
import bisect
from datetime import datetime, timedelta

import yaml
import requests

# setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)8s %(message)s')
log = logging.getLogger(__name__)

TIMEOUT = 30

# Indigo's API configuration
INDIGO_URL = 'https://api.laws.africa/v1'
INDIGO_AUTH_TOKEN = os.environ.get('INDIGO_API_AUTH_TOKEN')
if not INDIGO_AUTH_TOKEN:
    log.error("INDIGO_AUTH_TOKEN environment variable is not set.")
    sys.exit(1)

indigo = requests.Session()
indigo.headers['Authorization'] = 'Token ' + INDIGO_AUTH_TOKEN


def update_content(place_codes):
    with open("_data/places.json", "r") as f:
        places = json.load(f)

    for place in places:
        if not place_codes or place['code'] in place_codes:
            write_place(place)

    log.info("Done, bye")


def write_place(place):
    works = list_works(place)
    log.info(f"Got {len(works)} works for {place['code']}")

    # TODO: strip some info?
    with open(f"_data/works/{place['code']}.json", "w") as f:
        json.dump(works, f, indent=2, sort_keys=True)

    for work in works:
        write_work(place, work)

    if not place['special']:
        expressions = [
            exp
            for w in works
            for pit in w['points_in_time']
            for exp in pit['expressions']]
        languages = list(set(x['language'] for x in expressions))

        for lang in languages:
            dirname = os.path.join(place['code'], lang)
            os.makedirs(dirname, exist_ok=True)
            metadata = {
                'title': f"{place['name']} By-laws",
                'description': f"By-laws for {place['name']}, up-to-date and easy to read and share.",
                'layout': 'place',
                'place_code': place['code'],
                'language': lang,
            }

            with open(os.path.join(dirname, 'index.md'), "w") as f:
                f.write("---\n")
                yaml.dump(metadata, f)
                f.write("---\n")


def list_works(place):
    log.info(f"Loading {place['code']} works from Indigo at {INDIGO_URL}")
    works = []

    # walk through everything published on indigo
    url = f"/{place['code']}/.json"
    while url:
        resp = indigo.get(INDIGO_URL + url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        works.extend(data['results'])
        url = data['next']

    # only work with commenced works
    works = [w for w in works if w['commenced']]

    # slight tweaks to make templates easier
    for w in works:
        process_work(w)

    return works


def process_work(work):
    work['repealed'] = bool(work['repeal'])

    expressions = [exp for pit in work['points_in_time'] for exp in pit['expressions']]
    work['languages'] = [x['language'] for x in expressions]
    work['multiple_pits'] = len(set(x['expression_date'] for x in expressions)) > 1


def write_work(place, work):
    """ Write the various files for this work, including different expressions and languages.
    """
    log.info(f"Writing {work['frbr_uri']}")

    expressions = [exp for pit in work['points_in_time'] for exp in pit['expressions']]

    # point-in-time dates
    dates = sorted(list(set(x['date'] for x in work['amendments'])))

    # do the current one
    write_expression(place, work, False, dates)

    if work['multiple_pits']:
        log.info(f"Multiple points in time")
        # only write date-specific points in time if there are multiple
        # points in time
        write_expression(place, work, True, dates)

    for expr in expressions:
        # skip the current one, we've already done it
        if expr['expression_frbr_uri'] != work['expression_frbr_uri']:
            log.info(f"Fetching {expr['expression_frbr_uri']}")
            resp = indigo.get(expr['url'] + '.json', timeout=TIMEOUT)
            resp.raise_for_status()
            expr = resp.json()
            write_expression(place, expr, work['multiple_pits'], dates)


def write_expression(place, expr, use_date, dates):
    dirname = expr['frbr_uri'][1:] + '/' + expr['language']
    if use_date:
        dirname += '@' + expr['expression_date']

    os.makedirs(dirname, exist_ok=True)
    fname = os.path.join(dirname, "index.md")
    log.info(f"Writing {dirname}")

    metadata = {
        "layout": "work",
        "title": expr['title'],
        "frbr_uri": expr['frbr_uri'],
        "language": expr['language'],
        "expression_date": expr['expression_date'],
        "place_code": place['code'],
        "toc": work_toc(expr),
        "history": work_history(expr),
        "latest_expression": not dates or expr['expression_date'] == dates[-1],
    }

    if dates:
        # find the next date after in_force_from
        ix = bisect.bisect_right(dates, expr['expression_date'])
        if ix < len(dates):
            # subtract one day
            date = datetime.strptime(dates[ix], '%Y-%m-%d').date() - timedelta(days=1)
            metadata['in_force_to'] = date.strftime('%Y-%m-%d')

    resp = indigo.get(expr['url'] + '.html', timeout=TIMEOUT)
    resp.raise_for_status()
    # wrap in DIV tags so that markdown doesn't get confused
    html = "<div>" + resp.text + "</div>"

    write_images(place, expr, dirname)
    write_archive_formats(place, expr, dirname)

    with open(fname, "w") as f:
        f.write("---\n")
        yaml.dump(metadata, f)
        f.write("---\n\n")
        f.write(html)


def write_images(place, expr, dirname):
    images = []

    url = expr['url'] + '/media.json'
    while url:
        resp = indigo.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        images.extend(x for x in data['results'] if x['mime_type'].startswith('image/'))
        url = data['next']

    if images:
        log.info(f"Got {len(images)} images for {expr['expression_frbr_uri']}")
        dirname = os.path.join(dirname, 'media')
        os.makedirs(dirname, exist_ok=True)

    for img in images:
        log.info(f"Fetching and saving image {img['filename']}")
        resp = indigo.get(img['url'])
        # this is a binary string
        data = resp.content
        with open(os.path.join(dirname, img['filename']), "wb") as f:
            f.write(data)


def write_archive_formats(place, expr, dirname):
    dirname = os.path.join(dirname, 'resources')
    os.makedirs(dirname, exist_ok=True)

    for fmt in ['pdf', 'epub']:
        log.info(f"Fetching {fmt}")
        resp = indigo.get(expr['url'] + "." + fmt)

        # this is a binary string
        data = resp.content
        with open(os.path.join(dirname, expr['language'] + '.' + fmt), "wb") as f:
            f.write(data)


def work_toc(work):
    if 'toc' not in work:
        toc = []
        if not work['stub']:
            log.info(f"Fetching TOC")
            resp = indigo.get(work['url'] + '/toc.json', timeout=TIMEOUT)
            resp.raise_for_status()
            toc = resp.json()['toc']

        work['toc'] = toc

    return work['toc']


def work_history(work):
    # TODO
    return []


if __name__ == '__main__':
    if len(sys.argv) > 1:
        place_codes = sys.argv[1:]
    else:
        place_codes = []

    update_content(place_codes)
