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
from binding_core import ISO_TIMESTAMP, check  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "results" / "latest" / "claims.json"
LETTER = ROOT / "submission" / "response_to_reviewers.txt"

# (context pattern, literal, target, decimals[, scale]); target "!reason" is a declared non-result
L = [
    (r"original\ manuscript\ id\ access\-$", "2026", "!IEEE manuscript ID Access-2026-38801", 0),
    (r"original\ manuscript\ id\ access\-2026\-$", "38801", "!IEEE manuscript ID Access-2026-38801", 0),
    (r"protocol\ on\ a\ substantially\ different\ domain$", "537", "mmlu_overall_n_items", 0),
    (r"to\ rank\ ensemble\ decisions\.\ aurc\ is$", "0.553", "revision_r1_1_r3_4_selective_prediction_hom_aurc", 3),
    (r"decisions\.\ aurc\ is\ 0\.553\ for\ hom$", "0.568", "revision_r1_1_r3_4_selective_prediction_het_lite_aurc", 3),
    (r"for\ hom\ 0\.568\ for\ het\-lite\ and$", "0.554", "revision_r1_1_r3_4_selective_prediction_het_aurc", 3),
    (r"het\.\ the\ hom\-het\ difference\ is\ \-$", "0.001", "revision_r3_4_paired_cluster_contrasts_aurc_delta_hom_het", 3),
    (r"a\ 95\ confidence\ interval\ of\ \-$", "0.059", "revision_r3_4_paired_cluster_contrasts_aurc_ci_low", 3),
    (r"a\ 95\ confidence\ interval\ of\ \-0\.059$", "0.060", "revision_r3_4_paired_cluster_contrasts_aurc_ci_high", 3),
    (r"date\ resampling\ the\ interval\ is\ \-$", "0.113", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_low", 3),
    (r"date\ resampling\ the\ interval\ is\ \-0\.113$", "0.115", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_high", 3),
    (r"produces\ unanimous\ incorrect\ directional\ decisions\ at$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"the\ equity\-clustered\ 95\ confidence\ interval\ is$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"equity\-clustered\ 95\ confidence\ interval\ is\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"2\.52\ and\ the\ two\-way\ interval\ is$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"and\ the\ two\-way\ interval\ is\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"have\ nearly\ identical\ mean\ member\ accuracy$", "0.951", "mmlu_capability_matched_matched_same_provider_member_accuracy", 3),
    (r"identical\ mean\ member\ accuracy\ 0\.951\ and$", "0.955", "mmlu_capability_matched_matched_cross_provider_member_accuracy", 3),
    (r"respectively\.\ \-\ their\ error\ correlations\ are$", "0.954", "mmlu_capability_matched_matched_same_provider_phi", 3),
    (r"their\ error\ correlations\ are\ 0\.954\ and$", "0.607", "mmlu_capability_matched_matched_cross_provider_phi", 3),
    (r"0\.954\ and\ 0\.607\ a\ difference\ of$", "0.347", "mmlu_capability_matched_matched_d_phi", 3),
    (r"with\ a\ 95\ confidence\ interval\ of$", "0.207", "mmlu_capability_matched_matched_d_phi_ci_low", 3),
    (r"a\ 95\ confidence\ interval\ of\ 0\.207$", "0.507", "mmlu_capability_matched_matched_d_phi_ci_high", 3),
    (r"a\ substantially\ different\ clinical\-knowledge\ task\ using$", "537", "mmlu_overall_n_items", 0),
    (r"the\ ordering\ reproduces\.\ agreement\ decreases\ by$", "0.072", "mmlu_overall_d_kappa", 3),
    (r"with\ a\ 95\ confidence\ interval\ of$", "0.040", "mmlu_overall_d_kappa_ci_low", 3),
    (r"a\ 95\ confidence\ interval\ of\ 0\.040$", "0.104", "mmlu_overall_d_kappa_ci_high", 3),
    (r"interval\ of\ 0\.040\ 0\.104\ compared\ with$", "0.336", "primary_delta_kappa", 3),
    (r"in\ finance\.\ error\ correlation\ decreases\ by$", "0.393", "mmlu_overall_d_phi", 3),
    (r"with\ a\ 95\ confidence\ interval\ of$", "0.325", "mmlu_overall_d_phi_ci_low", 3),
    (r"a\ 95\ confidence\ interval\ of\ 0\.325$", "0.459", "mmlu_overall_d_phi_ci_high", 3),
    (r"interval\ of\ 0\.325\ 0\.459\ compared\ with$", "0.454", "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"was\ added\ to\ report\ the\ pre\-registered$", "537", "mmlu_overall_n_items", 0),
    (r"\-\ the\ hom\-to\-het\ unanimous\-incorrect\ ratio\ is$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"and\ date\ resampling\ the\ interval\ is$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"date\ resampling\ the\ interval\ is\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"same\ model\.\ \-\ same\-model\ agreement\ is$", "0.800", "revision_r1_5_independence_by_pair_type_hom_same_model_agreement", 3),
    (r"same\-model\ agreement\ is\ 0\.800\ in\ hom$", "0.794", "revision_r1_5_independence_by_pair_type_het_lite_same_model_agreement", 3),
    (r"in\ hom\ 0\.794\ in\ het\-lite\ and$", "0.862", "revision_r1_5_independence_by_pair_type_het_same_model_agreement", 3),
    (r"0\.862\ in\ het\.\ different\-model\ agreement\ is$", "0.455", "revision_r1_5_independence_by_pair_type_het_lite_diff_model_agreement", 3),
    (r"agreement\ is\ 0\.455\ in\ het\-lite\ and$", "0.490", "revision_r1_5_independence_by_pair_type_het_diff_model_agreement", 3),
    (r"configuration\.\ \-\ the\ resulting\ costs\ are$", "6.48", "frontier_hom_cost", 2, 10000.0),
    (r"6\.48\ x\ 10\ \-4\ for\ hom$", "1.52", "frontier_het_lite_cost", 2, 1000.0),
    (r"x\ 10\ \-3\ for\ het\-lite\ and$", "2.84", "frontier_het_cost", 2, 1000.0),
    (r"therefore\ increases\ inference\ cost\ by\ approximately$", "4.4", "cost_ratio_het_over_hom", 1),
    (r"pair\ have\ mean\ member\ accuracy\ of$", "0.951", "mmlu_capability_matched_matched_same_provider_member_accuracy", 3),
    (r"mean\ member\ accuracy\ of\ 0\.951\ and$", "0.955", "mmlu_capability_matched_matched_cross_provider_member_accuracy", 3),
    (r"respectively\ while\ their\ error\ correlations\ are$", "0.954", "mmlu_capability_matched_matched_same_provider_phi", 3),
    (r"drawn\ twice\ contributes\ twice\.\ it\ uses$", "2000", "revision_r3_2_clustering_ticker_draws_used", 0),
    (r"draw\.\ \-\ primary\ hom\-het\ agreement\ contrast$", "0.3363", "primary_delta_kappa", 4),
    (r"\-\ primary\ hom\-het\ agreement\ contrast\ 0\.3363$", "0.3035", "primary_ci_low", 4),
    (r"primary\ hom\-het\ agreement\ contrast\ 0\.3363\ 0\.3035$", "0.3689", "primary_ci_high", 4),
    (r"0\.3363\ 0\.3035\ 0\.3689\ under\ equity\ clustering$", "100", "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"0\.3689\ under\ equity\ clustering\ 100\ clusters$", "0.2989", "revision_r3_2_clustering_date_ci_low", 4),
    (r"under\ equity\ clustering\ 100\ clusters\ 0\.2989$", "0.3656", "revision_r3_2_clustering_date_ci_high", 4),
    (r"0\.3656\ under\ date\ clustering\ 12\ clusters$", "0.2786", "revision_r3_2_clustering_two_way_ci_low", 4),
    (r"under\ date\ clustering\ 12\ clusters\ 0\.2786$", "0.3877", "revision_r3_2_clustering_two_way_ci_high", 4),
    (r"clusters\ 0\.2786\ 0\.3877\ under\ two\-way\ resampling$", "1200", "revision_r3_2_clustering_two_way_n_clusters", 0),
    (r"reported\ under\ the\ same\ scheme\.\ hom\-het\-lite$", "0.249", "contrast_dkappa_hom_hetlite", 3),
    (r"the\ same\ scheme\.\ hom\-het\-lite\ 0\.249\ equity$", "0.218", "contrast_dkappa_hom_hetlite_ci_low", 3),
    (r"same\ scheme\.\ hom\-het\-lite\ 0\.249\ equity\ 0\.218$", "0.280", "contrast_dkappa_hom_hetlite_ci_high", 3),
    (r"hom\-het\-lite\ 0\.249\ equity\ 0\.218\ 0\.280\ two\-way$", "0.208", "contrast_dkappa_hom_hetlite_two_way_ci_low", 3),
    (r"0\.249\ equity\ 0\.218\ 0\.280\ two\-way\ 0\.208$", "0.290", "contrast_dkappa_hom_hetlite_two_way_ci_high", 3),
    (r"0\.280\ two\-way\ 0\.208\ 0\.290\ \.\ het\-lite\-het$", "0.087", "contrast_dkappa_hetlite_het", 3),
    (r"0\.208\ 0\.290\ \.\ het\-lite\-het\ 0\.087\ equity$", "0.067", "contrast_dkappa_hetlite_het_ci_low", 3),
    (r"0\.290\ \.\ het\-lite\-het\ 0\.087\ equity\ 0\.067$", "0.105", "contrast_dkappa_hetlite_het_ci_high", 3),
    (r"het\-lite\-het\ 0\.087\ equity\ 0\.067\ 0\.105\ two\-way$", "0.045", "contrast_dkappa_hetlite_het_two_way_ci_low", 3),
    (r"0\.087\ equity\ 0\.067\ 0\.105\ two\-way\ 0\.045$", "0.123", "contrast_dkappa_hetlite_het_two_way_ci_high", 3),
    (r"control\ is\ measured\ on\ the\ same$", "100", "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"it\ receives\ the\ same\ treatment\.\ hom\-sametier$", "0.315", "control_delta_kappa", 3),
    (r"the\ same\ treatment\.\ hom\-sametier\ 0\.315\ equity$", "0.288", "control_ci_low", 3),
    (r"same\ treatment\.\ hom\-sametier\ 0\.315\ equity\ 0\.288$", "0.341", "control_ci_high", 3),
    (r"hom\-sametier\ 0\.315\ equity\ 0\.288\ 0\.341\ two\-way$", "0.270", "control_two_way_ci_low", 3),
    (r"0\.315\ equity\ 0\.288\ 0\.341\ two\-way\ 0\.270$", "0.361", "control_two_way_ci_high", 3),
    (r"also\ reported\ both\ ways\.\ error\ correlation$", "0.454", "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"both\ ways\.\ error\ correlation\ 0\.454\ equity$", "0.376", "revision_r3_3_error_correlation_scored_d_phi_ci_low", 3),
    (r"ways\.\ error\ correlation\ 0\.454\ equity\ 0\.376$", "0.534", "revision_r3_3_error_correlation_scored_d_phi_ci_high", 3),
    (r"correlation\ 0\.454\ equity\ 0\.376\ 0\.534\ two\-way$", "0.328", "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_low", 3),
    (r"0\.454\ equity\ 0\.376\ 0\.534\ two\-way\ 0\.328$", "0.586", "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_high", 3),
    (r"specification\ counting\ hold\ as\ an\ error$", "0.309", "revision_r3_3_error_correlation_strict_d_phi", 3),
    (r"hold\ as\ an\ error\ 0\.309\ equity$", "0.262", "revision_r3_3_error_correlation_strict_d_phi_ci_low", 3),
    (r"as\ an\ error\ 0\.309\ equity\ 0\.262$", "0.354", "revision_r3_3_error_correlation_strict_d_phi_ci_high", 3),
    (r"error\ 0\.309\ equity\ 0\.262\ 0\.354\ two\-way$", "0.227", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_low", 3),
    (r"0\.309\ equity\ 0\.262\ 0\.354\ two\-way\ 0\.227$", "0.387", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_high", 3),
    (r"two\-way\ 0\.227\ 0\.387\ \.\ unanimous\-incorrect\ ratio$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"0\.387\ \.\ unanimous\-incorrect\ ratio\ 1\.84\ equity$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"\.\ unanimous\-incorrect\ ratio\ 1\.84\ equity\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"ratio\ 1\.84\ equity\ 1\.42\ 2\.52\ two\-way$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"1\.84\ equity\ 1\.42\ 2\.52\ two\-way\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"2\.52\ two\-way\ 1\.13\ 3\.06\ \.\ pile\-on$", "0.189", "revision_r3_4_paired_cluster_contrasts_pile_on_delta_hom_het", 3),
    (r"1\.13\ 3\.06\ \.\ pile\-on\ 0\.189\ equity$", "0.160", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_low", 3),
    (r"3\.06\ \.\ pile\-on\ 0\.189\ equity\ 0\.160$", "0.216", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_high", 3),
    (r"pile\-on\ 0\.189\ equity\ 0\.160\ 0\.216\ two\-way$", "0.140", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_low", 3),
    (r"0\.189\ equity\ 0\.160\ 0\.216\ two\-way\ 0\.140$", "0.232", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_high", 3),
    (r"two\-way\ 0\.140\ 0\.232\ \.\ aurc\ \-$", "0.001", "revision_r3_4_paired_cluster_contrasts_aurc_delta_hom_het", 3),
    (r"0\.232\ \.\ aurc\ \-0\.001\ equity\ \-$", "0.059", "revision_r3_4_paired_cluster_contrasts_aurc_ci_low", 3),
    (r"0\.232\ \.\ aurc\ \-0\.001\ equity\ \-0\.059$", "0.060", "revision_r3_4_paired_cluster_contrasts_aurc_ci_high", 3),
    (r"\-0\.001\ equity\ \-0\.059\ 0\.060\ two\-way\ \-$", "0.113", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_low", 3),
    (r"\-0\.001\ equity\ \-0\.059\ 0\.060\ two\-way\ \-0\.113$", "0.115", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_high", 3),
    (r"only\ the\ distinct\ equities\ of\ a$", "100", "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"and\ why\ the\ unanimous\-incorrect\ interval\ is$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"why\ the\ unanimous\-incorrect\ interval\ is\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"1\.42\ 2\.52\ rather\ than\ the\ narrower$", "1.51", "!superseded interval, labelled as superseded in the same sentence", 0),
    (r"2\.52\ rather\ than\ the\ narrower\ 1\.51$", "2.35", "!superseded interval, labelled as superseded in the same sentence", 0),
    (r"5\ previously\ labelled\ the\ two\-way\ row$", "1200", "revision_r3_2_clustering_two_way_n_clusters", 0),
    (r"clusters\ which\ can\ be\ read\ as$", "1200", "revision_r3_2_clustering_two_way_n_clusters", 0),
    (r"1200\ independent\ clusters\.\ it\ now\ reads$", "100", "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"agent\ pair\.\ error\ correlation\ decreases\ from$", "0.984", "revision_r3_3_error_correlation_scored_phi_hom", 3),
    (r"decreases\ from\ 0\.984\ for\ hom\ to$", "0.742", "revision_r3_3_error_correlation_scored_phi_het_lite", 3),
    (r"hom\ to\ 0\.742\ for\ het\-lite\ and$", "0.530", "revision_r3_3_error_correlation_scored_phi_het", 3),
    (r"for\ het\.\ the\ hom\-het\ contrast\ is$", "0.454", "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"with\ a\ 95\ confidence\ interval\ of$", "0.376", "revision_r3_3_error_correlation_scored_d_phi_ci_low", 3),
    (r"a\ 95\ confidence\ interval\ of\ 0\.376$", "0.534", "revision_r3_3_error_correlation_scored_d_phi_ci_high", 3),
    (r"under\ two\-way\ resampling\ the\ interval\ is$", "0.328", "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_low", 3),
    (r"two\-way\ resampling\ the\ interval\ is\ 0\.328$", "0.586", "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_high", 3),
    (r"error\.\ the\ corresponding\ hom\-het\ contrast\ is$", "0.309", "revision_r3_3_error_correlation_strict_d_phi", 3),
    (r"with\ a\ 95\ confidence\ interval\ of$", "0.262", "revision_r3_3_error_correlation_strict_d_phi_ci_low", 3),
    (r"a\ 95\ confidence\ interval\ of\ 0\.262$", "0.354", "revision_r3_3_error_correlation_strict_d_phi_ci_high", 3),
    (r"0\.354\ \.\ the\ two\-way\ interval\ is$", "0.227", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_low", 3),
    (r"\.\ the\ two\-way\ interval\ is\ 0\.227$", "0.387", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_high", 3),
    (r"the\ hom\-het\ aurc\ difference\ is\ \-$", "0.001", "revision_r3_4_paired_cluster_contrasts_aurc_delta_hom_het", 3),
    (r"95\ equity\-clustered\ confidence\ interval\ of\ \-$", "0.059", "revision_r3_4_paired_cluster_contrasts_aurc_ci_low", 3),
    (r"95\ equity\-clustered\ confidence\ interval\ of\ \-0\.059$", "0.060", "revision_r3_4_paired_cluster_contrasts_aurc_ci_high", 3),
    (r"the\ corresponding\ two\-way\ interval\ is\ \-$", "0.113", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_low", 3),
    (r"the\ corresponding\ two\-way\ interval\ is\ \-0\.113$", "0.115", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_high", 3),
    (r"zero\.\ \-\ the\ unanimous\-incorrect\ ratio\ is$", "1.84", "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"1\.84\ with\ an\ equity\-clustered\ interval\ of$", "1.42", "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"with\ an\ equity\-clustered\ interval\ of\ 1\.42$", "2.52", "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    (r"2\.52\ and\ a\ two\-way\ interval\ of$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"and\ a\ two\-way\ interval\ of\ 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"for\ pile\-on\ the\ hom\-het\ difference\ is$", "0.189", "revision_r3_4_paired_cluster_contrasts_pile_on_delta_hom_het", 3),
    (r"0\.189\ with\ an\ equity\-clustered\ interval\ of$", "0.160", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_low", 3),
    (r"with\ an\ equity\-clustered\ interval\ of\ 0\.160$", "0.216", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_high", 3),
    (r"0\.216\ and\ a\ two\-way\ interval\ of$", "0.140", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_low", 3),
    (r"and\ a\ two\-way\ interval\ of\ 0\.140$", "0.232", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_high", 3),
    (r"configurations\.\ the\ resulting\ hom\-het\ contrast\ is$", "0.309", "revision_r3_3_error_correlation_strict_d_phi", 3),
    (r"0\.354\ and\ a\ two\-way\ interval\ of$", "0.227", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_low", 3),
    (r"and\ a\ two\-way\ interval\ of\ 0\.227$", "0.387", "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_high", 3),
    (r"independence\.\ \-\ the\ confirmatory\ grid\ contains$", "54000", "calls_usable", 0),
    (r"valid\ outputs\.\ completing\ the\ grid\ required$", "94566", "capture_requests_total", 0),
    (r"required\ 94566\ api\ requests\.\ of\ the$", "40566", "capture_requests_unsuccessful", 0),
    (r"requests\.\ of\ the\ 40566\ unsuccessful\ requests$", "40544", "capture_unsuccessful_ratelimit_or_quota", 0),
    (r"and\ model\ set\.\ the\ contrast\ is$", "0.485", "pilot_broken_delta_kappa", 3),
    (r"0\.485\ under\ a\ shared\ seed\ and$", "0.113", "pilot_clean_delta_kappa", 3),
    (r"accounting\ was\ added\ to\ report\ the$", "94566", "capture_requests_total", 0),
    (r"to\ report\ the\ 94566\ attempted\ requests$", "54000", "calls_usable", 0),
    (r"is\ timestamped\ and\ records\ the\ sha\-$", "256", "!algorithm name SHA-256", 0),
    (r"we\ added\ a\ pre\-registered\ replication\ using$", "537", "mmlu_overall_n_items", 0),
    (r"main\ ordering\ reproduces\.\ agreement\ decreases\ by$", "0.072", "mmlu_overall_d_kappa", 3),
    (r"0\.104\ while\ error\ correlation\ decreases\ by$", "0.393", "mmlu_overall_d_phi", 3),
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
    print(f"[letter-binding] {bound}/{total} response-letter numbers bound to a named claim or a "
          f"declared non-result ({n_result} rules bind a claim, {n_declared} declare a "
          f"non-result; {len(claims)} claims available)")
    for f in fails:
        print("  " + f, file=sys.stderr)
    if fails:
        print(f"[letter-binding] {len(fails)} binding failure(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
