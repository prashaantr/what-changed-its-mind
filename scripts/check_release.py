"""Offline production gate, run before publishing a Pages artifact."""
import json
from pathlib import Path
from jev_elections.export import assert_public_safe, public_bundle
from jev_elections.models import digest, Dataset, Snapshot, Inference, Outcome, read_json

bundle_path=Path('apps/web/public/data/experiment.json')
bundle=json.loads(bundle_path.read_text())
manifest=json.loads(bundle_path.with_name('manifest.json').read_text())
assert digest(bundle)==manifest['sha256'], 'Public manifest hash mismatch'
assert_public_safe(bundle)
release=read_json('experiments/releases/current.json')
expected=public_bundle(
 Dataset.model_validate(read_json(release['dataset'])),
 snapshot=Snapshot.model_validate(read_json(release['snapshot'])),
 inferences=[Inference.model_validate(x) for x in read_json(release['inferences'])],
 diagnostics=[Inference.model_validate(x) for x in read_json(release['diagnostics'])],
 outcomes=[Outcome.model_validate(x) for x in read_json(release['outcomes'])],
 evaluation=read_json(release['evaluation']))
assert {k:v for k,v in bundle.items() if k!='generatedAt'}=={k:v for k,v in expected.items() if k!='generatedAt'}, 'Site values differ from source receipts'
assert all(not r['id'].startswith(('ZZ','FIXTURE')) for r in bundle['races']), 'Fictional race in release'
assert len([r for r in bundle['races'] if r['selected']])<=30
for root in [Path('apps/web/public'),Path('apps/web/dist')]:
 for f in root.rglob('*'):
  if not f.is_file(): continue
  assert f.name not in {'.env','.env.local'}, 'Credential file in site'
  if f.suffix in {'.json','.html','.txt','.js','.css','.map'}:
   assert_public_safe(f.read_text())
print('Public manifest, bundle and site artifact passed release gate.')
