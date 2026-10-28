from datetime import datetime, timezone, timedelta
import pytest
from jev_elections.models import Dataset, Race, Candidate, Source, Acquisition, Observation
from jev_elections.experiment import freeze_snapshot, build_packets, validate_snapshot

NOW=datetime(2026,10,28,12,tzinfo=timezone.utc)

def dataset():
    source=Source(id='s',url='https://example.org',publisher='Fixture',kind='fixture',title='Synthetic',attribution='Fixture',rights_basis='Created fixture',storage='allowed',model_use='allowed',redistribution='allowed',published_at=NOW,synthetic=True)
    race=Race(id='ZZ-01',name='Fictional',office='house',state='ZZ',state_fips='99',district='01',boundary_version='fixture',geography_verified=True,roster_verified=True,candidates=[Candidate(id='a',name='Alpha',party='D'),Candidate(id='b',name='Beta',party='R')],rating='Toss-up',rating_source_id='s',source_ids=['s'],synthetic=True)
    acq=Acquisition(id='acq',source_id='s',retrieved_at=NOW,raw_sha256='a'*64,media_type='application/json',http_status=200,final_url=source.url)
    kinds=['fundamental','poll','local_reporting','candidate_statement','candidate_statement','focus_group']
    obs=[Observation(id=str(i),source_id='s',acquisition_id='acq',race_id=race.id,candidate_id='a' if i==3 else 'b' if i==4 else None,kind=k,locator=f'row {i}',published_at=NOW,available_at=NOW,retrieved_at=NOW,content_sha256=str(i)*64,geography=race.id,geography_scope='district',excerpt='Fictional source text',synthetic=True,value={'pollster':'P','population':'LV','field_end':'2026-10-27','shares':{'a':47,'b':44}} if k=='poll' else {}) for i,k in enumerate(kinds)]
    return Dataset(races=[race],sources=[source],acquisitions=[acq],observations=obs,synthetic=True)

def snapshot():
    return freeze_snapshot(dataset(),'initial',NOW,now=NOW)

def test_variants_and_hash():
    snap=snapshot(); packets=build_packets(snap)
    assert len(packets)==9
    b=[p for p in packets if p['arm']=='B']
    assert b[0]['request']['state']['evidence']==b[1]['request']['state']['evidence']
    assert b[0]['request']['state']['evidence']==list(reversed(b[2]['request']['state']['evidence']))
    assert set(b[0]['request']['questions']['winner']['criteria'])=={'a','b','OTHER_WINNER'}
    snap.coverage['tamper']=True
    with pytest.raises(ValueError,match='hash'): validate_snapshot(snap)

def test_future_unknown_rights_and_geography_excluded():
    data=dataset(); data.observations[0].available_at=NOW+timedelta(days=1)
    data.observations[1].geography_scope='national'
    snap=freeze_snapshot(data,'initial',NOW,now=NOW)
    assert len(snap.races)==1
    assert len(snap.exclusions)==2
    b=next(p for p in build_packets(snap) if p['arm']=='B')
    assert b['error']=='No eligible poll evidence'
    data.sources[0].model_use='unknown'
    snap=freeze_snapshot(data,'initial',NOW,now=NOW)
    assert not snap.observations
    assert len(snap.races)==1

def test_no_backdate_no_truncation():
    with pytest.raises(ValueError,match='current'): freeze_snapshot(dataset(),'initial',NOW,now=NOW+timedelta(days=1))
    data=dataset(); data.observations[0].excerpt='x'*25000
    packets=build_packets(freeze_snapshot(data,'initial',NOW,now=NOW))
    assert all(p['error'] for p in packets)
    assert len(packets[0]['request']['state']['evidence'][0]['excerpt'])==25000

def test_forecast_excludes_expert_rating_and_selection_metadata():
    packet=build_packets(snapshot())[0]
    race=packet['request']['state']['race']
    assert 'rating' not in race and 'selection_reason' not in race and 'source_ids' not in race

def test_final_cohort_preserved_even_when_new_race_has_better_coverage():
    data=dataset(); final=datetime(2026,11,2,23,tzinfo=timezone.utc)
    original=data.races[0]
    data.races.append(original.model_copy(update={'id':'ZZ-02'}))
    original.roster_verified=False
    frozen=freeze_snapshot(data,'final',final,now=final,cohort_ids=['ZZ-01'])
    assert [r.id for r in frozen.races]==['ZZ-01']
    assert all(p['error'].startswith('Frozen race currently unavailable') for p in build_packets(frozen))
    with pytest.raises(ValueError,match='requires initial'): freeze_snapshot(data,'final',final,now=final)
    with pytest.raises(ValueError,match='Missing frozen'): freeze_snapshot(data,'final',final,now=final,cohort_ids=['ZZ-99'])

def test_old_poll_and_campaign_only_do_not_enable_arms():
    data=dataset(); data.observations[1].value['field_end']='2026-08-01'
    data.observations=[o for o in data.observations if o.kind not in {'local_reporting','focus_group'}]
    packets=build_packets(freeze_snapshot(data,'initial',NOW,now=NOW))
    canonical={p['arm']:p for p in packets if p['ordering']=='canonical'}
    assert canonical['A']['error'] is None
    assert canonical['B']['error']=='No eligible poll evidence'
    assert canonical['C']['error']=='No eligible independent qualitative evidence'
    assert canonical['D']['error'] is not None
    assert '1' in canonical['B']['omitted_observation_ids']

def test_removing_only_focus_group_still_produces_the_planned_ablation():
    data=dataset();data.observations=[o for o in data.observations if o.kind!='local_reporting']
    packets=build_packets(freeze_snapshot(data,'initial',NOW,now=NOW))
    removed=next(p for p in packets if p['arm']=='D_no_focus')
    assert removed['error'] is None
    assert all(o['kind']!='focus_group' for o in removed['request']['state']['evidence'])
