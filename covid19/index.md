---
layout: base
title: South African COVID-19 Regulations
description: COVID-19 Regulations for South Africa, up-to-date and easy to read and share.
---

<header>
  <div class="container">
    <div class="header-content">
      <h1>South Africa COVID-19 Regulations</h1>
    </div>
  </div>
</header>

<article>
  <div class="container">
    <div class="alert alert-warning">
      Some municipal functions such as public transport, restaurant hours and liquor sales are impacted by the recent national COVID-19 regulations listed below.
    </div>

    <p>For more information and resources on COVID-19, please visit <a href="https://sacoronavirus.co.za/">sacoronavirus.co.za</a>.</p>

    <table class="table table-sm table-hover sticky-thead">
      <thead class="thead-light">
        <tr>
          <th>Title</th>
          <th>Published</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
        {% assign works = site.data.works.za | where: "stub", "false" | where: "repealed", "false" | where: "has_parent", "true" %}
        {% assign groups = works | group_by: "parent_work.title" | sort: "name" %}

        {% for group in groups %}
          <tr>
            <th class="pt-3" colspan="3">{{ group.name }}</th>
          </tr>

          {% assign items = group.items | sort: "title" %}
          {% for work in items %}
            <tr>
              <td>
                <a href="{{ work.frbr_uri }}/{{ work.language }}/">{{ work.title }}</a>
              </td>
              <td class="text-nowrap">{{ work.publication_date }}</td>
              <td class="text-nowrap">
                {% if work.expression_date != work.publication_date %}
                  {{ work.expression_date }}
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        {% endfor %}
      </tbody>
    </table>

    {% assign repealed = site.data.works.za | where: "repealed", "true" | sort: "title" %}
    {% if repealed %}
      <h4 class="mt-4">Repealed</h4>

      <table class="table table-sm table-hover">
        <thead class="thead-light">
          <tr>
            <th>Title</th>
            <th>Published</th>
            <th>Repealed</th>
          </tr>
        </thead>
        <tbody>
          {% for work in repealed %}
            <tr>
              <td>
                <a href="{{ work.frbr_uri }}/{{ work.language }}/">{{ work.title }}</a>
              </td>
              <td class="text-nowrap">{{ work.publication_date }}</td>
              <td class="text-nowrap">{{ work.repeal.date }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </div>

</article>
