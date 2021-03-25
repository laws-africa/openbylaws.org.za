$(function() {
  window.bylawSearch = new Vue({
    el: "#search-container",
    template: `
      <div class="container">
        <div class="clearfix">
          <form action="/search.html" class="form-horizontal" id="search" method="get">
            <input name="region" type="hidden" value="">
            <div class="input-group">
              <input autofocus="autofocus" class="form-control" v-model="q" id="query" name="q" placeholder="What are you looking for?" type="search">
              <div class="input-group-append">
                <button @click.prevent="q=''" class="btn btn-primary">
                  Clear
                </button>
              </div>
            </div>
          </form>
        </div>
        <div v-if="waiting">
          Searching...
        </div>
        <div class="mt-4" v-if="count > 0">
          <p class="text-danger" v-if="suggestions">Did you mean <span class="text-secondary" v-html="suggestions"></span>?</p>
          <h3>You searched for "{{ q }}"</h3>
          <h6 class="mb-5">Found {{count}} results</h6>
          <div class="row justify-content-between container">
            <section>
              <h5>Places</h5>
              <h6 :class="activeAll ? '' : 'text-primary'" @click="getResults()">All</h6>
              <ul class="places" :key="place.key" v-for="place in places">
                <li @click="onPlaceClick(place.key)" class="place text-primary" :id="place.key" v-if="getRegion(place.key)">{{getRegion(place.key)}}({{place.count}})</li>
              </ul>
            </section>
            <div v-if="results.length > 0" class="col col-10">
              <section class="card mb-3 bg-light" :key="indx" v-for="(result, indx) in results">
                <div class="card-body">
                  <h5 class="card-title">{{result.title}}</h5>
                  <h6 class="card-subtitle  mb-2 text-muted">{{getRegion(result.country)}} > {{getRegion(result.country + '-' +result.locality)}}</h6>
                  <section v-if="result.results.length > 0">
                    <ul :key="snippet.id" v-for="snippet in result.results" class="list-group list-group-flush">
                      <li class="list-group-item">
                        <p class="text-primary"><a :href="result.expression_frbr_uri + '#' + snippet.id">{{snippet.title}}</a></p>
                        <p :key="indx" v-for="(highlight, indx) in snippet._search.highlight.body">
                          <span v-html="highlight"></span>
                        </p>
                      </li>
                    </ul>
                  </section>
                </div>
              </section>
            </div>
          </div>
        </div>
        <div v-else-if="q && noResults">No results match your search</div>
      </div>
    `,
    data: {
      q: "",
      results: [],
      places: [],
      count: 0,
      activeAll: true,
      noResults: false,
      waiting: false,
    },
    methods: {
      queryChanged() {
        const q = document.getElementById("query").value;
        if (q !== this.q) this.q = q;
      },
      onPlaceClick(id) {
        this.activeAll = false;
        const places = document.getElementsByClassName("place");
        const active = document.getElementById(id);
        Array.from(places).forEach((place) =>
          place.classList.add("text-primary")
        );
        active.classList.remove("text-primary");
        this.getResults(id);
      },
      getResults(place) {
        this.results = [];
        if (!place) {
          this.activeAll = true;
          this.count = 0;
        }
        setTimeout(() => {
          const params = {
            q: this.q,
            place: place ? place : "",
            v2: "hi",
          };
          if (this.q)
            $.getJSON(
              "https://srbeugae08.execute-api.eu-west-1.amazonaws.com/default/searchOpenBylaws",
              params,
              (response) => {
                this.count = response.count;
                this.places = response.search.aggregations.places.buckets;
                this.suggestions = response.search.did_you_mean
                  ? response.search.did_you_mean.html
                      .replace(/^\s*[;:",.()-]+/, "")
                      .replace(/<b>/g, "<mark>")
                      .replace(/<\/b>/g, "</mark>")
                      .trim()
                  : undefined;
                response.results.forEach((result) => {
                  const newResult = {
                    title: result.title,
                    country: result.country,
                    locality: result.locality,
                    results: result._search.provisions.results,
                    expression_frbr_uri: result.expression_frbr_uri
                  };
                  this.results.push(newResult);
                });
                this.waiting = false;
                if (response.count <= 0) this.noResults = true;
              }
            );
        }, 1000);
      },
      getRegion(code) {
        const region = REGIONS.find(
          (region) => region.code === code.toString()
        );
        if (region) return region.name;
        return "";
      },
    },
    watch: {
      q(newValue, oldValue) {
        this.noResults = false;
        if (newValue) this.waiting = true;
        else this.waiting = false;
        this.getResults();
      },
    },
  });
});
