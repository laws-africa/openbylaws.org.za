$(function() {
  window.bylawSearch = new Vue({
    el: '#search-results',
    template: `
    <div>you searched for {{ q }}</div>
    `,
    data: {
      q: 'hi',
    }
  });
});
