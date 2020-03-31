# openbylaws.org.za

This repo is the openbylaws.org.za website, based on Jekyll. There are two major steps to building this website:

1. `bin/update-content.py` is a Python script which pulls by-law information from Laws.Africa and sets up the appropriate Jekyll site structure.
2. `jekyll build` builds the website as a regular Jekyll website.

In production, these two steps are performed by Travis-CI, and the resulting site is force pushed to the `gh-pages` branch as a static website.

# But where is the content?

This repo looks a bit empty, there are no places and by-laws. This saves us from having a repo tracking every change to every by-law.
Instead, this repo is fleshed out by Travis-CI during the build phase.

## Local development

1. Clone this repo
2. Install Python dependencies: `pip install -r requirements.txt`
3. Install Jekyll: `bundle install`
4. Get your Laws.Africa API token from [edit.laws.africa/accounts/profile/api/](https://edit.laws.africa/accounts/profile/api/)
5. `export INDIGO_API_AUTH_TOKEN=your-token`
6. Pull in by-law content for just one region: `bin/update-content.py --quick za-cpt`
7. Build the website: `bundle exec jekyll server --watch --incremental`
