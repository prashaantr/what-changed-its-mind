from datetime import datetime,timezone
from typer.testing import CliRunner
from jev_elections.cli import app,read_cohort
from jev_elections.models import write_json,read_json,Snapshot
from jev_elections.experiment import build_packets
from test_experiment import dataset,NOW

runner=CliRunner()

def setup(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('jev_elections.cli.utcnow',lambda:NOW)
    monkeypatch.setattr('jev_elections.experiment.utcnow',lambda:NOW)
    data=dataset(); write_json('dataset.json',data)
    return data

def test_initial_registers_immutable_cohort_and_missing_race_preserved(tmp_path,monkeypatch):
    data=setup(tmp_path,monkeypatch)
    args=['snapshot','--data','dataset.json','--snapshot-id','first']
    result=runner.invoke(app,args)
    assert result.exit_code==0,result.output
    original=read_cohort(tmp_path/'experiments/cohort.json')
    assert original['race_ids']==['ZZ-01']
    receipt=(tmp_path/'experiments/cohort.json').read_bytes()
    new=data.races[0].model_copy(update={'id':'ZZ-02'})
    data.races=[new]; data.observations=[]
    write_json('dataset.json',data)
    final=datetime(2026,11,2,23,tzinfo=timezone.utc)
    monkeypatch.setattr('jev_elections.experiment.utcnow',lambda:final)
    result=runner.invoke(app,['snapshot','--data','dataset.json','--snapshot-id','final','--cutoff','2026-11-02T23:00:00Z'])
    assert result.exit_code==0,result.output
    snap=Snapshot.model_validate(read_json('results/snapshots/final.json'))
    assert [r.id for r in snap.races]==['ZZ-01']
    assert snap.races[0].candidates==dataset().races[0].candidates
    assert all(p['error'] for p in build_packets(snap))
    assert (tmp_path/'experiments/cohort.json').read_bytes()==receipt
    assert runner.invoke(app,args).exit_code!=0

def test_final_requires_cohort_and_corruption_rejected(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    result=runner.invoke(app,['snapshot','--data','dataset.json','--snapshot-id','final','--cutoff','2026-11-02T23:00:00Z'])
    assert result.exit_code!=0 and 'existing initial cohort' in result.output
    assert runner.invoke(app,['snapshot','--data','dataset.json']).exit_code==0
    cohort=read_json('experiments/cohort.json'); cohort['race_ids']=['ZZ-99']
    write_json('experiments/cohort.json',cohort)
    result=runner.invoke(app,['snapshot','--data','dataset.json','--snapshot-id','next'])
    assert result.exit_code!=0 and 'hash mismatch' in result.output
    assert not (tmp_path/'results/snapshots/next.json').exists()

def test_empty_collecting_does_not_lock_empty_cohort(tmp_path,monkeypatch):
    data=setup(tmp_path,monkeypatch); data.races[0].roster_verified=False
    write_json('dataset.json',data)
    result=runner.invoke(app,['snapshot','--data','dataset.json'])
    assert result.exit_code==0 and 'no empty cohort' in result.output
    assert not (tmp_path/'experiments/cohort.json').exists()
