import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree


ENDPOINT = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
MAX_RESPONSE_BYTES = 256 * 1024
KST = timezone(timedelta(hours=9))


def request_page(key, year, page):
    query = urlencode({"ServiceKey": key, "solYear": year, "pageNo": page, "numOfRows": 100})
    request = Request(ENDPOINT + "?" + query, headers={"User-Agent": "Autorun-HolidayPublisher/1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=15) as response:
                if response.status != 200:
                    raise ValueError("HTTP failure")
                content = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except (URLError, OSError):
            if attempt == 2:
                raise
            time.sleep(2)
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("Response too large")
    return content


def collect_year(key, year, fetch=request_page):
    holidays = {}
    expected_total = None
    received = 0
    for page in range(1, 11):
        root = ElementTree.fromstring(fetch(key, year, page))
        if root.findtext("./header/resultCode") != "00":
            raise ValueError("API failure")
        body = root.find("body")
        total = int(body.findtext("totalCount"))
        page_number = int(body.findtext("pageNo"))
        if total < 0 or total > 1000 or page_number != page:
            raise ValueError("Invalid pagination")
        if expected_total is None:
            expected_total = total
        if total != expected_total:
            raise ValueError("Changing result count")
        items = body.findall("./items/item")
        received += len(items)
        if received > total or (not items and received < total):
            raise ValueError("Incomplete response")
        for item in items:
            raw_date = item.findtext("locdate", "")
            if len(raw_date) != 8 or not raw_date.isdigit():
                raise ValueError("Invalid date")
            day = datetime.strptime(raw_date, "%Y%m%d").date()
            name = item.findtext("dateName", "").strip()
            is_holiday = item.findtext("isHoliday")
            if day.year != year or not name or len(name) > 200 or is_holiday not in {"Y", "N"}:
                raise ValueError("Invalid holiday")
            if is_holiday == "Y":
                date_key = day.isoformat()
                existing = holidays.get(date_key)
                holidays[date_key] = name if not existing or existing == name else existing + " / " + name
        if received == total:
            return dict(sorted(holidays.items()))
    raise ValueError("Too many pages")


def collect_snapshot(key, now=None, fetch=request_page):
    now = now or datetime.now(timezone.utc)
    current_year = now.astimezone(KST).year
    years = {}
    for year in range(current_year - 1, current_year + 2):
        entries = collect_year(key, year, fetch)
        if not entries and year <= current_year:
            raise ValueError("Required year missing")
        if entries:
            years[str(year)] = entries
    return {
        "schema_version": 1,
        "country": "KR",
        "verified_at": now.astimezone(timezone.utc).isoformat(),
        "years": years,
    }


def main():
    temporary = None
    try:
        key = unquote(os.environ.get("DATA_GO_KR_API_KEY", "").strip())
        if not key:
            raise ValueError("Missing API key")
        payload = collect_snapshot(key)
        target = Path("holidays.json")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        print("Verified years: " + ", ".join(payload["years"]))
        return 0
    except Exception as error:
        details = type(error).__name__
        if isinstance(error, HTTPError):
            details += "/" + str(error.code)
            try:
                body = ElementTree.fromstring(error.read(4096))
                auth_message = body.findtext(".//returnAuthMsg") or body.findtext(".//resultMsg")
                known_errors = {
                    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "SERVICE_KEY_IS_NOT_REGISTERED",
                    "SERVICE_ACCESS_DENIED_ERROR", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
                    "DEADLINE_HAS_EXPIRED_ERROR", "UNREGISTERED_IP_ERROR", "HTTPS_ONLY_ERROR",
                }
                details += "/" + (auth_message if auth_message in known_errors else "XML-error")
                code = body.findtext(".//resultCode") or body.findtext(".//returnReasonCode") or ""
                if code.isdigit() and len(code) <= 3:
                    details += "/code-" + code
            except (ElementTree.ParseError, OSError):
                details += "/non-XML-error"
        elif isinstance(error, URLError):
            details += "/" + type(error.reason).__name__
        print(f"Official holiday collection failed ({details}); previous data preserved.", file=sys.stderr)
        return 1
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
