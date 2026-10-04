# Freeze receipt — cross-domain replication (MMLU medical decisions)

Frozen (UTC): `2026-09-29T14:47:54.287335+00:00`

Recorded **before any API call for this arm**. The prediction is in
`docs/preregistration_mmlu.md`; the collected data does not yet exist.

## Frozen artifacts

| SHA-256 | file |
|---|---|
| `971b123b3d5843fff78b1aefc28f66dac46afd46834181078987442da161e141` | `data/configs/config_mmlu.yaml` |
| `7575aa67690f816c08df17c7a2a6e10780a4ac7bd904e3414315d70ecd064dc6` | `data/configs/prompt_mmlu.txt` |
| `30e4284ccd4ab4e41d885e371ff402484b4a132e0101ae360b60cc21d789f6b8` | `docs/preregistration_mmlu.md` |
| `6512682a56392856016b449de0f9eb67dbbc83e0c33b3a5c5ea8d77e684fda34` | `code/src/build_mmlu_inputs.py` |
| `4c2ca4321d139c9785694fcc22fd86ee949ffdc2bcd1d00f1386973766173a03` | `data/mmlu_ground_truth.json` |
| `c870f8cf3b2053c59c9a903dbba53f720d8396874bc738b7440b783169b6f1bf` | `data/mmlu_manifest.json` |

## Input set

- items: **537** ({'professional_medicine': 272, 'clinical_knowledge': 265})
- labels: ['A', 'B', 'C', 'D'], answer key {'A': 126, 'B': 128, 'C': 145, 'D': 138}
- directory digest (`data/inputs_mmlu/`): `8bc7e76d928bc263d015941a6559154c7cffe85e9cff554c157acf8731b85ed5`
- source: cais/mmlu (MIT); subsets professional_medicine, clinical_knowledge

