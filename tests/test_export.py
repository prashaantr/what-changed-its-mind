import pytest
from jev_elections.export import assert_public_safe, public_bundle
from jev_elections.models import Dataset, Source

def test_no_fixture_or_secret_publishing():
    with pytest.raises(ValueError,match='Synthetic'):
        public_bundle(Dataset(synthetic=True))
    for payload in [{'api_key':'secret'},'/Users/private/secret','version https://git-lfs.github.com/spec/v1','apikey_'+'a'*50]:
        with pytest.raises(ValueError): assert_public_safe(payload)

def test_missing_data_is_not_filled_with_predictions():
    bundle=public_bundle(Dataset())
    assert bundle['status']=='collecting'
    assert bundle['stats']['forecasts']==0 and bundle['races']==[]

def test_bad_source_url_rejected():
    source=Source(id='evil',url='javascript:alert(1)',title='x',kind='x',publisher='x',attribution='x',rights_basis='unknown')
    with pytest.raises(ValueError,match='HTTPS'): public_bundle(Dataset(sources=[source]))


def release_case():
    """In-memory test-only records exercise the production gates; never written."""
    from test_experiment import dataset, NOW
    from jev_elections.experiment import freeze_snapshot, build_packets, MODEL
    from jev_elections.models import Inference
    from jev_elections.jev import request_hash
    data=dataset()
    data.synthetic=False
    for row in [*data.races,*data.sources,*data.observations]: row.synthetic=False
    snapshot=freeze_snapshot(data,'test-release',NOW,now=NOW)
    packet=next(p for p in build_packets(snapshot) if p['arm']=='B' and p['ordering']=='canonical')
    probabilities={'a':.6,'b':.3,'OTHER_WINNER':.1}
    response={'model':MODEL,'answers':{'winner':{'type':'choice','choice':'a','probabilities':probabilities}}}
    inference=Inference(id='test-inference',snapshot_id=snapshot.id,race_id=packet['race_id'],arm='B',request_hash=request_hash(packet['request']),started_at=NOW,completed_at=NOW,status='ok',requested_model=MODEL,returned_model=MODEL,request=packet['request'],response=response,probabilities=probabilities,selected='a',observation_ids=packet['observation_ids'],omitted_observation_ids=packet['omitted_observation_ids'])
    return data,snapshot,inference

def test_valid_release_has_inspectable_acquisition_and_receipt_hashes():
    from jev_elections.models import digest
    data,snapshot,inference=release_case()
    bundle=public_bundle(data,snapshot=snapshot,inferences=[inference])
    assert bundle['stats']['forecasts']==1
    assert bundle['acquisitions'][0]['rawHash']=='a'*64
    row=bundle['races'][0]['observations'][0]
    assert row['acquisitionId']=='acq' and row['contentHash'] and row['retrievedAt']
    assert bundle['races'][0]['forecasts'][0]['responseHash']==digest(inference.response)

@pytest.mark.parametrize('change,match',[
    (lambda i:setattr(i,'request_hash','f'*64),'request hash'),
    (lambda i:setattr(i,'probabilities',{'a':.8,'b':.1,'OTHER_WINNER':.1}),'Displayed'),
    (lambda i:setattr(i,'selected','b'),'Displayed'),
    (lambda i:setattr(i,'observation_ids',[]),'linkage'),
    (lambda i:setattr(i,'race_id','not-in-snapshot'),'unknown race'),
    (lambda i:setattr(i,'status','error'),'Failed inference'),
])
def test_release_rejects_tampered_receipt(change,match):
    data,snapshot,inference=release_case(); change(inference)
    with pytest.raises(ValueError,match=match): public_bundle(data,snapshot=snapshot,inferences=[inference])

def test_release_rejects_request_changed_with_new_hash():
    from jev_elections.jev import request_hash
    data,snapshot,inference=release_case()
    inference.request['questions']['winner']['instructions']='A different experiment'
    inference.request_hash=request_hash(inference.request)
    with pytest.raises(ValueError,match='frozen protocol'): public_bundle(data,snapshot=snapshot,inferences=[inference])

def test_release_rejects_current_record_that_diverged_from_frozen_record():
    data,snapshot,inference=release_case()
    # Pydantic preserves object references; replace, do not mutate the snapshot too.
    data.observations[0]=data.observations[0].model_copy(update={'value':{'changed':True}})
    with pytest.raises(ValueError,match='Frozen observation'): public_bundle(data,snapshot=snapshot,inferences=[inference])

def test_release_rechecks_temporal_validity_even_with_recomputed_snapshot_hash():
    from datetime import timedelta
    from jev_elections.experiment import snapshot_hash
    data,snapshot,inference=release_case()
    snapshot.observations[0].available_at=snapshot.cutoff+timedelta(days=1)
    snapshot.content_hash=snapshot_hash(snapshot)
    with pytest.raises(ValueError,match='temporal cutoff'): public_bundle(data,snapshot=snapshot,inferences=[inference])

def test_release_rejects_duplicate_slots_and_hash_modified_snapshot():
    data,snapshot,inference=release_case()
    with pytest.raises(ValueError,match='Duplicate inference slot'): public_bundle(data,snapshot=snapshot,inferences=[inference,inference])
    snapshot.content_hash='f'*64
    with pytest.raises(ValueError,match='Snapshot hash'): public_bundle(data,snapshot=snapshot,inferences=[inference])

def test_export_keeps_first_snapshot_view_while_current_evaluation_can_advance(tmp_path):
    from jev_elections.export import export_bundle
    from jev_elections.models import read_json
    data,snapshot,inference=release_case()
    bundle=public_bundle(data,snapshot=snapshot,inferences=[inference])
    export_bundle(bundle,tmp_path/'experiment.json')
    first=(tmp_path/'snapshots/test-release.json').read_bytes()
    bundle['evaluation']={'pending_count':1}
    export_bundle(bundle,tmp_path/'experiment.json')
    assert (tmp_path/'snapshots/test-release.json').read_bytes()==first
    assert read_json(tmp_path/'experiment.json')['evaluation']=={'pending_count':1}
    assert len(read_json(tmp_path/'snapshots.json')['snapshots'])==1
