# Paged Out! Articles Feed

Generates an Atom feed with individual article entries from [Paged Out!](https://pagedout.institute) magazine issues that have a web viewer.

See the generated [website](https://abhin4v.github.io/paged-out-feed/).

## Usage

```bash
# With Nix
nix-shell --run "python generate_feed.py"

# Or without nix
pip install -r requirements.txt
python generate_feed.py
```

Output goes to `_site/`. Set `CI=true` to disable caching.

## How it works

1. Fetches issue list from pagedout.institute/atom.xml.
2. Downloads web viewer pages for each issue.
3. Parses article links from the table of contents.
4. Generates Atom feed at `_site/feed.atom`.

A GitHub Actions workflow runs daily to update the feed.
