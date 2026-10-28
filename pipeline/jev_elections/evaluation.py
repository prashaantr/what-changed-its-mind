"""Outcome scoring; vote shares are never treated as win probabilities."""
import math
from datetime import timedelta
from .models import Snapshot, Inference, Outcome
from .experiment import OTHER, MODEL

def uniform_baseline(candidate_ids:list[str])->dict[str,float]:
    if not candidate_ids or len(set(candidate_ids))!=len(candidate_ids):
        raise ValueError('Unique nonempty outcome options required')
    return {c:1/len(candidate_ids) for c in candidate_ids}

def multiclass_brier(probabilities:dict[str,float],winner_id:str)->float:
    if winner_id not in probabilities:
        raise ValueError('Certified winner missing from outcome options')
    if not probabilities or any(isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-6:
        raise ValueError('Invalid probability distribution')
    return sum((p-int(c==winner_id))**2 for c,p in probabilities.items())

def polling_leader(snapshot:Snapshot,race_id:str)->dict:
    """Latest eligible release per pollster within 30 days; prefer LV within a release.

    Expected value: pollster, population='LV', field_end ISO date, shares keyed
    by candidate ID. Require the same candidate coverage across retained polls.
    """
    from datetime import datetime, timezone
    latest={}
    race=next(r for r in snapshot.races if r.id==race_id)
    aliases={c.name:c.id for c in race.candidates}
    allowed={c.id for c in race.candidates}
    for o in snapshot.observations:
        if o.race_id!=race_id or o.kind!='poll': continue
        v=o.value
        if v.get('population') not in {'LV','RV','likely_voters','registered_voters'} or not v.get('pollster'): continue
        try:
            end=datetime.fromisoformat(v['field_end'].replace('Z','+00:00'))
            if end.tzinfo is None: end=end.replace(tzinfo=timezone.utc)
            raw=v.get('shares',v.get('shares_percent',{}))
            shares={aliases.get(c,c):x for c,x in raw.items()}
            if not set(shares)<=allowed: continue
            if not shares or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=100 for x in shares.values()): continue
        except (KeyError,TypeError,ValueError): continue
        if not snapshot.cutoff-timedelta(days=30)<=end<=snapshot.cutoff: continue
        key=v['pollster']; rank=(o.published_at or o.available_at,v.get('population') in {'LV','likely_voters'},end,o.id)
        if key not in latest or rank>latest[key][0]: latest[key]=(rank,o,shares)
    polls=[pair[1] for pair in latest.values()]
    if not polls: return {'status':'unavailable','reason':'No eligible LV/RV polls','poll_ids':[]}
    aligned={x[1].id:x[2] for x in latest.values()}
    common=set(aligned[polls[0].id])
    if any(set(aligned[o.id]) != common for o in polls):
        return {'status':'unavailable','reason':'Candidate shares not aligned','poll_ids':[o.id for o in polls]}
    race=next(r for r in snapshot.races if r.id==race_id)
    major={c.id for c in race.candidates if c.party.upper() in {'D','R','DEM','REP','DEMOCRATIC','REPUBLICAN'}}
    if len(common)<2 or not major<=common:
        return {'status':'unavailable','reason':'Candidate shares not aligned','poll_ids':[o.id for o in polls]}
    averages={c:sum(aligned[o.id][c] for o in polls)/len(polls) for c in sorted(common)}
    high=max(averages.values()); winners=[c for c,v in averages.items() if abs(v-high)<1e-9]
    return {'status':'ok' if len(winners)==1 else 'tie','leader':winners[0] if len(winners)==1 else None,'mean_vote_shares':averages,'poll_ids':[o.id for o in polls],'note':'Vote shares; not probabilities of winning'}

def evaluate(snapshot:Snapshot,inferences:list[Inference],outcomes:list[Outcome])->dict:
    certified={o.race_id:o for o in outcomes if o.status=='certified' and o.winner_id}
    rows=[]; paired=[]; unresolved=[]
    seen=set()
    for r in snapshot.races:
        outcome=certified.get(r.id)
        if not outcome:
            unresolved.append(r.id); continue
        options=[c.id for c in r.candidates]+[OTHER]
        winner=outcome.winner_id if outcome.winner_id in options else OTHER
        selected=[i for i in inferences if i.snapshot_id==snapshot.id and i.race_id==r.id and i.ordering=='canonical' and i.status=='ok' and i.returned_model==MODEL and i.probabilities is not None]
        scores={}
        for inf in selected:
            key=(r.id,inf.arm)
            if key in seen: raise ValueError('Duplicate primary inference; choose one frozen run')
            seen.add(key)
            if set(inf.probabilities)!=set(options): raise ValueError('Inference ballot options mismatch')
            scores[inf.arm]=multiclass_brier(inf.probabilities,winner)
        poll=polling_leader(snapshot,r.id)
        rows.append({'race_id':r.id,'winner_id':winner,'scores':scores,'uniform_brier':multiclass_brier(uniform_baseline(options),winner),'polling_leader_correct':poll.get('leader')==winner if poll.get('status')=='ok' else None})
        if 'B' in scores and 'D' in scores: paired.append({'race_id':r.id,'difference':scores['D']-scores['B']})
    means={arm:sum(row['scores'][arm] for row in rows if arm in row['scores'])/sum(arm in row['scores'] for row in rows) for arm in sorted({a for row in rows for a in row['scores']})}
    arms=['A','B','C','D','D_no_focus']
    arm_counts={arm:sum(arm in row['scores'] for row in rows) for arm in arms}
    poll_values=[row['polling_leader_correct'] for row in rows if row['polling_leader_correct'] is not None]
    summary={'resolved_count':len(rows),'pending_count':len(unresolved),'uniform_mean_brier':sum(row['uniform_brier'] for row in rows)/len(rows) if rows else None,'uniform_count':len(rows),'polling_leader_accuracy':sum(poll_values)/len(poll_values) if poll_values else None,'polling_leader_count':len(poll_values),'polling_leader_missing_count':len(rows)-len(poll_values),'arm_counts':arm_counts,'arm_missing_counts':{arm:len(rows)-count for arm,count in arm_counts.items()},'paired_missing_count':len(rows)-len(paired),'denominator_note':'Missing comparator/arm counts refer only to certified resolved races; pending outcomes are separate.'}
    return {**summary,'snapshot_id':snapshot.id,'metric':'mean unscaled multiclass Brier (0..2)','rows':rows,'arm_means':means,'paired_B_D':paired,'paired_count':len(paired),'paired_mean_difference':sum(x['difference'] for x in paired)/len(paired) if paired else None,'pending_races':unresolved,'note':'Negative D-minus-B favours qualitative evidence. Repeated snapshots are not independent outcomes.'}
