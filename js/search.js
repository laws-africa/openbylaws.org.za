$(function() {
  function debounce(func, wait, immediate) {
    let timeout;
    return function() {
      const context = this;
      const args = arguments;
      const later = function() {
        timeout = null;
        if (!immediate) func.apply(context, args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
      if (immediate && !timeout) func.apply(context, args);
    };
  }

  const regionMap = {};
  for (let region of REGIONS) {
    regionMap[region.code] = region;
  }

  window.bylawSearch = new Vue({
    el: "#search-container",
    template: `
      <div class="container">
        <div class="clearfix">
          <form action="/search.html" class="form-horizontal" method="get" @submit.prevent="search">
            <div class="input-group">
              <input autofocus class="form-control" v-model="q" name="q" placeholder="What are you looking for?" type="search" autocomplete="off">
              <div class="input-group-append">
                <button type="button" class="btn btn-primary">Search</button>
              </div>
            </div>
          </form>
        </div>
        <div v-if="waiting">
          Searching...
        </div>
        <div class="mt-3" v-if="count > 0">
          <p class="text-danger" v-if="suggestion">
            Did you mean <a href="#" v-html="suggestion.html" @click.prevent="q = suggestion.q"></a>?
          </p>
          
          <h6 class="mb-4">Found {{count}} results</h6>
          
          <div class="row justify-content-between">
            <section class="col-md-3 col-lg-2" v-if="!forcePlace">
              <ul class="places">
                <li>
                  <a href="#" @click.prevent="place = ''" :class="place == '' ? 'font-weight-bold' : ''">All ({{ count }})</a>
                </li>
                <li v-if="p.details" v-for="p in places" :key="p.key">
                  <a href="#" @click.prevent="place = p.key" :class="place == p.key ? 'font-weight-bold' : ''">
                    {{ p.details.name }} ({{ p.count }})
                  </a>
                </li>
              </ul>
            </section>

            <div class="col-md-9 col-lg-10">
              <section class="card mb-3 bg-light" :key="indx" v-for="(result, indx) in results" v-if="result.place">
                <div class="card-body">
                  <h5 class="card-title"><a :href="result.url">{{result.title}}</a></h5>
                  <h6 class="card-subtitle  mb-2 text-muted">{{result.place.name}}</h6>
                  
                  <section v-if="result.results.length > 0">
                    <ul :key="snippet.id" v-for="snippet in result.results" class="list-group list-group-flush">
                      <li class="list-group-item">
                        <div><a :href="result.url + '#' + snippet.id">{{snippet.title}}</a></div>
                        <div :key="indx" v-for="(highlight, indx) in snippet._search.highlight.body">
                          ... <span v-html="highlight"></span> ...
                        </div>
                      </li>
                    </ul>
                  </section>
                </div>
              </section>
            </div>
          </div>
        </div>

        <div v-else-if="q && !waiting && count == 0">No results match your search</div>
      </div>
    `,
    data: {
      q: "",
      results: [],
      places: [],
      forcePlace: null,
      count: 0,
      waiting: false,
      place: '',
      suggestion: null,
    },
    mounted() {
      window.onpopstate = this.searchFromUrl;
      // must we always limit results to one place?
      if (window.place) {
        this.forcePlace = this.place = window.place;
      }
      this.searchFromUrl();
    },
    methods: {
      searchFromUrl() {
        // kick-off search from URL
        const params = new URLSearchParams(location.search);
        this.q = params.get('q');
        if (!this.forcePlace) {
          this.place = params.get('region');
        }
      },
      search() {
        const q = this.q.trim();
        this.waiting = q.length > 0;

        // update URL
        history.pushState(null, null, '?q=' + encodeURIComponent(this.q) + '&region=' + encodeURIComponent(this.place));

        if (q.length > 0) {
          this.getResults();
        }
      },
      getResults() {
        this.results = [];
        this.count = 0;
        const params = {
          q: this.q.trim(),
          place: this.place
        };
        $.getJSON("https://jjkxbrqcf6.execute-api.eu-west-1.amazonaws.com/search", params)
          .done((response) => {
            this.count = response.count;
            this.places = response.search.aggregations.places.buckets.map((p) => {
              p.details = regionMap[p.key];
              return p;
            });
            this.suggestion = response.search.did_you_mean;
            if (this.suggestion) {
              this.suggestion.html = this.suggestion.html.replace(/^\s*[;:",.()-]+/, "").trim();
            }
            this.results = response.results.map((result) => {
              let url = result.expression_frbr_uri.substring(4, result.expression_frbr_uri.indexOf('@')) + '/';
              const place = regionMap[result.country + (result.locality ? '-' + result.locality : '')];
              if (place && place.microsite) {
                url = 'https://' + place.bucket + url;
              }

              return {
                title: result.title,
                place: place,
                url: url,
                results: result._search.provisions.results,
              };
            });
          })
          .always(() => {
            this.waiting = false;
          });
      }
    },
    computed: {
      noPlace() {
        return this.place === '';
      }
    },
    watch: {
      q: debounce(function(newValue, oldValue) {
        this.search();
      }, 250),
      place () {
        this.search();
      }
    },
  });
});
