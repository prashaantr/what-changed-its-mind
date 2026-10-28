"""Rights-allowlisted, credential-free public artifacts. Never export fixtures."""
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import re

from .models import Dataset, Snapshot, Inference, Outcome, digest, write_json, read_json, utcnow
from .experiment import validate_snapshot, build_packets, MODEL
from .jev import request_hash, validate_response, diagnostic_packets

FAMILIES = ('fundamental', 'poll', 'candidate_statement', 'local_reporting', 'focus_group')

def validate_dataset(data: Dataset) -> list[str]:
    errors = []
    for label, rows in [('race', data.races), ('source', data.sources), ('acquisition', data.acquisitions), ('observation', data.observations)]:
        ids = [x.id for x in rows]
        if len(ids) != len(set(ids)): errors.append(f'Duplicate {label} IDs')
    sources = {x.id:x for x in data.sources}
    races = {x.id:x for x in data.races}
    acqs = {x.id:x for x in data.acquisitions}
    for s in data.sources:
        if urlparse(s.url).scheme != 'https' or not urlparse(s.url).hostname:
            errors.append(f'{s.id}: public source URL must use HTTPS')
    for a in data.acquisitions:
        if a.source_id not in sources or not re.fullmatch('[a-f0-9]{64}', a.raw_sha256):
            errors.append(f'{a.id}: invalid acquisition source/hash')
    for o in data.observations:
        a = acqs.get(o.acquisition_id)
        r = races.get(o.race_id)
        if o.source_id not in sources or not r or not a or a.source_id != o.source_id:
            errors.append(f'{o.id}: unresolved provenance')
        if not re.fullmatch('[a-f0-9]{64}', o.content_sha256):
            errors.append(f'{o.id}: invalid observation hash')
        if r and o.candidate_id and o.candidate_id not in {c.id for c in r.candidates}:
            errors.append(f'{o.id}: unresolved candidate')
    return errors

def assert_public_safe(value, path='root'):
    if isinstance(value, dict):
        for key, v in value.items():
            if key.lower() in {'authorization','api_key','apikey','password','cookie','set-cookie','headers','raw_path'}:
                raise ValueError(f'Private field in public export: {path}.{key}')
            assert_public_safe(v, f'{path}.{key}')
    elif isinstance(value, list):
        for i, v in enumerate(value): assert_public_safe(v, f'{path}[{i}]')
    elif isinstance(value, str):
        if any(s in value for s in ['version https://git-lfs.github.com/spec/v1','/Users/','/home/','file://']):
            raise ValueError(f'Private path or LFS pointer at {path}')
        if re.search(r'(?:apikey_[a-zA-Z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+\S{12,})', value):
            raise ValueError(f'Possible credential at {path}')

def _validate_receipt(inference: Inference, packet: dict) -> None:
    """Bind display values to the exact protocol request and validated response."""
    if inference.request is None or request_hash(inference.request) != inference.request_hash:
        raise ValueError('Inference request hash mismatch')
    if request_hash(packet['request']) != inference.request_hash:
        raise ValueError('Inference request differs from frozen protocol packet')
    if inference.requested_model != MODEL:
        raise ValueError('Inference requested model differs from protocol')
    if inference.observation_ids != packet.get('observation_ids', []) or inference.omitted_observation_ids != packet.get('omitted_observation_ids', []):
        raise ValueError('Inference observation linkage differs from frozen packet')
    if inference.completed_at < inference.started_at:
        raise ValueError('Inference timestamps are reversed')
    if inference.status == 'ok':
        if packet.get('error'):
            raise ValueError('Successful inference for an ineligible evidence packet')
        answers = validate_response(inference.request, inference.response)
        answer = answers.get('winner')
        if inference.returned_model != inference.response.get('model'):
            raise ValueError('Returned model metadata differs from response')
        if answer and (inference.probabilities != answer['probabilities'] or inference.selected != answer['choice']):
            raise ValueError('Displayed forecast differs from stored response')
    elif inference.probabilities is not None or inference.selected is not None:
        raise ValueError('Failed inference must not publish forecast values')


def _validate_frozen_data(data: Dataset, snapshot: Snapshot) -> None:
    validate_snapshot(snapshot)
    if any(x.synthetic for x in [*snapshot.races, *snapshot.sources, *snapshot.observations]):
        raise ValueError('Synthetic records in production snapshot')
    for label, current, frozen in [('observation',data.observations,snapshot.observations),('acquisition',data.acquisitions,snapshot.acquisitions)]:
        current_by_id = {x.id:x for x in current}
        # Only acquisitions backing frozen observations need remain in the public registry.
        used = {o.acquisition_id for o in snapshot.observations}
        for record in frozen:
            if label == 'acquisition' and record.id not in used: continue
            if record.id not in current_by_id or current_by_id[record.id].model_dump(mode='json') != record.model_dump(mode='json'):
                raise ValueError(f'Frozen {label} modified or missing: {record.id}')
    source_ids = {o.source_id for o in snapshot.observations}
    current_sources = {x.id:x for x in data.sources}
    sources = {x.id:x for x in snapshot.sources}
    acquisitions = {x.id:x for x in snapshot.acquisitions}
    for sid in source_ids:
        if sid not in current_sources or sid not in sources or current_sources[sid] != sources[sid]:
            raise ValueError(f'Frozen source modified or missing: {sid}')
    current_races = {x.id:x for x in data.races}
    for race in snapshot.races:
        exclude = {'selected','selection_reason'}
        if race.id not in current_races or race.model_dump(exclude=exclude) != current_races[race.id].model_dump(exclude=exclude):
            raise ValueError(f'Frozen race modified or missing: {race.id}')
    for observation in snapshot.observations:
        source = sources[observation.source_id]
        acquisition = acquisitions.get(observation.acquisition_id)
        if not acquisition or acquisition.source_id != observation.source_id or acquisition.http_status != 200:
            raise ValueError('Invalid frozen acquisition linkage')
        if source.model_use != 'allowed' or source.redistribution != 'allowed':
            raise ValueError('Restricted frozen evidence')
        if any(t > snapshot.cutoff for t in [source.published_at,observation.published_at,observation.available_at,observation.retrieved_at,acquisition.retrieved_at] if t is not None):
            raise ValueError('Frozen evidence exceeds temporal cutoff')

def public_bundle(data: Dataset, *, snapshot: Snapshot | None = None,
                  inferences: list[Inference] | None = None, outcomes: list[Outcome] | None = None,
                  diagnostics: list[Inference] | None = None, evaluation: dict | None = None) -> dict:
    errors = validate_dataset(data)
    if errors: raise ValueError('; '.join(errors))
    if data.synthetic or any(x.synthetic for x in [*data.races,*data.sources,*data.observations]) or (snapshot and snapshot.synthetic):
        raise ValueError('Synthetic fixtures cannot enter production export')
    inferences, outcomes, diagnostics = inferences or [], outcomes or [], diagnostics or []
    if any(i.synthetic for i in inferences): raise ValueError('Synthetic inference in production export')
    if snapshot: _validate_frozen_data(data, snapshot)
    expected = {(p['race_id'],p['arm'],p['ordering']):p for p in build_packets(snapshot)} if snapshot else {}
    seen_slots = set()
    for inference in inferences:
        slot = (inference.race_id,inference.arm,inference.ordering)
        if not snapshot or inference.snapshot_id != snapshot.id or slot not in expected:
            raise ValueError('Inference belongs to a different snapshot or unknown race/arm/order')
        if slot in seen_slots: raise ValueError('Duplicate inference slot')
        seen_slots.add(slot)
        _validate_receipt(inference, expected[slot])
    expected_diagnostics = {p['race_id']:p for p in diagnostic_packets()}
    for inference in diagnostics:
        if inference.arm != 'diagnostic' or inference.race_id not in expected_diagnostics:
            raise ValueError('Unknown diagnostic receipt')
        _validate_receipt(inference, expected_diagnostics[inference.race_id])
    sources = {s.id:s for s in data.sources}
    visible = {o.id:o for o in data.observations if sources[o.source_id].redistribution == 'allowed'}
    selected = {r.id:r for r in snapshot.races} if snapshot else {}
    snap_ids = {o.id for o in snapshot.observations} if snapshot else set()
    out_by_race = {o.race_id:o for o in outcomes}
    race_rows = []
    for r in data.races:
        records = [o for o in visible.values() if o.race_id == r.id]
        forecasts = []
        for i in inferences:
            if i.race_id != r.id: continue
            if not snapshot or i.snapshot_id != snapshot.id:
                raise ValueError('Inference belongs to a different snapshot')
            if not set(i.observation_ids) <= (set(visible) & snap_ids):
                raise ValueError('Inference contains restricted or unfrozen observations')
            if i.request:
                state = i.request.get('state', {})
                if isinstance(state, dict):
                    for row in state.get('evidence', []):
                        if row.get('id') not in visible or row != visible[row['id']].model_dump(mode='json'):
                            raise ValueError('Request evidence differs from approved public observation')
            forecasts.append(dict(id=i.id,arm=i.arm,ordering=i.ordering,status=i.status,probabilities=i.probabilities,selected=i.selected,error=i.error,requestHash=i.request_hash,responseHash=digest(i.response) if i.response is not None else None,requestedModel=i.requested_model,returnedModel=i.returned_model,usage=i.usage,startedAt=i.started_at.isoformat(),completedAt=i.completed_at.isoformat(),request=i.request,response=i.response,observationIds=i.observation_ids,omittedObservationIds=i.omitted_observation_ids))
        counts = Counter(o.kind for o in records)
        outcome = out_by_race.get(r.id)
        actual = selected.get(r.id)
        missing = [k for k in FAMILIES if not counts[k]]
        if not r.roster_verified: missing.append('verified candidate roster')
        if not r.geography_verified: missing.append('verified election geography')
        if not r.rating: missing.append('verified competitive rating')
        race_rows.append(dict(id=r.id,name=r.name,office=r.office,state=r.state,stateFips=r.state_fips,district=r.district,rating=r.rating or 'Not verified',selected=bool(actual),selectionReason=actual.selection_reason if actual else r.selection_reason,geographyVerified=r.geography_verified,rosterVerified=r.roster_verified,candidates=[c.model_dump(include={'id','name','party','incumbent'}) for c in r.candidates],coverage={k:counts[k] for k in FAMILIES},missing=missing,observations=[dict(id=o.id,kind=o.kind,candidateId=o.candidate_id,excerpt=o.excerpt,value=o.value,sourceId=o.source_id,acquisitionId=o.acquisition_id,contentHash=o.content_sha256,retrievedAt=o.retrieved_at.isoformat(),locator=o.locator,publishedAt=o.published_at.isoformat() if o.published_at else None,availableAt=o.available_at.isoformat(),recordType=o.record_type) for o in records],forecasts=forecasts,outcome=dict(status=outcome.status,winnerId=outcome.winner_id) if outcome else None))
    successful = sum(i.status=='ok' and i.arm not in {'diagnostic','classification'} for i in inferences)
    bundle = dict(schemaVersion='1.0',title='What Changed Its Mind?',status='ready' if successful else 'collecting',generatedAt=utcnow().isoformat(),model='jev-1.14.0',snapshot=dict(id=snapshot.id,cutoff=snapshot.cutoff.isoformat()) if snapshot else None,protocol=dict(finalCutoff='2026-11-02T23:00:00Z',targetRaces=30,primaryComparison='Final snapshot: D minus B, paired multiclass Brier score'),stats=dict(races=len(race_rows),selected=len(selected),sources=len(sources),forecasts=successful,focusGroups=sum(o.kind=='focus_group' for o in visible.values())),races=race_rows,acquisitions=[dict(id=a.id,sourceId=a.source_id,retrievedAt=a.retrieved_at.isoformat(),rawHash=a.raw_sha256,mediaType=a.media_type,parserVersion=a.parser_version,httpStatus=a.http_status,finalUrl=a.final_url) for a in data.acquisitions if a.id in {o.acquisition_id for o in visible.values()}],sources=[dict(id=s.id,title=s.title,url=s.url,publisher=s.publisher,kind=s.kind,attribution=s.attribution,rightsBasis=s.rights_basis,redistribution=s.redistribution,notes=s.notes) for s in sources.values()],diagnostics=[dict(id=i.race_id,status=i.status,model=i.returned_model,request=i.request,response=i.response,probabilities=i.probabilities,error=i.error,completedAt=i.completed_at.isoformat()) for i in diagnostics],evaluation=evaluation,limitations=['Raw model estimates are experimental, not calibrated election probabilities.','The cohort is selected for competitiveness and evidence availability; it does not represent the country.','Ranges show only the tested orderings, not confidence intervals.','Coverage is incomplete. Missing sources and failed forecasts remain visible.','Focus groups are qualitative evidence, not representative samples of an electorate.','House locations are state-level unless a verified district boundary is explicitly supplied.','The initial snapshot is exploratory. The primary evaluation uses the predeclared final snapshot.'])
    assert_public_safe(bundle)
    return bundle

def export_bundle(bundle: dict, output: str | Path):
    assert_public_safe(bundle)
    write_json(output, bundle)
    write_json(Path(output).with_name('manifest.json'), {'schema_version':'1.0','generated_at':bundle['generatedAt'],'sha256':digest(bundle),'counts':bundle['stats'],'export_policy':'1.0.0','file':Path(output).name})
    # Preserve the first public view of each snapshot when the active view changes.
    # Later evaluations can update the current view without rewriting this archive.
    if bundle.get('snapshot'):
        sid=bundle['snapshot']['id']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',sid):
            raise ValueError('Unsafe snapshot archive identifier')
        archive=Path(output).parent/'snapshots'/f'{sid}.json'
        if not archive.exists(): write_json(archive,bundle,immutable=True)
        catalog_path=Path(output).parent/'snapshots.json'
        catalog=read_json(catalog_path) if catalog_path.exists() else {'snapshots':[]}
        if not any(row['id']==sid for row in catalog['snapshots']):
            catalog['snapshots'].append({'id':sid,'cutoff':bundle['snapshot']['cutoff'],'url':f'data/snapshots/{sid}.json'})
            write_json(catalog_path,catalog)
