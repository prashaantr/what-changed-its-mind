"""Bounded public-source acquisition and deliberately narrow, auditable parsers.

No browser cookies, API credentials, scraping proxies, or inferred election facts.
Raw responses stay under ignored data/raw; public records contain factual extracts.
"""
from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import re
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .models import Acquisition, Candidate, Dataset, Observation, Race, Source, digest, utcnow, write_json

HOSTS = frozenset({"www.ncsbe.gov", "s3.amazonaws.com", "www2.census.gov", "www.census.gov", "surveyresearch-ecu.reportablenews.com", "engagious.com", "centerforpolitics.org", "www.fec.gov", "www.sos.state.tx.us", "maristpoll.marist.edu", "sabatoscrystalball.substack.com", "www.texastribune.org", "keokukcounty.iowa.gov", "www.jocoelection.org", "www.iowapublicradio.org", "www.kcur.org", "afightworthhaving.com"})
USER_AGENT = "ElectionEvidenceResearch/0.1 (public source audit)"
NC_CSV = "https://s3.amazonaws.com/dl.ncsbe.gov/Elections/2026/Candidate%20Filing/Candidate_Listing_2026.csv"
ECU_RELEASE = "https://surveyresearch-ecu.reportablenews.com/pr/ecu-poll-cooper-s-lead-holds-at-7-points"

@dataclass(frozen=True)
class FetchedResource:
    body: bytes
    final_url: str
    status: int
    media_type: str


def validate_url(url: str, allowed_hosts: frozenset[str] = HOSTS) -> None:
    """Reject credentials, non-HTTPS, arbitrary hosts and nonpublic DNS answers."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Only credential-free HTTPS on port 443 is permitted")
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        raise ValueError(f"Host is not allowlisted: {host}")
    if host == "s3.amazonaws.com" and not parsed.path.startswith("/dl.ncsbe.gov/"):
        raise ValueError("Only the official NCSBE S3 bucket is allowed")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Source resolved to a nonpublic address")


def secure_fetch(url: str, *, allowed_hosts: frozenset[str] = HOSTS,
                 timeout: float = 30, max_bytes: int = 12_000_000,
                 client: httpx.Client | None = None) -> FetchedResource:
    """Validate each redirect; limit body bytes; never retry an access denial.

Only fixed publisher URLs are accepted by the collector. This is not a public URL
proxy. DNS validation does not claim to defend arbitrary hostile DNS rebinding.
"""
    own_client = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False,
                                   headers={"User-Agent": USER_AGENT})
    try:
        for _ in range(6):
            validate_url(url, allowed_hosts)
            with client.stream("GET", url, follow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect without Location")
                    url = urljoin(url, location)
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("Source exceeded acquisition size limit")
                    chunks.append(chunk)
                return FetchedResource(b"".join(chunks), str(response.url), response.status_code,
                                       response.headers.get("content-type", "application/octet-stream").split(";")[0])
        raise ValueError("Too many source redirects")
    finally:
        if own_client:
            client.close()


def parse_nc_roster(body: bytes) -> list[Candidate]:
    """2026 general Senate ballot only; discard addresses/email/phone immediately."""
    rows = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    required = {"election_dt", "contest_name", "name_on_ballot", "party_candidate"}
    if not required.issubset(rows.fieldnames or []):
        raise ValueError("NCSBE CSV schema changed")
    candidates: dict[str, Candidate] = {}
    for row in rows:
        if row["election_dt"] != "11/03/2026" or row["contest_name"] != "US SENATE":
            continue
        name = row["name_on_ballot"].strip()
        party = row["party_candidate"].strip()
        candidate_id = "nc-sen-2026-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        item = Candidate(id=candidate_id, name=name, party=party)
        if candidate_id in candidates and candidates[candidate_id] != item:
            raise ValueError("Conflicting candidate identity across county records")
        candidates[candidate_id] = item
    if len(candidates) < 2:
        raise ValueError("No usable general Senate roster")
    return sorted(candidates.values(), key=lambda x: x.id)


def text_content(body: bytes) -> str:
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def parse_ecu_poll(body: bytes) -> dict:
    """Fail closed if this specific publisher release no longer matches its schema."""
    text = text_content(body)
    topline = re.search(r"Roy Cooper leading Republican nominee Michael Whatley,\s*(\d+)% to (\d+)%", text)
    n = re.search(r"based on ([\d,]+) completed responses", text)
    field = re.search(r"This ECU Poll was conducted (September \d+) through (October \d+), (2026)", text)
    date = re.search(r"(OCTOBER\s+\d+,\s+2026), GREENVILLE", text)
    undecided = re.search(r"only (\d+)% remaining undecided and (\d+)% supporting a minor-party or write-in candidate", text)
    if not all((topline, n, field, date, undecided)):
        raise ValueError("ECU release schema/content changed; manual source audit required")
    published_day = datetime.strptime(date.group(1), "%B %d, %Y").date().isoformat()
    return {
        "pollster": "East Carolina University Center for Survey Research",
        "sample_size": int(n.group(1).replace(",", "")), "population": "LV",
        "field_start": datetime.strptime(field.group(1) + " " + field.group(3), "%B %d %Y").date().isoformat(),
        "field_end": datetime.strptime(field.group(2) + " " + field.group(3), "%B %d %Y").date().isoformat(),
        "published_date": published_day, "publication_time_precision": "day",
        "shares_percent": {"Roy Cooper": int(topline.group(1)), "Michael Whatley": int(topline.group(2))},
        "undecided_percent": int(undecided.group(1)), "other_percent": int(undecided.group(2)),
        "rounding_note": "Publisher reports rounded whole percentages; categories may not sum to 100.",
        "question_variant": "Initial preference allowing undecided; not forced-choice follow-up",
        "mode": "MMS-to-web plus supplemental online panel",
    }


def source_records() -> list[Source]:
    facts = "Derived factual records only. Full publisher page is retained locally, not licensed by this project."
    return expansion_sources() + [
        Source(id="fec-federal-elections-2020", url="https://www.fec.gov/resources/cms-content/documents/federalelections2020.pdf", publisher="Federal Election Commission", kind="official_prior_results", title="Federal Elections2020", attribution="Federal Election Commission, October2022, 2020 U.S. Senate Results", rights_basis="US federal government publication of official election results; factual vote counts and percentages.", storage="allowed", model_use="allowed", redistribution="allowed", notes="Prior2020 class2 Senate contests; historical candidates remain separate from2026 candidate IDs. Fixed14MB cap for this12.53MB federal PDF."),
        Source(id="tribune-tx-debates-2026-10-07", url="https://www.texastribune.org/2026/10/07/texas-debate-republicans-talarico-paxton-abbott-hinojosa-election/", publisher="The Texas Tribune", kind="local_reporting", title="Most Texas Republicans ignore Democratic calls to debate in statewide races", attribution="Kayla Guo, The Texas Tribune, October 7, 2026", rights_url="https://www.texastribune.org/republishing-guidelines/", rights_basis="Original independently worded factual event records only, with attribution and link; no article text or photographs republished. Publisher separately permits article republication under its guidelines.", storage="allowed", model_use="allowed", redistribution="allowed", notes="Historical report as of October7; no assumption its debate status remains current."),
        Source(id="crystal-ball-oct27", url="https://sabatoscrystalball.substack.com/p/democrats-appear-to-hold-narrow-senate", publisher="Sabato's Crystal Ball / UVA Center for Politics", kind="race_rating", title="Democrats Appear to Hold Narrow Senate Edge with Week to Go", attribution="Sabato's Crystal Ball, Kyle Kondik and J. Miles Coleman, October 27, 2026", rights_basis=facts, storage="allowed", model_use="allowed", redistribution="allowed", notes="Export discrete rating facts only; full article stays local. Current main rating pages return403."),
        Source(id="texas-ballot-2026", url="https://www.sos.state.tx.us/elections/forms/2026-ballot-cert.pdf", publisher="Texas Secretary of State", kind="official_roster", title="2026 General Election Ballot Certification", attribution="Texas Secretary of State, August28,2026", rights_basis="Derived public candidate facts only", storage="allowed", model_use="allowed", redistribution="allowed"),
        Source(id="texas-writeins-2026", url="https://www.sos.state.tx.us/elections/forms/2026-write-In-ballot-cert.pdf", publisher="Texas Secretary of State", kind="official_roster", title="2026 Declared Write-In Candidate Certification", attribution="Texas Secretary of State, August28,2026", rights_basis="Derived public candidate facts only", storage="allowed", model_use="allowed", redistribution="allowed"),
        Source(id="marist-tx-2026-10-14", url="https://maristpoll.marist.edu/polls/2026-midterm-elections-in-texas-october-2026/", publisher="Marist Poll", kind="poll", title="2026 Midterm Elections in Texas, October2026", attribution="Marist Poll, October14,2026", rights_basis=facts, storage="allowed", model_use="allowed", redistribution="allowed", notes="LV toplines;1196 is RV sample, LV sample unavailable in article. No fabricated LV count."),
        Source(id="ncsbe-candidate-list-2026", url=NC_CSV, publisher="North Carolina State Board of Elections", kind="official_roster", title="2026 Candidate List CSV", attribution="North Carolina State Board of Elections", rights_url="https://www.ncsbe.gov/results-data/candidate-lists", rights_basis="Official public candidate list; only candidate names, party and contest facts exported; contact fields discarded.", storage="allowed", model_use="allowed", redistribution="allowed"),
        Source(id="census-state-codes", url="https://www2.census.gov/geo/docs/reference/state.txt", publisher="US Census Bureau", kind="geography", title="State FIPS and ANSI codes", attribution="US Census Bureau", rights_url="https://www.census.gov/about/policies/privacy/privacy-policy.html", rights_basis="US federal government factual geography reference.", storage="allowed", model_use="allowed", redistribution="allowed"),
        Source(id="ecu-nc-poll-2026-10-08", url=ECU_RELEASE, publisher="ECU Center for Survey Research", kind="poll", title="ECU Poll: Cooper's Lead Holds at 7 Points", attribution="ECU Center for Survey Research, October 8, 2026", rights_url=ECU_RELEASE, rights_basis=facts, storage="allowed", model_use="allowed", redistribution="allowed", notes="Rights allowed for manually specified factual numeric extracts only. Full release not public-exported. Publication day known; observation published_at left null because exact time not stated."),
        Source(id="crystal-ball-senate-2026", url="https://centerforpolitics.org/crystalball/2026-senate/", publisher="UVA Center for Politics", kind="race_rating", title="Crystal Ball 2026 Senate ratings", attribution="Sabato's Crystal Ball, UVA Center for Politics", rights_basis="Access and redistribution not established; do not infer current ratings.", notes="Cohort eligibility blocked until actual primary-source rating acquired."),
        Source(id="crystal-ball-house-2026", url="https://centerforpolitics.org/crystalball/2026-house/", publisher="UVA Center for Politics", kind="race_rating", title="Crystal Ball 2026 House ratings", attribution="Sabato's Crystal Ball, UVA Center for Politics", rights_basis="Access and redistribution not established; do not infer current ratings."),
        Source(id="engagious-deciders-2026", url="https://engagious.com/2026deciders/", publisher="Engagious / Sago / Syracuse IDJC", kind="focus_group", title="2026 Deciders sessions", attribution="Engagious / Sago / Syracuse IDJC; https://engagious.com/swingvoters/", rights_url="https://engagious.com/2026deciders/", rights_basis="Page includes reuse language referring to swing voter study; scope for full Deciders transcripts/media unresolved.", storage="allowed", model_use="unknown", redistribution="unknown", notes="Discovery metadata only. Video existence does not imply verified transcript, participant counts or representative sample."),
    ]


def collect(output_path: str | Path = "data/processed/dataset.json", raw_dir: str | Path = "data/raw", *, timeout: float = 30, reuse_existing: bool = True) -> Dataset:
    sources = source_records()
    acquisitions, bodies, report = [], {}, []
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    cached = {}
    if reuse_existing and Path(output_path).exists():
        previous = Dataset.model_validate_json(Path(output_path).read_text())
        previous_sources = {source.id: source for source in previous.sources}
        for acq in previous.acquisitions:
            old_source = previous_sources.get(acq.source_id)
            if old_source:
                cached[acq.source_id] = (old_source.url, acq)
    for source in sources:
        try:
            if source.id in cached and cached[source.id][0] == source.url:
                acq = cached[source.id][1]
                raw_path = raw_dir / acq.raw_sha256
                body = raw_path.read_bytes()
                if hashlib.sha256(body).hexdigest() != acq.raw_sha256:
                    raise ValueError("Cached acquisition hash mismatch")
                acquisitions.append(acq)
                bodies[source.id] = (body, acq)
                report.append({"source_id": source.id, "status": "reused_verified_acquisition", "bytes": len(body), "retrieved_at": acq.retrieved_at.isoformat(), "sha256": acq.raw_sha256})
                continue
            fetched = secure_fetch(source.url, timeout=timeout, max_bytes=14_000_000 if source.id == "fec-federal-elections-2020" else 12_000_000)
            retrieved = utcnow()
            sha = hashlib.sha256(fetched.body).hexdigest()
            raw_path = raw_dir / sha
            if not raw_path.exists():
                raw_path.write_bytes(fetched.body)
            acq = Acquisition(id=f"acq-{source.id}-{sha[:12]}", source_id=source.id, retrieved_at=retrieved,
                              raw_sha256=sha, media_type=fetched.media_type, http_status=fetched.status,
                              final_url=fetched.final_url, parser_version="collection-1")
            acquisitions.append(acq)
            bodies[source.id] = (fetched.body, acq)
            report.append({"source_id": source.id, "status": "acquired", "bytes": len(fetched.body), "retrieved_at": retrieved.isoformat(), "sha256": sha})
        except (httpx.HTTPError, ValueError, OSError) as exc:
            report.append({"source_id": source.id, "status": "blocked", "error": str(exc), "attempted_at": utcnow().isoformat()})
    races, observations = [], []
    if "ncsbe-candidate-list-2026" in bodies:
        try:
            candidates = parse_nc_roster(bodies["ncsbe-candidate-list-2026"][0])
            geography_ok = False
            if "census-state-codes" in bodies:
                rows = csv.DictReader(io.StringIO(bodies["census-state-codes"][0].decode()), delimiter="|")
                geography_ok = any(r["STATE"] == "37" and r["STUSAB"] == "NC" and r["STATE_NAME"] == "North Carolina" for r in rows)
            race = Race(id="NC-SEN-2026", name="North Carolina US Senate", office="senate", state="NC", state_fips="37", seat="class-2", boundary_version="Census state reference, state-wide Senate seat", geography_verified=geography_ok, roster_verified=True, candidates=candidates, rating=None, rating_source_id=None, source_ids=["ncsbe-candidate-list-2026", "census-state-codes"], selected=False, selection_reason="Real integration/reference race. Current primary-source Toss-up/Lean rating not acquired; excluded from forecast cohort.")
            races.append(race)
            if "ecu-nc-poll-2026-10-08" in bodies:
                body, acq = bodies["ecu-nc-poll-2026-10-08"]
                value = parse_ecu_poll(body)
                value["shares"] = {c.id: value["shares_percent"][c.name] for c in candidates if c.name in value["shares_percent"]}
                known_names = {c.name for c in candidates}
                if not set(value["shares_percent"]).issubset(known_names):
                    raise ValueError("Poll candidates do not match verified roster")
                # Conservatively use first actual retrieval for availability, never a guessed publication hour.
                observations.append(Observation(id="obs-ecu-nc-2026-10-08", source_id=acq.source_id, acquisition_id=acq.id, race_id=race.id, kind="poll", value=value, locator="Release main topline paragraph and Methodology section", available_at=acq.retrieved_at, retrieved_at=acq.retrieved_at, content_sha256=digest(value), geography="NC", geography_scope="state"))
        except ValueError as exc:
            report.append({"source_id": "derived-nc", "status": "parse_failed", "error": str(exc)})
    if all(key in bodies for key in ("texas-ballot-2026", "texas-writeins-2026", "census-state-codes")):
        try:
            candidates = parse_texas_roster(bodies["texas-ballot-2026"][0], bodies["texas-writeins-2026"][0])
            census = bodies["census-state-codes"][0].decode()
            geography_ok = "48|TX|Texas|" in census
            rating = None
            if "crystal-ball-oct27" in bodies:
                rating_text = text_content(bodies["crystal-ball-oct27"][0])
                # Explicit prose: seven states; AK and MI lean; the others remain Toss-ups.
                if all(phrase in rating_text for phrase in ("Alaska, Iowa, Kansas, Ohio, and Texas", "Alaska and Michigan at least leaning to Democrats", "While the others are Toss-ups and remain so today")):
                    rating = "Toss-up"
            race = Race(id="TX-SEN-2026", name="Texas US Senate", office="senate", state="TX", state_fips="48", seat="class-2", boundary_version="Census state reference, state-wide Senate seat", geography_verified=geography_ok, roster_verified=True, candidates=candidates, rating=rating, rating_source_id="crystal-ball-oct27" if rating else None, source_ids=["texas-ballot-2026", "texas-writeins-2026", "census-state-codes"] + (["crystal-ball-oct27"] if rating else []), selected=bool(rating and geography_ok), selection_reason="Verified official roster incl declared write-ins and primary publisher Toss-up rating; eligible partial-cohort pilot, not complete30-race cohort.")
            races.append(race)
            if "marist-tx-2026-10-14" in bodies:
                body, acq = bodies["marist-tx-2026-10-14"]
                value = parse_marist_tx(body, candidates)
                observations.append(Observation(id="obs-marist-tx-2026-10-14", source_id=acq.source_id, acquisition_id=acq.id, race_id=race.id, kind="poll", value=value, locator="U.S. Senate Race in Texas and Methodology sections", available_at=acq.retrieved_at, retrieved_at=acq.retrieved_at, content_sha256=digest(value), geography="TX", geography_scope="state"))
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            report.append({"source_id": "derived-tx", "status": "parse_failed", "error": str(exc)})
    if "tribune-tx-debates-2026-10-07" in bodies and any(r.id == "TX-SEN-2026" for r in races):
        body, acq = bodies["tribune-tx-debates-2026-10-07"]
        try:
            value = parse_tribune_debates(body)
            observations.append(Observation(id="obs-tribune-tx-debates-2026-10-07", source_id=acq.source_id, acquisition_id=acq.id, race_id="TX-SEN-2026", kind="local_reporting", value=value, locator="Opening four paragraphs of Kayla Guo's October7 report; Senate facts only", available_at=acq.retrieved_at, retrieved_at=acq.retrieved_at, content_sha256=digest(value), geography="TX", geography_scope="state"))
        except ValueError as exc:
            report.append({"source_id": acq.source_id, "status": "parse_failed", "error": str(exc)})
    if "crystal-ball-oct27" in bodies:
        rating_text = text_content(bodies["crystal-ball-oct27"][0])
        if all(p in rating_text for p in ("Alaska, Iowa, Kansas, Ohio, and Texas", "Alaska and Michigan at least leaning to Democrats", "While the others are Toss-ups and remain so today", "Maine")):
            for state, name, fips in [("IA", "Iowa", "19"), ("KS", "Kansas", "20"), ("ME", "Maine", "23"), ("OH", "Ohio", "39")]:
                races.append(Race(id=f"{state}-SEN-2026", name=f"{name} US Senate", office="senate", state=state, state_fips=fips, boundary_version="pending official election geography verification", geography_verified=False, roster_verified=False, candidates=[], rating="Toss-up", rating_source_id="crystal-ball-oct27", source_ids=["crystal-ball-oct27"], selected=False, selection_reason="Verified rating metadata only. Candidate roster and election geography pending; excluded from cohort and inference."))
    expand_records(races, observations, bodies, report)
    if "fec-federal-elections-2020" in bodies:
        body, acq = bodies["fec-federal-elections-2020"]
        try:
            prior = parse_fec_senate_2020(pdf_text(body))
            for state, value in prior.items():
                race_id = f"{state}-SEN-2026"
                if not any(r.id == race_id and r.roster_verified for r in races):
                    continue
                observations.append(Observation(id=f"obs-fec-2020-senate-{state.lower()}", source_id=acq.source_id, acquisition_id=acq.id, race_id=race_id, kind="fundamental", value=value, locator=f"2020 U.S. Senate Results, {state} general-election column; printed pages74–75 (IA/KS),82 (TX)", available_at=acq.retrieved_at, retrieved_at=acq.retrieved_at, content_sha256=digest(value), geography=state, geography_scope="state"))
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            report.append({"source_id": acq.source_id, "status":"parse_failed", "error":str(exc)})
    dataset = Dataset(races=races, sources=sources, acquisitions=acquisitions, observations=observations)
    write_json(output_path, dataset)
    write_json("data/registry/sources.json", [s.model_dump(mode="json") for s in sources])
    write_json("data/registry/acquisitions.json", [a.model_dump(mode="json") for a in acquisitions])
    write_json("data/registry/collection_report.json", {"generated_at": utcnow().isoformat(), "sources": report, "races_with_verified_roster_and_geography": sum(r.roster_verified and r.geography_verified for r in races), "metadata_races": len(races), "selected_races": sum(r.selected for r in races), "observations": len(observations), "target_cohort": {"maximum_competitive_races": 30}, "cohort_status": "partial_cohort_not_30_races"})
    return dataset


def pdf_text(body: bytes) -> str:
    result = subprocess.run(["pdftotext", "-layout", "-", "-"], input=body, capture_output=True, check=True, timeout=45)
    return result.stdout.decode("utf-8")


def parse_texas_roster(ballot_pdf: bytes, writein_pdf: bytes) -> list[Candidate]:
    return parse_texas_roster_text(pdf_text(ballot_pdf), pdf_text(writein_pdf))


def parse_texas_roster_text(ballot: str, writeins: str) -> list[Candidate]:
    if "2026 NOVEMBER GENERAL ELECTION" not in ballot or "November 3, 2026" not in writeins:
        raise ValueError("Texas certification election mismatch")
    blocks = re.findall(r"U\. S\. SENATOR\s*\n(.*?)(?=U\. S\. REPRESENTATIVE|GOVERNOR)", ballot, re.S)
    if not blocks:
        raise ValueError("Texas Senate block missing")
    found = set()
    for block in blocks:
        found.update((name.strip().title(), party) for name, party in re.findall(r"^\s*([A-Z][A-Z .'-]+?)\s{2,}(REP|DEM|LIB|GRE|IND)\s*$", block, re.M))
    found.update((name.strip(), "WRITE-IN") for name in re.findall(r"^U\.S\. Senator\s+([^\n]+)", writeins, re.M))
    if len(found) < 3:
        raise ValueError("Incomplete Texas roster parse")
    return sorted([Candidate(id="tx-sen-2026-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), name=name, party=party) for name, party in found], key=lambda c: c.id)


def parse_marist_tx(body: bytes, candidates: list[Candidate]) -> dict:
    text = text_content(body)
    match = re.search(r"Talarico \((\d+)%\) and Paxton \((\d+)%\) among likely voters", text)
    if not match or "October 8th through October 11th, 2026" not in text or "October 14, 2026" not in text:
        raise ValueError("Marist Texas poll changed; audit required")
    named = {"James Talarico": int(match.group(1)), "Ken Paxton": int(match.group(2))}
    shares = {c.id: named[c.name] for c in candidates if c.name in named}
    if len(shares) != 2:
        raise ValueError("Marist names not in official roster")
    return {"pollster": "Marist Poll", "population": "LV", "sample_size": None, "sample_size_note": "1196 registered voters; likely-voter subgroup sample not given in publisher article", "field_start": "2026-10-08", "field_end": "2026-10-11", "published_date": "2026-10-14", "publication_time_precision": "day", "shares": shares, "unallocated_percent": 100 - sum(shares.values()), "unallocated_note": "Residual only; article does not disaggregate undecided versus other candidates", "mode": "phone, text, online", "margin_of_error_percentage_points": 4.9}


def parse_tribune_debates(body: bytes) -> dict:
    text = text_content(body)
    checks = ["October 7, 2026", "Kayla Guo", "nominee has yet to accept any invitations", "has accepted at least four debate invitations", "Paxton’s campaign has not responded to repeated requests"]
    if not all(phrase in text for phrase in checks):
        raise ValueError("Texas Tribune article changed; manual audit required")
    return {"published_date": "2026-10-07", "publication_time_precision": "day", "as_of_date": "2026-10-07", "reporting_type": "independent local reporting", "facts": [{"subject": "Ken Paxton", "event": "The report found no accepted Senate debate invitation as of its publication; his campaign had not answered the reporter's repeated requests for comment."}, {"subject": "James Talarico", "event": "The report documented acceptance of at least four debate invitations from CNN and local television stations."}], "scope_note": "Facts reflect this dated article, not a verified current debate status. No electoral effect is inferred."}


def expansion_sources() -> list[Source]:
    specs = [
        ("keokuk-ia-ballot-2026", "https://keokukcounty.iowa.gov/news/2026_general_election/7118/", "Keokuk County Auditor, Iowa", "official_roster", "2026 General Election official notice", "Keokuk County Auditor, October14,2026"),
        ("johnson-ks-ballot-2026", "https://www.jocoelection.org/candidates-elected-officials/candidates?field_election_reference_target_id=6023&field_office_jurisdiction_target_id_1=All&field_office_level_target_id_1=All", "Johnson County Election Office, Kansas", "official_roster", "November3,2026 general election candidates", "Johnson County Election Office"),
        ("marist-ia-2026-10-15", "https://maristpoll.marist.edu/polls/2026-midterm-elections-in-iowa-october-2026/", "Marist Poll", "poll", "2026 Midterm Elections in Iowa, October2026", "Marist Poll, October15,2026"),
        ("ipr-ia-debate-2026-10-08", "https://www.iowapublicradio.org/political-news/2026-10-08/u-s-senate-debate-ashley-hinson-josh-turek", "Iowa Public Radio", "local_reporting", "U.S. Senate candidates discuss Iran war, affordability and defend voting records in debate", "Natalie Krebs, Iowa Public Radio, October8,2026"),
        ("redbox-ks-2026-10-25", "https://afightworthhaving.com/polling/2026/kansas", "RedBox Research / A Fight Worth Having", "poll", "Kansas statewide poll, October2026", "RedBox Research; sponsored by A Fight Worth Having super PAC, October25,2026"),
        ("kcur-ks-debate-2026-10-21", "https://www.kcur.org/politics-elections-and-government/2026-10-21/control-of-the-senate-goes-through-kansas-marshall-and-hamilton-clash-at-last-debate", "KCUR", "local_reporting", "Marshall and Hamilton clash at last debate", "KCUR, October21,2026"),
    ]
    return [Source(id=id, url=url, publisher=publisher, kind=kind, title=title, attribution=attribution, rights_basis="Independently worded factual records and numeric extracts only; no full article, image or publisher prose licensed or exported.", storage="allowed", model_use="allowed", redistribution="allowed", notes="Official county election authority documents statewide Senate nominees; no personal contact fields exported." if kind=="official_roster" else "Retain explicit poll sponsorship and dated reporting context; no inferred causal effect.") for id,url,publisher,kind,title,attribution in specs]


def parse_iowa_roster(body: bytes) -> list[Candidate]:
    text = text_content(body)
    if "November 3, 2026" not in text or "complete listing of candidates" not in text:
        raise ValueError("Iowa official election notice changed")
    block = re.search(r"U\.S\. Senator: (.*?) U\.S\. Representative", text)
    if not block:
        raise ValueError("Iowa Senate block missing")
    rows = re.findall(r"([A-Za-z .'-]+) \((DEM|REP|LIB|GRE|IND)\)", block.group(1))
    if len(rows) != 3:
        raise ValueError("Iowa Senate roster schema changed")
    return [Candidate(id="ia-sen-2026-"+re.sub(r"[^a-z0-9]+", "-", name.strip().lower()), name=name.strip(), party=party) for name,party in rows]


def parse_kansas_roster(body: bytes) -> list[Candidate]:
    text = text_content(body)
    if "November 3, 2026 General Election" not in text:
        raise ValueError("Kansas election context missing")
    block = re.search(r"Showing All Candidates U.S. Senate U.S. Senate (.*?) U.S. Representative", text)
    if not block:
        raise ValueError("Kansas Senate section missing")
    rows = re.findall(r"([A-Z][A-Za-z .'-]+?) Incumbent: (Yes|No) .*?(Democratic|Republican|Libertarian)(?: |$)", block.group(1))
    if len(rows) != 3:
        raise ValueError("Kansas Senate roster schema changed")
    return [Candidate(id="ks-sen-2026-"+re.sub(r"[^a-z0-9]+", "-", name.strip().lower()), name=name.strip(), party={"Democratic":"DEM", "Republican":"REP", "Libertarian":"LIB"}[party], incumbent=incumbent=="Yes") for name,incumbent,party in rows]


def parse_expansion_poll(body: bytes, state: str, candidates: list[Candidate]) -> dict:
    text = text_content(body)
    if state == "IA":
        match = re.search(r"Turek \((\d+)%\) edges Hinson \((\d+)%\) among likely voters",text)
        if not match or "October 8th through October 11th, 2026" not in text or "October 15, 2026" not in text:
            raise ValueError("Marist Iowa poll changed")
        named = {"Josh Turek":int(match[1]), "Ashley Hinson":int(match[2])}
        value = {"pollster":"Marist Poll", "population":"LV", "field_start":"2026-10-08", "field_end":"2026-10-11", "published_date":"2026-10-15", "sample_size":None, "sample_size_note":"1100 is registered-voter sample; likely-voter subgroup sample not provided in article", "margin_of_error_percentage_points":6.6, "mode":"phone, text, online"}
    else:
        match = re.search(r"Full results U.S. Senate Roger Marshall \(R\) ([\d.]+)% Adam Hamilton \(D\) ([\d.]+)% Undecided ([\d.]+)% David C Graham \(L\) ([\d.]+)%",text)
        if not match or "October 20–23, 2026" not in text or "Released October 25, 2026" not in text or "1,301 likely voters" not in text:
            raise ValueError("RedBox Kansas poll changed")
        named={"Roger Marshall":float(match[1]), "Adam Hamilton":float(match[2]), "David C. Graham":float(match[4])}
        value={"pollster":"RedBox Research", "sponsor":"A Fight Worth Having super PAC (FEC C00933085)", "sponsor_note":"Poll conducted by sponsor's own polling unit; not independent nonpartisan sponsorship", "population":"LV", "field_start":"2026-10-20", "field_end":"2026-10-23", "published_date":"2026-10-25", "sample_size":1301, "margin_of_error_percentage_points":3.2, "mode":"text invitation to self-administered web survey", "undecided_percent":float(match[3]), "other_percent":1.3, "prefer_not_answer_percent":1.0, "did_not_vote_in_race_percent":0.4}
    value["shares"]={c.id:named[c.name] for c in candidates if c.name in named}
    if len(value["shares"])!=len(named):
        raise ValueError("Poll candidates do not match official roster")
    value["publication_time_precision"]="day"
    if state=="IA":
        value["unallocated_percent"]=100-sum(named.values())
        value["unallocated_note"]="Residual; no invented split among other candidate and undecided"
    return value


def parse_expansion_reporting(body: bytes, state: str) -> dict:
    text=text_content(body)
    if state=="IA":
        checks=["October 8, 2026", "hour-long debate on Iowa PBS", "Libertarian Thomas Laehn is also on the ballot, but he was not part of the debate", "return to diplomacy", "not to support a Democratic-backed resolution"]
        facts=[{"subject":"Ashley Hinson", "event":"At the October7 Iowa PBS debate, she defended opposing a resolution limiting the president's powers in Iran."}, {"subject":"Josh Turek", "event":"At the same debate, he advocated ending the war and returning to diplomacy."}, {"subject":"Thomas Laehn", "event":"The report identified him as a ballot candidate who did not participate in this debate."}]
        day="2026-10-08"
    else:
        checks=["October 21, 2026", "final scheduled debate", "Marshall promised to continue President Donald Trump", "Hamilton says the tariffs are too broad"]
        facts=[{"subject":"Roger Marshall", "event":"At the October21 debate, he supported continuing President Trump's agenda and defended tariffs as helping bring jobs to the US."}, {"subject":"Adam Hamilton", "event":"At the same debate, he criticized broad tariffs and associated uncertainty for businesses."}]
        day="2026-10-21"
    if not all(c in text for c in checks):
        raise ValueError("Independent reporting source changed; audit required")
    return {"published_date":day, "publication_time_precision":"day", "as_of_date":day, "reporting_type":"independent local reporting", "facts":facts, "scope_note":"Dated reported positions, not endorsements, verified policy effects or representative voter opinion."}


def expand_records(races: list, observations: list, bodies: dict, report: list) -> None:
    configs=[("IA","keokuk-ia-ballot-2026",parse_iowa_roster,"marist-ia-2026-10-15","ipr-ia-debate-2026-10-08","19|IA|Iowa|"), ("KS","johnson-ks-ballot-2026",parse_kansas_roster,"redbox-ks-2026-10-25","kcur-ks-debate-2026-10-21","20|KS|Kansas|")]
    for state, roster_id, parser, poll_id, news_id, census_row in configs:
        if roster_id not in bodies or "census-state-codes" not in bodies:
            continue
        try:
            race=next((r for r in races if r.id==f"{state}-SEN-2026"),None)
            if not race:
                continue
            candidates=parser(bodies[roster_id][0])
            race.candidates=candidates
            race.roster_verified=True
            race.geography_verified=census_row in bodies["census-state-codes"][0].decode()
            race.boundary_version="Census state reference; statewide Senate contest verified by official county election notice"
            race.source_ids += [roster_id,"census-state-codes"]
            race.selected=bool(race.geography_verified and race.rating=="Toss-up")
            race.selection_reason="Verified official statewide Senate ballot nominees, Census state geography and primary Toss-up rating; partial pilot cohort. Unlisted write-in winners resolve through OTHER_WINNER."
            for source_id, kind in [(poll_id,"poll"),(news_id,"local_reporting")]:
                if source_id not in bodies:
                    continue
                body,acq=bodies[source_id]
                value=parse_expansion_poll(body,state,candidates) if kind=="poll" else parse_expansion_reporting(body,state)
                observations.append(Observation(id="obs-"+source_id, source_id=source_id, acquisition_id=acq.id, race_id=race.id, kind=kind,value=value,locator="Publisher Senate toplines and methodology" if kind=="poll" else "Dated debate reporting, candidate positions and participation paragraphs",available_at=acq.retrieved_at,retrieved_at=acq.retrieved_at,content_sha256=digest(value),geography=state,geography_scope="state"))
        except ValueError as exc:
            report.append({"source_id":"derived-"+state.lower(), "status":"parse_failed", "error":str(exc)})


def parse_fec_senate_2020(text: str) -> dict[str,dict]:
    """Use the final GENERAL column, never a primary/runoff column; reconcile total."""
    configs={
        "IA":("IOWA", "KANSAS", [("Ernst, Joni","REP"),("Greenfield, Theresa","DEM"),("Stewart, Rick","LIB"),("Herzog, Suzanne","NPY"),("Scattered","WRITE-IN")]),
        "KS":("KANSAS", "KENTUCKY", [("Marshall, Roger","REP"),("Bollier, Barbara","DEM"),("Buckley, Jason","LIB")]),
        "TX":("TEXAS", "VIRGINIA", [("Cornyn, John","REP"),('Hegar, Mary "MJ"',"DEM"),("McKennon, Kerry Douglas","LIB"),("Collins, David B.","GRE"),("Turullols-Bonilla, Ricardo","WRITE-IN")]),
    }
    result={}
    for state,(heading,next_heading,names) in configs.items():
        start=re.search(r"^\s*"+heading+r"\s+[^\n]*November 3rd\s*$",text,re.M)
        if not start:
            raise ValueError("FEC Senate general election heading missing: "+state)
        remaining=text[start.end():]
        end=re.search(r"^\s*"+next_heading+r"\s+[^\n]*November 3rd",remaining,re.M)
        if not end:
            raise ValueError("FEC Senate section boundary missing")
        block=remaining[:end.start()]
        rows=[]
        for name,party in names:
            # General totals are right-aligned beyond column85; primary scattered rows are excluded.
            matches=[line for line in block.splitlines() if re.match(r"^\s*(?:\(I\)\s*)?"+re.escape(name)+r"\s+",line) and len(line)>85]
            if len(matches)!=1:
                raise ValueError("FEC general candidate row ambiguous: "+name)
            match=re.search(r"([\d,]+)\s+([\d.]+)%\s*$",matches[0])
            if not match or match.start()<80:
                raise ValueError("FEC column alignment changed")
            rows.append({"name":name,"party":party,"votes":int(match[1].replace(',','')),"reported_vote_share_percent":float(match[2])})
        totals=re.findall(r"Total State Votes:[^\n]*?([\d,]+)\s*$",block,re.M)
        if len(totals)!=1:
            raise ValueError("FEC general total ambiguous")
        total=int(totals[0].replace(',',''))
        if sum(row['votes'] for row in rows)!=total:
            raise ValueError("FEC candidate votes do not reconcile with general-election total")
        result[state]={"measure":"previous_same_seat_senate_general_election", "election_date":"2020-11-03", "election_cycle":2020, "publication_month":"2022-10", "publication_time_precision":"month", "office":"senate", "state":state, "candidates":rows,"total_votes":total,"comparability_note":"Same statewide class2 Senate seat; historical2020 candidates and presidential-year turnout differ from2026. These votes are context, not a2026 prediction or certified2026 outcome."}
    return result
