# Korean public holidays for Autorun

Public holiday dates and names from the Korea Astronomy and Space Science
Institute's Special Day Information API:
https://www.data.go.kr/data/15012690/openapi.do

The collector runs daily at 04:17 Korea Standard Time. It publishes the previous,
current and following calendar years. The following year is omitted if not yet
published. Failed collection leaves the previous file intact. `verified_at`
records a successful source check, even when holiday dates have not changed.

`holidays.json` is available without authentication. It contains `schema_version`
(1), `country` (KR), `verified_at` (UTC ISO timestamp), and `years` (year to
ISO-date/name mapping). Consumers must check freshness and retain an offline cache.

Maintainers register `DATA_GO_KR_API_KEY` as a GitHub Actions repository secret
and can run the workflow manually to verify updates. The credential must never
be placed in files or published data. Check failed workflow runs if the public
verification timestamp stops advancing. Scheduled workflows can be delayed;
GitHub may disable schedules after 60 days without repository activity.

This repository publishes only holiday data and its collector. It does not contain
the signage application's source, user schedules, media or credentials.
