"""Offline contracts; fabricated parser fixtures never enter the production Dataset."""
import socket

import httpx
import pytest

from jev_elections.collection import parse_nc_roster, parse_ecu_poll, parse_texas_roster_text, secure_fetch, validate_url


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))])


@pytest.mark.parametrize('url', ['http://www.census.gov/', 'https://user:pass@www.census.gov/', 'https://www.census.gov:444/', 'https://localhost/', 'https://s3.amazonaws.com/other-bucket/file'])
def test_reject_unsafe_urls(url, public_dns):
    with pytest.raises(ValueError):
        validate_url(url)


def test_reject_private_dns(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='nonpublic'):
        validate_url('https://www.census.gov/')


def test_redirect_revalidated(public_dns):
    seen = []
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={'location': 'https://localhost/secret'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match='allowlisted'):
            secure_fetch('https://www.census.gov/', client=client)
    assert len(seen) == 1


def test_body_bounded(public_dns):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'12345'))) as client:
        with pytest.raises(ValueError, match='size limit'):
            secure_fetch('https://www.census.gov/', max_bytes=4, client=client)


def test_nc_deduplicates_and_filters_primary_contact_data():
    header = 'election_dt,contest_name,name_on_ballot,party_candidate,email\n'
    row = '11/03/2026,US SENATE,Fixture One,AAA,private@example.invalid\n'
    body = (header + row + row + '11/03/2026,US SENATE,Fixture Two,BBB,secret@example.invalid\n' + '03/03/2026,US SENATE,Primary Only,CCC,secret@example.invalid\n').encode()
    result = parse_nc_roster(body)
    assert [c.name for c in result] == ['Fixture One', 'Fixture Two']
    assert 'private@' not in str(result)


def test_parsers_fail_closed():
    with pytest.raises(ValueError):
        parse_ecu_poll(b'<p>changed page</p>')
    with pytest.raises(ValueError):
        parse_nc_roster(b'name,office\nTest,Senate')
    with pytest.raises(ValueError):
        parse_texas_roster_text('Different election', '')


def test_iowa_official_notice_parser():
    from jev_elections.collection import parse_iowa_roster
    body=b'<p>November 3, 2026 complete listing of candidates U.S. Senator: Fixture One (DEM), Fixture Two (REP), Fixture Three (LIB) U.S. Representative District 1</p>'
    result=parse_iowa_roster(body)
    assert [c.name for c in result] == ['Fixture One','Fixture Two','Fixture Three']
    assert [c.party for c in result] == ['DEM','REP','LIB']


def test_kansas_roster_retains_third_party_and_incumbency():
    from jev_elections.collection import parse_kansas_roster
    body=b'<p>November 3, 2026 General Election Showing All Candidates U.S. Senate U.S. Senate Fixture One Incumbent: No City: Example Democratic Fixture Two Incumbent: No City: Example Libertarian Fixture Three Incumbent: Yes City: Example Republican U.S. Representative</p>'
    result=parse_kansas_roster(body)
    assert len(result)==3
    assert result[1].party=='LIB'
    assert result[2].incumbent is True


def test_expansion_fails_closed():
    from jev_elections.collection import parse_expansion_reporting, parse_expansion_poll
    for state in ['IA','KS']:
        with pytest.raises(ValueError):
            parse_expansion_poll(b'<p>wrong page</p>',state,[])
        with pytest.raises(ValueError):
            parse_expansion_reporting(b'<p>wrong page</p>',state)


def test_cached_acquisition_keeps_time_and_hash(tmp_path, monkeypatch):
    import hashlib
    from datetime import datetime, timezone
    import jev_elections.collection as mod
    from jev_elections.models import Source, Acquisition, Dataset, write_json
    monkeypatch.chdir(tmp_path)
    source=Source(id='fixture',url='https://www.census.gov/test',publisher='Fixture',kind='geography',title='Fixture',attribution='Fixture',rights_basis='Synthetic test only',synthetic=True)
    body=b'synthetic fixture body'
    sha=hashlib.sha256(body).hexdigest()
    acq=Acquisition(id='fixture-acq',source_id='fixture',retrieved_at=datetime(2026,1,1,tzinfo=timezone.utc),raw_sha256=sha,media_type='text/plain',http_status=200,final_url=source.url)
    (tmp_path/'raw').mkdir();(tmp_path/'raw'/sha).write_bytes(body)
    write_json('fixture.json',Dataset(sources=[source],acquisitions=[acq],synthetic=True))
    monkeypatch.setattr(mod,'source_records',lambda:[source])
    def no_network(*args,**kwargs):
        raise AssertionError('cached source must not refetch')
    monkeypatch.setattr(mod,'secure_fetch',no_network)
    result=mod.collect('fixture.json','raw')
    assert result.acquisitions[0]==acq


def test_fec_general_column_and_reconciliation():
    from jev_elections.collection import parse_fec_senate_2020
    # Artificial vote counts in parser-only fixture; never a production observation.
    blocks=[]
    for state,names in [('IOWA',['Ernst, Joni','Greenfield, Theresa','Stewart, Rick','Herzog, Suzanne','Scattered']),('KANSAS',['Marshall, Roger','Bollier, Barbara','Buckley, Jason']),('KENTUCKY',[]),('TEXAS',['Cornyn, John','Hegar, Mary "MJ"','McKennon, Kerry Douglas','Collins, David B.','Turullols-Bonilla, Ricardo']),('VIRGINIA',[])]:
        blocks.append(f'  {state}    June 2nd    November 3rd\n')
        for name in names:
            blocks.append(('  '+name+'   R  900 90.0%').ljust(92)+'2 20.0%\n')
        if names:blocks.append(f'  Total State Votes: 999  {len(names)*2}\n')
    text=''.join(blocks)
    parsed=parse_fec_senate_2020(text)
    assert parsed['KS']['total_votes']==6
    assert parsed['TX']['candidates'][0]['votes']==2
    with pytest.raises(ValueError,match='reconcile'):
        parse_fec_senate_2020(text.replace('999  6','999  7'))
