import asyncio
import httpx
import pytest
from test_experiment import snapshot
from jev_elections.experiment import build_packets
from jev_elections.jev import JevClient, validate_response, request_hash, MODEL

def body(request):
    options=request['questions']['winner']['criteria']
    return {'model':MODEL,'answers':{'winner':{'type':'choice','choice':next(iter(options)),'probabilities':{k:1/len(options) for k in options}}},'usage':{'input_tokens':123}}

def test_default_dry_and_missing_key(tmp_path,monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY',raising=False)
    s=snapshot(); packets=build_packets(s)[:1]
    c=JevClient(cache_dir=tmp_path)
    result=asyncio.run(c.run_packets(s,packets))
    assert result[0].status=='unavailable' and result[0].attempts==0
    with pytest.raises(ValueError,match='TYPESAFE_API_KEY'): asyncio.run(c.run_packets(s,packets,live=True))

def test_live_mock_cache_and_retry(tmp_path):
    s=snapshot(); packet=build_packets(s)[0]; calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(429 if len(calls)==1 else 200,json={} if len(calls)==1 else body(packet['request']))
    c=JevClient('fake',tmp_path,httpx.MockTransport(handler))
    result=asyncio.run(c.run_packets(s,[packet],live=True))[0]
    assert result.status=='ok' and result.attempts==2
    cached=asyncio.run(c.run_packets(s,[packet]))[0]
    assert cached.reused_from==result.id and cached.started_at==result.started_at
    assert len(calls)==2

def test_invalid_and_order_hash():
    packets=[p for p in build_packets(snapshot()) if p['arm']=='B']
    assert len({request_hash(p['request']) for p in packets})==3
    response=body(packets[0]['request']); response['answers']['winner']['probabilities']['a']=float('nan')
    with pytest.raises(ValueError,match='probability'): validate_response(packets[0]['request'],response)

def test_diagnostics_and_caps(tmp_path):
    from jev_elections.jev import diagnostic_packets
    assert len(diagnostic_packets())==8
    c=JevClient(cache_dir=tmp_path)
    s=snapshot(); packet=build_packets(s)[0]
    with pytest.raises(ValueError,match='cap'): asyncio.run(c.run_packets(s,[packet]*271))

def test_noul_and_diagnostic_invalid_floats():
    from jev_elections.jev import diagnostic_packets
    packet=diagnostic_packets()[0]; response=body(packet['request'])
    response['answers']['winner']['probabilities']['1']=float('inf')
    with pytest.raises(ValueError,match='probability'): validate_response(packet['request'],response)
    req={'questions':{'issue':{'type':'noul'}}}
    with pytest.raises(ValueError,match='Noul'): validate_response(req,{'model':MODEL,'answers':{'issue':{'type':'noul','noul':float('nan')}}})

def test_cache_replay_uses_provider_answer_not_edited_display_fields(tmp_path):
    import json
    s=snapshot(); packet=build_packets(s)[0]
    client=JevClient('fake',tmp_path,httpx.MockTransport(lambda _:httpx.Response(200,json=body(packet['request']))))
    original=asyncio.run(client.run_packets(s,[packet],live=True))[0]
    path=tmp_path/f'{original.request_hash}.json'
    edited=json.loads(path.read_text())
    edited['selected']='invented'
    edited['probabilities']={'invented':1.0}
    path.write_text(json.dumps(edited))
    replay=asyncio.run(client.run_packets(s,[packet]))[0]
    assert replay.selected==original.selected
    assert replay.probabilities==original.probabilities

def test_invalid_provider_distribution_is_preserved_without_forecast(tmp_path):
    s=snapshot(); packet=build_packets(s)[0]
    invalid=body(packet['request'])
    invalid['answers']['winner']['probabilities']={k:0.9 for k in invalid['answers']['winner']['probabilities']}
    client=JevClient('fake',tmp_path,httpx.MockTransport(lambda _:httpx.Response(200,json=invalid)))
    result=asyncio.run(client.run_packets(s,[packet],live=True))[0]
    assert result.status=='error' and result.probabilities is None
    assert result.response==invalid and result.usage['input_tokens']==123
