$(function() {
  var $form = $("form#search");
  var $input = $("input[name=q]");
  var $waiting = $("#search-waiting");
  var q = $input.val();
  const $btn = $form.find("button[type=button]");
  $input.keyup(function (e) {
    window.bylawSearch.queryChanged();
  });
  $btn.click(function(e) {
    $input.val('');
    window.bylawSearch.queryChanged();
    $input.focus();
  });
  window.bylawSearch = new Vue({
    el: "#search-results",
    template: `
      <div class="mt-4" v-if="count > 0">
        <h3>You searched for "{{ q }}"</h3>
        <h6 class="mb-5">Found {{count}} results</h6>
        <div class="row justify-content-between container">
          <section>
            <h5>Places</h5>
            <h6>All</h6>
            <ul :key="place.key" v-for="place in places">
              <li v-if="getRegion(place.key)">{{getRegion(place.key)}}({{place.count}})</li>
            </ul>
          </section>
          <div class="col col-10">
            <section class="card mb-3 bg-light" :key="indx" v-for="(result, indx) in results">
              <div class="card-body">
                <h5 class="card-title">{{result.title}}</h5>
                <h6 class="card-subtitle  mb-2 text-muted">{{getRegion(result.country)}} > {{getRegion(result.country + '-' +result.locality)}}</h6>
                <section v-if="result.results.length > 0">
                  <ul :key="snippet.id" v-for="snippet in result.results" class="list-group list-group-flush">
                    <li class="list-group-item">
                      <p class="text-primary">{{snippet.title}}</p>
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
    `,
    data: {
      q: q,
      results: [],
      count: 0,
      places: [],
    },
    methods: {
      queryChanged() {
        const q = document.getElementById("query").value;
        if (q !== this.q) this.q = q;
      },
      getResults() {
        this.results = [];
        this.count = 0;
        setTimeout(() => {
          const params = {
            q: this.q,
            country: "",
            v2: "hi",
          };
          if (this.q)
            $.getJSON(
              "https://srbeugae08.execute-api.eu-west-1.amazonaws.com/default/searchOpenBylaws",
              params,
              (response) => {
                this.count = response.count;
                this.places = response.search.aggregations.places.buckets;
                response.results.forEach((result) => {
                  const newResult = {
                    title: result.title,
                    country: result.country,
                    locality: result.locality,
                    results: result._search.provisions.results,
                  };
                  this.results.push(newResult);
                });
                console.log(response);
                $waiting.hide();
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
        console.log(newValue);
        newValue ? $waiting.show() : $waiting.hide();
        this.getResults();
      },
    },
  });
});
