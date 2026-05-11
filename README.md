In this project, we perform an end-to-end production of a geospatially resolved arXiv co-authorship network. To do this, we utilize a variety of publicly available bibliometric APIs, LLMs, and commercial/open geocoding sources.

Our frontend uses Deck.GL + Next.JS.

```
[arXiv / OpenAlex / PDF metadata]
        |
        v
[affiliation extraction / location parsing] (arXiv hit -> openAlex hit -> LLM hit)
        |
        v
[normalize location string]
        |
        v
[Postgres geocode_cache lookup]
        |
        | cache hit
        v
[attach lon/lat to affiliation / author / institution]
        |
        | cache miss
        v
[insert pending geocode request]
        |
        v
[geocode worker]
        |
        v
[external geocoder API]
        |
        v
[Postgres geocode_cache]
        |
        v
[Deck.GL + Next.js frontend] data sourced from PG DB
```

# Contributors

[Aniket Pant](https://www.aniketpant.me), [Abhinav Gullapalli](https://scholar.google.com/citations?user=ko91go0AAAAJ&hl=en)

Summer 2026