"""Explicit acquisition, immutable snapshotting and offline-first experiments."""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated
import re

import typer
from dotenv import load_dotenv

from .models import Dataset, Snapshot, Inference, Outcome, Race, Source, Observation, Acquisition, read_json, write_json, utcnow, digest

app = typer.Typer(no_args_is_help=True, help='What Changed Its Mind? Inspectable election experiments.')

def dataset(path: Path) -> Dataset:
    return Dataset.model_validate(read_json(path))

def snapshot_file(path: Path) -> Snapshot:
    from .experiment import validate_snapshot
    s = Snapshot.model_validate(read_json(path)); validate_snapshot(s); return s

def inference_file(path: Path | None) -> list[Inference]:
    if not path: return []
    return [Inference.model_validate(i) for i in read_json(path)]

@app.command()
def validate(data: Path = Path('data/processed/dataset.json')):
    """Validate schema, source links, candidate IDs and provenance offline."""
    from .export import validate_dataset
    d = dataset(data); errors = validate_dataset(d)
    if errors:
        for e in errors: typer.echo(e, err=True)
        raise typer.Exit(1)
    typer.echo(f'Valid: {len(d.races)} races, {len(d.sources)} sources, {len(d.observations)} observations')

@app.command()
def fetch(output: Path = Path('data/processed/dataset.json'), source: str | None = None):
    """Acquire registered sources; secrets and raw bodies never enter the export."""
    from .collection import collect, source_records, secure_fetch
    if source:
        from .models import digest
        import hashlib
        s = next((s for s in source_records() if s.id == source), None)
        if not s: raise typer.BadParameter('Unknown registered source ID')
        fetched = secure_fetch(s.url)
        sha = hashlib.sha256(fetched.body).hexdigest()
        path = Path('data/raw')/sha; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(fetched.body)
        acq = Acquisition(id=f'acq-{s.id}-{sha[:12]}',source_id=s.id,retrieved_at=utcnow(),raw_sha256=sha,media_type=fetched.media_type,http_status=fetched.status,final_url=fetched.final_url)
        write_json(Path('data/working/acquisitions')/(acq.id+'.json'),acq,immutable=True)
        typer.echo(f'Acquired {source}; SHA256 {sha}; run full fetch to integrate supported parsers.')
        return
    d = collect(output_path=output)
    typer.echo(f'Collected {len(d.races)} races / {len(d.observations)} observations. See collection report for unavailable sources.')

@app.command()
def normalize(data: Path = Path('data/processed/dataset.json'), output: Path = Path('data/processed/normalized.json')):
    """Validate and serialize canonical records; collection adapters parse raw inputs."""
    from .export import validate_dataset
    d = dataset(data); errors = validate_dataset(d)
    if errors: raise typer.BadParameter('; '.join(errors))
    write_json(output, d); typer.echo(str(output))

def read_cohort(path: Path) -> dict:
    """Validate the immutable cohort receipt before using its frozen identities."""
    record=read_json(path)
    if not isinstance(record,dict) or record.get('content_hash') != digest({k:v for k,v in record.items() if k!='content_hash'}):
        raise ValueError('Cohort manifest hash mismatch')
    if record.get('protocol_version')!='1.0.0':
        raise ValueError('Cohort protocol version does not match current protocol')
    ids=record.get('race_ids',[])
    races=[Race.model_validate(r) for r in record.get('original_races',[])]
    if not ids or len(ids)>30 or len(ids)!=len(set(ids)) or ids!=[r.id for r in races]:
        raise ValueError('Invalid frozen cohort identities')
    if not record.get('initial_snapshot_hash'):
        raise ValueError('Cohort is missing initial snapshot provenance')
    return record

@app.command(name='snapshot')
def freeze(data: Path = Path('data/processed/dataset.json'), snapshot_id: str = 'initial', cutoff: str | None = None, output: Path | None = None, limit: int = 30, cohort: Path = Path('experiments/cohort.json')):
    """Freeze evidence while preserving the immutable initial cohort on later runs."""
    from .experiment import freeze_snapshot
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',snapshot_id):
        raise typer.BadParameter('Snapshot ID must be a simple filename-safe identifier')
    target = output or Path(f'results/snapshots/{snapshot_id}.json')
    if target.exists():
        raise typer.BadParameter('Snapshot already exists; immutable snapshots cannot be replaced')
    when = datetime.fromisoformat(cutoff.replace('Z','+00:00')) if cutoff else utcnow()
    current=dataset(data)
    registered=None
    if cohort.exists():
        try: registered=read_cohort(cohort)
        except ValueError as exc: raise typer.BadParameter(str(exc)) from exc
        current_ids={r.id for r in current.races}
        for original in registered['original_races']:
            if original['id'] not in current_ids:
                previous=Race.model_validate(original)
                current.races.append(previous.model_copy(update={'roster_verified':False,'geography_verified':False,'selected':True,'selection_reason':'Frozen race absent from current dataset; all forecasts unavailable'}))
    is_final=when.isoformat()=='2026-11-02T23:00:00+00:00'
    if is_final and registered is None:
        raise typer.BadParameter('Final snapshot requires an existing initial cohort manifest')
    try:
        snap = freeze_snapshot(current,snapshot_id,when,limit=limit,cohort_ids=registered['race_ids'] if registered else None)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    write_json(target,snap,immutable=True)
    if registered is None and snap.races:
        receipt={'protocol_version':snap.protocol_version,'initial_snapshot_id':snap.id,'initial_snapshot_hash':snap.content_hash,'initial_cutoff':snap.cutoff.isoformat(),'race_ids':[r.id for r in snap.races],'original_races':[r.model_dump(mode='json') for r in snap.races]}
        receipt['content_hash']=digest(receipt)
        write_json(cohort,receipt,immutable=True)
        typer.echo(f'Registered immutable cohort: {cohort}')
    elif registered is None:
        typer.echo('Collecting: no eligible races. Empty snapshot saved; no empty cohort registered.')
    else:
        typer.echo(f'Preserved {len(registered["race_ids"])} initial cohort IDs; unavailable races were not replaced.')
    typer.echo(f'{target}: {len(snap.races)} selected, {len(snap.observations)} eligible observations; cutoff {when.isoformat()}')

async def run_inference(snap, packets, live):
    from .jev import JevClient
    load_dotenv('.env.local',override=False)
    return await JevClient().run_packets(snap,packets,live=live)

@app.command()
def forecast(snapshot: Annotated[Path, typer.Option()], output: Path = Path('results/forecasts/initial.json'), live: bool = False, diagnostics: Path = Path('results/diagnostics/initial.json')):
    """Preview by default; --live spends API credits on eligible, uncached packets."""
    from .experiment import build_packets, request_size
    snap = snapshot_file(snapshot); packets = build_packets(snap)
    typer.echo(f'{len(packets)} slots; {sum(not p.get("error") for p in packets)} eligible; {sum(request_size(p["request"]) for p in packets)} total UTF-8 budget bytes (not token count).')
    if not live:
        typer.echo('Preview only. No API calls or stored forecast results. Add --live to execute.'); return
    if output.exists(): raise typer.BadParameter('Output already exists; replay it or choose a new run filename')
    from .jev import diagnostic_packets, request_hash
    from .export import _validate_receipt
    if not diagnostics.exists(): raise typer.BadParameter('Archive diagnostics first, or pass --diagnostics with their stored path')
    probes={p['race_id']:p for p in diagnostic_packets()}
    receipts=inference_file(diagnostics)
    if len(receipts)!=len(probes) or {i.race_id for i in receipts}!=set(probes):
        raise typer.BadParameter('Complete diagnostic archive required before live forecasts')
    for receipt in receipts:
        _validate_receipt(receipt,probes[receipt.race_id])
        if receipt.completed_at>utcnow(): raise typer.BadParameter('Diagnostic timestamp is in the future')
    result = asyncio.run(run_inference(snap,packets,live))
    write_json(output,[i.model_dump(mode='json') for i in result],immutable=True)
    typer.echo(f'{output}: {sum(i.status=="ok" for i in result)} successful / {len(result)} slots')

@app.command()
def classify(snapshot: Annotated[Path, typer.Option()], output: Path = Path('results/classifications/initial.json'), live: bool = False):
    """Classify approved passages for browsing, never as fabricated forecast facts."""
    from .jev import classification_packets
    snap=snapshot_file(snapshot); packets=classification_packets(snap)
    if len(packets)>1000: raise typer.BadParameter('Classification cap exceeded')
    typer.echo(f'{len(packets)} passage requests')
    if not live: return
    if output.exists(): raise typer.BadParameter('Output already exists')
    from .jev import request_hash
    prior={i.request_hash for path in Path('results/classifications').glob('*.json') for i in inference_file(path)}
    if len(prior | {request_hash(p['request']) for p in packets})>1000:
        raise typer.BadParameter('Classification cap of 1000 unique requests across v1 exceeded')
    results=asyncio.run(run_inference(snap,packets,True))
    write_json(output,[i.model_dump(mode='json') for i in results],immutable=True)

@app.command()
def diagnostics(output: Path = Path('results/diagnostics/initial.json'), live: bool = False):
    """Known-process probes; these do not calibrate election probabilities."""
    from .jev import diagnostic_packets
    from .experiment import freeze_snapshot
    now=utcnow(); snap=freeze_snapshot(Dataset(), 'diagnostics', now,now=now)
    packets=diagnostic_packets(); typer.echo(f'{len(packets)} known-process probes')
    if not live: return
    if output.exists(): raise typer.BadParameter('Output already exists')
    results=asyncio.run(run_inference(snap,packets,True))
    write_json(output,[i.model_dump(mode='json') for i in results],immutable=True)
    typer.echo(f'{sum(i.status=="ok" for i in results)} successful; inspect the recorded distributions before interpretation.')

@app.command()
def evaluate(snapshot: Annotated[Path, typer.Option()], inferences: Annotated[Path, typer.Option()], outcomes: Annotated[Path, typer.Option()], output: Path = Path('results/evaluation/initial.json')):
    """Score only certified outcomes; unresolved races remain pending."""
    from .evaluation import evaluate as score
    snap=snapshot_file(snapshot)
    result=score(snap,inference_file(inferences),[Outcome.model_validate(o) for o in read_json(outcomes)])
    result['primary']=snap.cutoff.isoformat()=='2026-11-02T23:00:00+00:00'
    write_json(output,result,immutable=True); typer.echo(str(output))

@app.command(name='export')
def export_public(data: Path = Path('data/processed/dataset.json'), snapshot: Path | None = None, inferences: Path | None = None, diagnostics: Path | None = None, outcomes: Path | None = None, evaluation: Path | None = None, output: Path = Path('apps/web/public/data/experiment.json')):
    """Create the allowlisted public bundle; synthetic fixtures are rejected."""
    from .export import public_bundle,export_bundle
    bundle=public_bundle(dataset(data),snapshot=snapshot_file(snapshot) if snapshot else None,inferences=inference_file(inferences),diagnostics=inference_file(diagnostics),outcomes=[Outcome.model_validate(o) for o in read_json(outcomes)] if outcomes else [],evaluation=read_json(evaluation) if evaluation else None)
    export_bundle(bundle,output); typer.echo(f'{output}: {bundle["status"]}; {bundle["stats"]["forecasts"]} recorded forecasts')

@app.command()
def schemas(output: Path = Path('docs/schemas')):
    """Generate contributor-facing JSON Schemas from the authoritative models."""
    for model in [Race,Source,Acquisition,Observation,Snapshot,Inference,Outcome,Dataset]:
        write_json(output/f'{model.__name__}.schema.json',model.model_json_schema())
    typer.echo(str(output))

if __name__ == '__main__': app()
