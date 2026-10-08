# Lawn Sign Routing Prototype

Proof of concept for turning the lawn sign request sheet into one delivery route per town, each starting and ending at Town Hall, with a map and phone-ready Google Maps links for town captains.

**All data in this folder is synthetic.** Names, phone numbers (781-555-01xx, the reserved fictional range), emails (`@example.com`), house numbers, and route tokens are made up. Street names are real streets in each town so the geocoder has something to match; any match to a real residence is coincidental.

## What it does

1. **Load** the requests export, skipping the three title rows above the column headers. Keep rows where `Installation Authorized` is "Yes" and `Delivery Status` is not "Delivered" (any capitalization).
2. **Group** requests by `Town`.
3. **Geocode** every address with the free [U.S. Census batch geocoder](https://geocoding.geo.census.gov/geocoder/). Addresses with no match, or with a tie between candidates, are listed as failures, not guessed.
4. **Route** each town: drive times from the public [OSRM](https://project-osrm.org/) server, then the shortest round trip from Town Hall. Exact solver (Held-Karp) for up to 14 stops; nearest-neighbor plus 2-opt above that.
5. **Write** `routes.csv` with the columns of the sheet's Routes tab: Route ID, Town, Volunteer, Route Token, Stop, Request ID, Name, Address, Signs, Status, Reason, Created, Start, End, Active. Volunteer and Route Token come from the Captains tab. Addresses that did not geocode are included with Status `Unrouted` and a Reason.
6. **Map** every route in its own color in `routes_map.html`, with Google Maps directions links per town. A link holds at most 9 intermediate stops; longer routes are split into parts, and each part starts where the previous one ended.
7. **Summarize** stops, signs, drive time, and geocoding failures in the terminal.

No API keys, no paid services, no installs beyond Python 3 and `requests`.

## Run it

From this folder:

```bash
python3 make_test_data.py sample-data
```

```bash
python3 build_routes.py sample-data/test_lawn_sign_requests.csv sample-data/test_captains.csv sample-output
```

To run on the real sheet, download the **Lawn Sign Requests** and **Captains** tabs as CSV (File → Download → Comma-separated values) into `private/`, which git ignores:

```bash
python3 build_routes.py private/requests.csv private/captains.csv private/output
```

Town Hall addresses are set in `TOWN_HALLS` at the top of `build_routes.py`.

## Sample results

From the synthetic data in `sample-data/` (100 requests, 56 authorized and undelivered):

| Town | Stops | Signs | Drive time | Miles | Maps links |
|---|---|---|---|---|---|
| Duxbury | 7 | 11 | 30 min | 14.6 | 1 |
| Halifax | 12 | 20 | 48 min | 20.7 | 2 |
| Hanson | 16 | 23 | 31 min | 11.9 | 2 |
| Marshfield | 8 | 14 | 47 min | 22.4 | 1 |
| Pembroke | 6 | 10 | 28 min | 13.2 | 1 |

Seven addresses did not geocode: two fake streets planted on purpose (Moonbeam Terrace, Quillfeather Way) and five real streets where the random house number falls outside the Census address ranges.

[`sample-output/routes_map.html`](sample-output/routes_map.html) is the map. GitHub shows its source rather than rendering it; download it and open it in a browser.

## Limitations

- **Drive time is driving only.** It excludes time spent at each stop installing signs, and OSRM does not model traffic.
- **The public OSRM server is a demo service** with no uptime guarantee and fair-use limits. Fine for a campaign's volume; not for heavy automated use.
- **Routes above 14 stops use a heuristic**, so they are usually but not guaranteed shortest (Hanson in the sample).
- **Census geocoding misses** typos, new construction, and some rural addresses. Failures need a human to fix the address in the sheet.
- **One route per town.** No splitting a large town across several volunteers or capping signs per car.
- **Python on some Macs stalls on IPv6**, so the script forces IPv4 for its own requests.

## Privacy

Real exports contain residents' names, phones, emails, and home addresses, and real route tokens act like passwords. Keep them in `private/` (git-ignored) and never commit them. `geocode_cache.json` is also ignored because it stores addresses.
