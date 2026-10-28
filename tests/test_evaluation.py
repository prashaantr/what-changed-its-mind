import pytest
from test_experiment import snapshot,NOW
from jev_elections.models import Outcome,Inference
from jev_elections.evaluation import evaluate,multiclass_brier,polling_leader

def test_brier():
    assert multiclass_brier({'a':1.,'b':0.},'a')==0
    assert multiclass_brier({'a':1.,'b':0.},'b')==2
    with pytest.raises(ValueError): multiclass_brier({'a':.3},'a')

def test_only_certified_and_paired():
    s=snapshot(); records=[]
    for arm,p in [('B',.4),('D',.8)]:
        records.append(Inference(id=arm,snapshot_id=s.id,race_id='ZZ-01',arm=arm,request_hash=arm,returned_model='jev-1.14.0',started_at=NOW,completed_at=NOW,status='ok',probabilities={'a':p,'b':1-p,'OTHER_WINNER':0},selected='a'))
    outcome=Outcome(race_id='ZZ-01',source_id='s',retrieved_at=NOW,status='projected',winner_id='a')
    assert evaluate(s,records,[outcome])['paired_count']==0
    outcome.status='certified'
    report=evaluate(s,records,[outcome])
    assert report['paired_count']==1 and report['paired_mean_difference']<0
    with pytest.raises(ValueError,match='Duplicate'): evaluate(s,records+records,[outcome])

def test_polling_vote_share_not_probability():
    result=polling_leader(snapshot(),'ZZ-01')
    assert result['leader']=='a'
    assert result['mean_vote_shares']['a']==47

def test_polling_unequal_candidate_sets_has_no_comparator():
    from jev_elections.models import Candidate
    s=snapshot(); s.races[0].candidates.append(Candidate(id='c',name='Third',party='I'))
    first=next(o for o in s.observations if o.kind=='poll')
    second=first.model_copy(deep=True); second.id='poll2'
    second.value['pollster']='Second'; second.value['shares']['c']=3
    s.observations.append(second)
    result=polling_leader(s,'ZZ-01')
    assert result['status']=='unavailable' and result['reason']=='Candidate shares not aligned'
    assert 'leader' not in result

def test_new_rv_beats_old_lv_but_same_release_prefers_lv():
    from datetime import timedelta
    s=snapshot(); old=next(o for o in s.observations if o.kind=='poll')
    old.published_at=NOW-timedelta(days=2)
    old.available_at=old.published_at
    new=old.model_copy(deep=True); new.id='new-rv'; new.published_at=NOW; new.available_at=NOW
    new.value['population']='RV'; new.value['shares']={'a':40,'b':50}
    s.observations.append(new)
    result=polling_leader(s,'ZZ-01')
    assert result['leader']=='b' and result['poll_ids']==['new-rv']
    lv=new.model_copy(deep=True); lv.id='same-release-lv'; lv.value['population']='LV'; lv.value['shares']={'a':49,'b':44}
    s.observations.append(lv)
    assert polling_leader(s,'ZZ-01')['poll_ids']==['same-release-lv']

def test_evaluation_summaries_leave_pending_and_missing_as_null():
    s=snapshot()
    pending=evaluate(s,[],[])
    assert pending['pending_count']==1 and pending['resolved_count']==0
    assert pending['uniform_mean_brier'] is None and pending['polling_leader_accuracy'] is None
    outcome=Outcome(race_id='ZZ-01',source_id='s',retrieved_at=NOW,status='certified',winner_id='a')
    scored=evaluate(s,[],[outcome])
    assert scored['uniform_count']==1 and scored['uniform_mean_brier']==pytest.approx(2/3)
    assert scored['polling_leader_count']==1 and scored['polling_leader_accuracy']==1
    assert scored['arm_counts']['B']==0 and scored['arm_missing_counts']['B']==1
    assert scored['paired_missing_count']==1
    s.observations=[o for o in s.observations if o.kind!='poll']
    missing=evaluate(s,[],[outcome])
    assert missing['polling_leader_accuracy'] is None and missing['polling_leader_missing_count']==1
