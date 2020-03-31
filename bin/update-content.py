#!/usr/bin/env python
import json
import logging
import os
import sys

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


def update_content():
    with open("_data/places.json", "r") as f:
        places = json.load(f)

    for place in places:
        write_place(place)

    log.info("Done, bye")


def write_place(place):
    works = list_works(place)
    for work in works:
        write_work(place, work)

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

    # TODO: strip some info?
    with open(f"_data/works/{place['code']}.json", "w") as f:
        json.dump(works, f, indent=2, sort_keys=True)


def list_works(place):
    log.info(f"Loading works from Indigo at {INDIGO_URL}")
    works = []

    # walk through everything published on indigo
    url = f"/{place['code']}/.json"
    while url:
        resp = indigo.get(INDIGO_URL + url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        works.extend(data['results'])
        url = data['next']

    return works


def write_work(place, work):
    """ Write the various files for this work, including different expressions and languages.
    """
    expressions = [exp for pit in work['points_in_time'] for exp in pit['expressions']]
    languages = [x['language'] for x in expressions]
    work['languages'] = languages

    # do the current one
    work['latest_expression'] = True
    write_expression(place, work)

    for expr in expressions:
        # skip the current one
        if expr['expression_frbr_uri'] != work['expression_frbr_uri']:
            log.info(f"Fetching {expr['expression_frbr_uri']}")
            resp = indigo.get(expr['url'] + '.json', timeout=TIMEOUT)
            resp.raise_for_status()
            expr = resp.json()
            write_expression(place, expr)


def write_expression(place, expr):
    # TODO: ensure dir exists
    dirname = expr['frbr_uri'][1:] + '/' + expr['language']
    os.makedirs(dirname, exist_ok=True)
    fname = os.path.join(dirname, "index.md")
    log.info(f"Writing {expr['expression_frbr_uri']} to {fname}")

    # TODO: images
    # TODO: pdf, epub

    metadata = {
        "layout": "work",
        "place_code": place['code'],
        "toc": work_toc(expr),
        "toc": work_history(expr),
    }

    for fld in "title language expression_date".split():
        metadata[fld] = expr[fld]

    with open(fname, "w") as f:
        f.write("---\n")
        yaml.dump(metadata, f)
        f.write("---\n")


def work_toc(work):
    # TODO
    return []


def work_history(work):
    # TODO
    return []


if __name__ == '__main__':
    update_content()
