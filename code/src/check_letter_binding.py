#!/usr/bin/env python3
"""Gate: every number in the response letter is BOUND to the one claim it must equal.

The manuscript has had this since check_binding.py; the response letter did not, and the
difference mattered. The letter was only set-checked, so substituting 0.455 for the error-
correlation contrast 0.454 passed every gate, because 0.455 is the true value of a different
claim. With 415 claims, "this number exists somewhere in the analysis" is close to no check.

Each rule names the phrase a number follows in submission/response_to_reviewers.txt and the
single claim it must equal. The claim keys are deliberately the same ones check_binding.py uses
for the same values in the manuscript, so the letter cannot agree with the analysis while
disagreeing with the paper.

Two normalisations run before extraction, each narrow and each for a reason:
  * ISO-8601 freeze timestamps are masked. The seconds field of 2026-07-03T20:41:51.396959+00:00
    extracts as the literal 51.396959; check_freeze_timestamps.py gates those against the
    receipts instead, which is a stronger check than declaring them non-results here.
  * "54,000" becomes "54000", the same thousands-separator normalisation the manuscript gate
    applies to 54{,}000, so a correct number is not reported as a defect over punctuation.

  python code/src/check_letter_binding.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from binding_core import ISO_TIMESTAMP, check, rounds_to, words_before  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- short integers
# LIT only extracts decimals and integers of three digits or more, which is right for the bulk of
# the text but leaves a real gap: "approximately 94% of the primary agreement contrast" and "22
# were transport or schema failures" are results, and neither gate saw them. This second pass
# covers every one- and two-digit integer. Each must match a result rule or one of the declared
# structural classes; anything else is UNBOUND, so a new short number cannot slip in unnoticed.
#
# A target of the form "a/b" is the RATIO of two claims, times `scale`: the 94% retention is
# control_delta_kappa / primary_delta_kappa and exists in no single claim.
SHORT_RESULTS = [
    (r"control (?:which )?preserves approximately$", "94",
     "control_delta_kappa/primary_delta_kappa", 0, 100.0),
    (r"now reads 100 x$", "12", "revision_r3_2_clustering_date_n_clusters", 0),
    (r"or quota responses and$", "22", "capture_unsuccessful_transport_or_schema", 0),
]
# Structural: a number that is part of the letter's apparatus, not a measurement. Each class is
# gated elsewhere or is a fixed convention, and that is named so the exemption is auditable.
SHORT_STRUCTURAL = [
    (r"Reviewer #\d, Concern #\d", "concern header; the letter's own numbering"),
    (r"\b95%", "the 95% confidence level, a fixed convention"),
    (r"\[\d{1,2}\]", "bibliography number, gated by check_letter_refs.py"),
    (r"\b(?:Table|Figure) \d", "float pointer, gated by check_letter_sections.py"),
    (r"10\^-\d", "exponent of a scaled cost; the mantissa is bound with its scale"),
    (r"Index Terms to \d", "inside the reviewer's quoted comment"),
    (r"\d\s*-\s*5 words", "inside the reviewer's quoted comment"),
]
# A trailing period ends a sentence as often as it continues a decimal, so the lookahead must
# reject only a digit after the dot. With (?![\w.]) a number written "...from 11." was never
# extracted at all, and fault injection caught exactly that.
SHORT = re.compile(r"(?<![\w.$^-])(\d{1,2})(?![\w])(?!\.\d)")
CLAIMS = ROOT / "results" / "latest" / "claims.json"
LETTER = ROOT / "submission" / "response_to_reviewers.txt"

# (context pattern, literal, target, decimals[, scale]); target "!reason" is a declared non-result
L = [
    (r"original\ manuscript\ id\ access\-$", "2026", "!IEEE manuscript ID Access-2026-38801", 0),
    (r"original\ manuscript\ id\ access\-2026\-$", "38801", "!IEEE manuscript ID Access-2026-38801", 0),
    (r"protocol\ on\ a\ substantially\ different\ domain$", "537", "mmlu_overall_n_items", 0),
    (r"using\ mean\ agent\ conviction\.\ aurc\ is$", "0.553", "revision_r1_1_r3_4_selective_prediction_hom_aurc", 3),
    (r"conviction\.\ aurc\ is\ 0\.553\ for\ hom$", "0.568", "revision_r1_1_r3_4_selective_prediction_het_lite_aurc", 3),
    (r"for\ hom\ 0\.568\ for\ het\-lite\ and$", "0.554", "revision_r1_1_r3_4_selective_prediction_het_aurc", 3),
    (r"het\ the\ hom\-het\ difference\ is\ \-$", "0.001", "revision_r3_4_paired_cluster_contrasts_aurc_delta_hom_het", 3),
    (r"a\ 95\ equity\-clustered\ interval\ of\ \-$", "0.059", "revision_r3_4_paired_cluster_contrasts_aurc_ci_low", 3),
    (r"a\ 95\ equity\-clustered\ interval\ of\ \-0\.059$", "0.060", "revision_r3_4_paired_cluster_contrasts_aurc_ci_high", 3),
    (r"and\ a\ two\-way\ interval\ of\ \-$", "0.113", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_low", 3),
    (r"and\ a\ two\-way\ interval\ of\ \-0\.113$", "0.115", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_high", 3),
    (r"produces\ unanimous\ incorrect\ directional\ decisions\ at$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"equity\-clustered\ and\ two\-way\ 95\ intervals\ of$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"and\ two\-way\ 95\ intervals\ of\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"95\ intervals\ of\ 1\.42\ 2\.52\ and$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"intervals\ of\ 1\.42\ 2\.52\ and\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"have\ nearly\ identical\ mean\ member\ accuracy$", "0.951", "mmlu_capability_matched_matched_same_provider_member_accuracy", 3),
    (r"identical\ mean\ member\ accuracy\ 0\.951\ and$", "0.955", "mmlu_capability_matched_matched_cross_provider_member_accuracy", 3),
    (r"0\.955\ while\ their\ error\ correlations\ are$", "0.954", "mmlu_capability_matched_matched_same_provider_phi", 3),
    (r"their\ error\ correlations\ are\ 0\.954\ and$", "0.607", "mmlu_capability_matched_matched_cross_provider_phi", 3),
    (r"0\.954\ and\ 0\.607\ a\ difference\ of$", "0.347", "mmlu_capability_matched_matched_d_phi", 3),
    (r"a\ difference\ of\ 0\.347\ 95\ ci$", "0.207", "mmlu_capability_matched_matched_d_phi_ci_low", 3),
    (r"difference\ of\ 0\.347\ 95\ ci\ 0\.207$", "0.507", "mmlu_capability_matched_matched_d_phi_ci_high", 3),
    (r"we\ added\ a\ pre\-registered\ replication\ using$", "537", "mmlu_overall_n_items", 0),
    (r"the\ ordering\ reproduces\ agreement\ decreases\ by$", "0.072", "mmlu_overall_d_kappa", 3),
    (r"agreement\ decreases\ by\ 0\.072\ 95\ ci$", "0.040", "mmlu_overall_d_kappa_ci_low", 3),
    (r"decreases\ by\ 0\.072\ 95\ ci\ 0\.040$", "0.104", "mmlu_overall_d_kappa_ci_high", 3),
    (r"0\.040\ 0\.104\ and\ error\ correlation\ by$", "0.393", "mmlu_overall_d_phi", 3),
    (r"error\ correlation\ by\ 0\.393\ 95\ ci$", "0.325", "mmlu_overall_d_phi_ci_low", 3),
    (r"correlation\ by\ 0\.393\ 95\ ci\ 0\.325$", "0.459", "mmlu_overall_d_phi_ci_high", 3),
    (r"95\ ci\ 0\.325\ 0\.459\ compared\ with$", "0.336", "primary_delta_kappa", 3),
    (r"0\.325\ 0\.459\ compared\ with\ 0\.336\ and$", "0.454", "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"was\ added\ to\ report\ the\ pre\-registered$", "537", "mmlu_overall_n_items", 0),
    (r"exploratory\.\ the\ hom\-to\-het\ unanimous\-incorrect\ ratio\ is$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"with\ an\ equity\-clustered\ 95\ interval\ of$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"an\ equity\-clustered\ 95\ interval\ of\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"2\.52\ and\ a\ two\-way\ interval\ of$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"and\ a\ two\-way\ interval\ of\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"pair\-type\ sensitivity\ analysis\.\ same\-model\ agreement\ is$", "0.800", "revision_r1_5_independence_by_pair_type_hom_same_model_agreement", 3),
    (r"same\-model\ agreement\ is\ 0\.800\ in\ hom$", "0.794", "revision_r1_5_independence_by_pair_type_het_lite_same_model_agreement", 3),
    (r"in\ hom\ 0\.794\ in\ het\-lite\ and$", "0.862", "revision_r1_5_independence_by_pair_type_het_same_model_agreement", 3),
    (r"in\ het\ while\ different\-model\ agreement\ is$", "0.455", "revision_r1_5_independence_by_pair_type_het_lite_diff_model_agreement", 3),
    (r"agreement\ is\ 0\.455\ in\ het\-lite\ and$", "0.490", "revision_r1_5_independence_by_pair_type_het_diff_model_agreement", 3),
    (r"cells\.\ \-\ the\ resulting\ costs\ are$", "6.48", "frontier_hom_cost", 2, 10000.0),
    (r"6\.48\ x\ 10\ \-4\ for\ hom$", "1.52", "frontier_het_lite_cost", 2, 1000.0),
    (r"x\ 10\ \-3\ for\ het\-lite\ and$", "2.84", "frontier_het_cost", 2, 1000.0),
    (r"\-\ the\ primary\ hom\-het\ contrast\ remains$", "0.3363", "primary_delta_kappa", 4),
    (r"remains\ 0\.3363\ with\ 95\ intervals\ of$", "0.3035", "primary_ci_low", 4),
    (r"0\.3363\ with\ 95\ intervals\ of\ 0\.3035$", "0.3689", "primary_ci_high", 4),
    (r"of\ 0\.3035\ 0\.3689\ under\ equity\ clustering$", "0.2989", "revision_r3_2_clustering_date_ci_low", 4),
    (r"0\.3035\ 0\.3689\ under\ equity\ clustering\ 0\.2989$", "0.3656", "revision_r3_2_clustering_date_ci_high", 4),
    (r"0\.2989\ 0\.3656\ under\ date\ clustering\ and$", "0.2786", "revision_r3_2_clustering_two_way_ci_low", 4),
    (r"0\.3656\ under\ date\ clustering\ and\ 0\.2786$", "0.3877", "revision_r3_2_clustering_two_way_ci_high", 4),
    (r"5\ previously\ labelled\ the\ two\-way\ row$", "1200", "revision_r3_2_clustering_two_way_n_clusters", 0),
    (r"clusters\ which\ can\ be\ read\ as$", "1200", "revision_r3_2_clustering_two_way_n_clusters", 0),
    (r"1200\ independent\ clusters\.\ it\ now\ reads$", "100", "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"error\ indicators\.\ error\ correlation\ decreases\ from$", "0.984", "revision_r3_3_error_correlation_scored_phi_hom", 3),
    (r"decreases\ from\ 0\.984\ for\ hom\ to$", "0.742", "revision_r3_3_error_correlation_scored_phi_het_lite", 3),
    (r"hom\ to\ 0\.742\ for\ het\-lite\ and$", "0.530", "revision_r3_3_error_correlation_scored_phi_het", 3),
    (r"het\ giving\ a\ hom\-het\ contrast\ of$", "0.454", "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"hom\-het\ contrast\ of\ 0\.454\ 95\ ci$", "0.376", "revision_r3_3_error_correlation_scored_d_phi_ci_low", 3),
    (r"contrast\ of\ 0\.454\ 95\ ci\ 0\.376$", "0.534", "revision_r3_3_error_correlation_scored_d_phi_ci_high", 3),
    (r"0\.454\ 95\ ci\ 0\.376\ 0\.534\ two\-way$", "0.328", "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_low", 3),
    (r"95\ ci\ 0\.376\ 0\.534\ two\-way\ 0\.328$", "0.586", "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_high", 3),
    (r"ordering\ with\ a\ hom\-het\ contrast\ of$", "0.309", "revision_r3_3_error_correlation_strict_d_phi", 3),
    (r"hom\-het\ contrast\ of\ 0\.309\ 95\ ci$", "0.262", "revision_r3_3_error_correlation_strict_d_phi_ci_low", 3),
    (r"contrast\ of\ 0\.309\ 95\ ci\ 0\.262$", "0.354", "revision_r3_3_error_correlation_strict_d_phi_ci_high", 3),
    (r"0\.309\ 95\ ci\ 0\.262\ 0\.354\ two\-way$", "0.227", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_low", 3),
    (r"95\ ci\ 0\.262\ 0\.354\ two\-way\ 0\.227$", "0.387", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_high", 3),
    (r"the\ hom\-het\ aurc\ difference\ is\ \-$", "0.001", "revision_r3_4_paired_cluster_contrasts_aurc_delta_hom_het", 3),
    (r"an\ equity\-clustered\ 95\ interval\ of\ \-$", "0.059", "revision_r3_4_paired_cluster_contrasts_aurc_ci_low", 3),
    (r"an\ equity\-clustered\ 95\ interval\ of\ \-0\.059$", "0.060", "revision_r3_4_paired_cluster_contrasts_aurc_ci_high", 3),
    (r"consensus\ outcomes\ the\ unanimous\-incorrect\ ratio\ is$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"unanimous\-incorrect\ ratio\ is\ 1\.84\ with\ intervals$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"ratio\ is\ 1\.84\ with\ intervals\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"1\.84\ with\ intervals\ 1\.42\ 2\.52\ and$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"with\ intervals\ 1\.42\ 2\.52\ and\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"3\.06\ while\ the\ pile\-on\ difference\ is$", "0.189", "revision_r3_4_paired_cluster_contrasts_pile_on_delta_hom_het", 3),
    (r"difference\ is\ 0\.189\ with\ intervals\ 0\.160$", "0.216", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_high", 3),
    (r"0\.189\ with\ intervals\ 0\.160\ 0\.216\ and$", "0.140", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_low", 3),
    (r"with\ intervals\ 0\.160\ 0\.216\ and\ 0\.140$", "0.232", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_high", 3),
    (r"error\ yields\ a\ hom\-het\ contrast\ of$", "0.309", "revision_r3_3_error_correlation_strict_d_phi", 3),
    (r"with\ equity\ and\ two\-way\ intervals\ of$", "0.262", "revision_r3_3_error_correlation_strict_d_phi_ci_low", 3),
    (r"equity\ and\ two\-way\ intervals\ of\ 0\.262$", "0.354", "revision_r3_3_error_correlation_strict_d_phi_ci_high", 3),
    (r"two\-way\ intervals\ of\ 0\.262\ 0\.354\ and$", "0.227", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_low", 3),
    (r"intervals\ of\ 0\.262\ 0\.354\ and\ 0\.227$", "0.387", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_high", 3),
    (r"independence\.\ \-\ the\ confirmatory\ grid\ contains$", "54000", "calls_usable", 0),
    (r"contains\ 54000\ valid\ outputs\ and\ required$", "94566", "capture_requests_total", 0),
    (r"required\ 94566\ api\ requests\ of\ the$", "40566", "capture_requests_unsuccessful", 0),
    (r"requests\ of\ the\ 40566\ unsuccessful\ requests$", "40544", "capture_unsuccessful_ratelimit_or_quota", 0),
    (r"set\ the\ hom\-het\ agreement\ contrast\ is$", "0.485", "pilot_broken_delta_kappa", 3),
    (r"0\.485\ under\ a\ shared\ seed\ and$", "0.113", "pilot_clean_delta_kappa", 3),
    (r"accounting\ was\ added\ to\ report\ the$", "94566", "capture_requests_total", 0),
    (r"to\ report\ the\ 94566\ attempted\ requests$", "54000", "calls_usable", 0),
    (r"is\ timestamped\ and\ records\ the\ sha\-$", "256", "!algorithm name SHA-256", 0),
    (r"main\ ordering\ reproduces\ agreement\ decreases\ by$", "0.072", "mmlu_overall_d_kappa", 3),
    (r"pile\-on difference is 0\.189 with intervals$", "0.160", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_low", 3),
]


def normalize(raw: str) -> str:
    t = ISO_TIMESTAMP.sub(" ", raw)
    return re.sub(r"(\d),(\d{3})\b", r"\1\2", t)


def main() -> int:
    if not CLAIMS.exists():
        print("[letter-binding] INCOMPLETE: claims.json absent -- run make_claims.py",
              file=sys.stderr)
        return 2
    if not LETTER.exists():
        print("[letter-binding] INCOMPLETE: response letter not present in this copy",
              file=sys.stderr)
        return 2
    claims = json.loads(CLAIMS.read_text())
    text = normalize(LETTER.read_text())
    fails, bound, total, n_result, n_declared = check(
        L, text, claims, "response_to_reviewers.txt")

    # second pass: one- and two-digit integers
    short_ok = short_struct = 0
    for m in SHORT.finditer(text):
        lit = m.group(1)
        window = " ".join(text[max(0, m.start() - 60):m.end() + 14].split())
        hit = [r for r in SHORT_RESULTS
               if r[1] == lit and re.search(r[0], words_before(text, m.start(), 5))]
        if hit:
            rule = hit[0]
            target, nd = rule[2], rule[3]
            scale = rule[4] if len(rule) > 4 else 1.0
            if "/" in target:
                num, den = target.split("/")
                if num not in claims or den not in claims:
                    fails.append(f"{lit} bound to the ratio {target}, which names a missing claim")
                    continue
                value = float(claims[num]) / float(claims[den])
            else:
                if target not in claims:
                    fails.append(f"{lit} bound to {target}, which is not in claims.json")
                    continue
                value = float(claims[target])
            if not rounds_to(value, lit, nd, scale):
                fails.append(f"MISMATCH the letter says {lit} after \"{window[-60:]}\" but "
                             f"{target} = {value * scale:.4f} at the printed scale")
            else:
                short_ok += 1
            continue
        # The structural pattern has to cover THIS number, not merely appear somewhere nearby.
        # Matching against the whole window let a "Reviewer #2, Concern #1" header sixty
        # characters earlier excuse an unrelated integer, which fault injection caught.
        local = text[max(0, m.start() - 60):m.end() + 14]
        off = m.start() - max(0, m.start() - 60)
        why = [w for pat, w in SHORT_STRUCTURAL
               for mm in re.finditer(pat, local)
               if mm.start() <= off < mm.end()]
        if why:
            short_struct += 1
            continue
        fails.append(f"UNBOUND short integer {lit} in \"{window}\" -- not a declared result and "
                     f"not one of the structural classes, so nothing checks it")
    print(f"[letter-binding] {bound}/{total} response-letter numbers bound to a named claim or a "
          f"declared non-result ({n_result} rules bind a claim, {n_declared} declare a "
          f"non-result; {len(claims)} claims available)")
    print(f"[letter-binding] short integers: {short_ok} bound to a result, {short_struct} in a "
          f"declared structural class (concern headers, the 95% level, bibliography numbers, "
          f"float pointers, cost exponents, quoted reviewer text)")
    for f in fails:
        print("  " + f, file=sys.stderr)
    if fails:
        print(f"[letter-binding] {len(fails)} binding failure(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
