# Public bundle v1

Frontend consumes `public/data/experiment.json`, built by coordinator export.py. All fields below always exist, including empty arrays. Production initially honestly shows collection status if no live Jev run. No invented probabilities.

```ts
type Bundle = {
 schemaVersion: '1.0'; title: string; status: 'collecting'|'ready'; generatedAt: string;
 model: string; snapshot: null | {id:string; cutoff:string};
 protocol: {finalCutoff:string; targetRaces:number; primaryComparison:string};
 stats: {races:number; selected:number; sources:number; forecasts:number; focusGroups:number};
 races: Array<{
  id:string; name:string; office:'house'|'senate'; state:string; stateFips:string; district:string|null;
  rating:string; selected:boolean; selectionReason:string; geographyVerified:boolean; rosterVerified:boolean;
  candidates:Array<{id:string;name:string;party:string;incumbent:boolean|null}>;
  coverage:Record<string,number>; missing:string[];
  observations:Array<{id:string;kind:string;candidateId:string|null;excerpt:string|null;value:Record<string,unknown>;sourceId:string;locator:string;publishedAt:string|null;availableAt:string;recordType:string}>;
  forecasts:Array<{id:string;arm:string;ordering:string;status:string;probabilities:Record<string,number>|null;selected:string|null;error:string|null;requestHash:string;startedAt:string;completedAt:string;request:unknown;response:unknown;observationIds:string[];omittedObservationIds:string[]}>;
  outcome:null|{status:string;winnerId:string|null};
 }>;
 sources:Array<{id:string;title:string;url:string;publisher:string;kind:string;attribution:string;rightsBasis:string;redistribution:string;notes:string}>;
 diagnostics:Array<Record<string,unknown>>;
 evaluation:null|Record<string,unknown>;
 limitations:string[];
};
```

Map: use real self-hosted US state geography (Census-derived us-atlas permitted license). Senate regions state outlines, House races located at state level until verified district geometry exists; explicitly label that geographic precision. Never draw fictional district shapes. List all state races on click. Unsampled states neutral.

No live browser inference. All controls reveal exported stored data. If forecasts empty, show Forecast pending / No model output yet, with evidence coverage and informative method visual. Shuffle button explains pending precomputed runs rather than animating fabricated results. Synthetic development fixture is separate and prohibited from production.
