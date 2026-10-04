"""Gate: every number in the manuscript is BOUND to the one claim it must equal.

check_claims.py asks whether a claim's value appears somewhere in main.tex, and
check_coverage.py asks whether a manuscript number equals something in claims.json. Both are
set-membership tests, and with 378 claims that is close to vacuous: the coverage gate expanded
the claims into 3,046 candidate strings (every rounding from 0 to 6 decimals, three unit
transforms, and every pairwise quotient of every cost), so 28 of its 161 literals were
"traced" to more than three different claims and one -- the model name grok-4.3 -- traced to
a bootstrap ratio of 4.289. A number that matches anything proves nothing.

This gate binds instead of matching. Each rule below names the phrase a number follows and the
single claim it must equal, so

    (r"primary reduction of$",            "0.336", "primary_delta_kappa", 3),

asserts that the number written after "primary reduction of" is primary_delta_kappa rounded to
three decimals -- not that 0.336 exists somewhere in the analysis. Three failures follow from
that, none of which the older gates could see:

  * a manuscript number that disagrees with its claim, even when some other claim matches it;
  * a number no rule covers, including one newly inserted into a sentence;
  * a rule nothing matches, which means the sentence it described has been edited or deleted.

Non-results (model names, API list prices, DOI prefixes, years, the SHA-256 algorithm name)
are bound the same way, to a reason rather than a claim. They are bound to their CONTEXT, so
declaring the list price 0.20 does not also excuse a 0.20 that appears in a results sentence --
which the old NON_RESULTS dict, keyed on the bare string, did.

  python code/src/check_binding.py
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "results" / "latest" / "claims.json"
TEX = ROOT / "paper" / "main.tex"

# A number followed by letters is a placeholder, not a value. main.tex shipped
# "(95\% CI $[0.393LO,\,0.393HI]$)" for months: the coverage gate's literal pattern required a
# non-word character after the digits, so "0.393LO" was never extracted and never reported.
# A TeX dimension (1.25in, 11pt) is digits followed by letters but is not a placeholder, so the
# units are excluded; everything else that runs digits into letters still fails.
PLACEHOLDER = re.compile(r"(?<![\w.])\d+\.\d+"
                         r"(?!(?:in|cm|mm|pt|ex|em|bp|pc|dd|sp|px|true)\b)[A-Za-z]+")

LIT = re.compile(r"(?<![\w.])(\d+\.\d+|\d{3,})(?![\w])")

# (context pattern, literal, target, decimals[, scale])
#   target "claim_key"  -> the literal must equal that claim, rounded half-up at `decimals`
#   target "!reason"    -> declared non-result, with the reason it appears
#   scale               -> multiply the claim before rounding, for a mantissa printed as
#                          6.48 \times 10^{-4}
R = [
    # ---------------------------------------------------------------- front matter / abstract
    (r"date of publication xxxx 00$", "0000", "!IEEE template placeholder in \\history", 0),
    (r"date of current version xxxx 00$", "0000", "!IEEE template placeholder in \\history", 0),
    (r"manuscript submitted august 3$", "2026", "!submission date", 0),
    (r"agreement and inference cost\. in a$", "54000", "calls_usable", 0),
    (r"directional financial-analysis task covering$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"agreement with a primary reduction of$", "0.336", "primary_delta_kappa", 3),
    (r"primary reduction of 0\.336 95 ci$", "0.304", "primary_ci_low", 3),
    (r"of 0\.336 95 ci 0\.304 --$", "0.369", "primary_ci_high", 3),
    (r"but increases inference cost by approximately$", "4.4", "cost_ratio_het_over_hom", 1),
    (r"error indicators\. error correlation decreases by$", "0.454",
     "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"correlation decreases by 0\.454 95 ci$", "0.376",
     "revision_r3_3_error_correlation_scored_d_phi_ci_low", 3),
    (r"by 0\.454 95 ci 0\.376 to$", "0.534",
     "revision_r3_3_error_correlation_scored_d_phi_ci_high", 3),
    (r"on a substantially different task involving$", "537", "mmlu_overall_n_items", 0),
    (r"the directional pattern\. agreement decreases by$", "0.072", "mmlu_overall_d_kappa", 3),
    (r"agreement decreases by 0\.072 95 ci$", "0.040", "mmlu_overall_d_kappa_ci_low", 3),
    (r"by 0\.072 95 ci 0\.040 to$", "0.104", "mmlu_overall_d_kappa_ci_high", 3),
    (r"0\.104 while error correlation decreases by$", "0.393", "mmlu_overall_d_phi", 3),
    (r"correlation decreases by 0\.393 95 ci$", "0.325", "mmlu_overall_d_phi_ci_low", 3),
    (r"by 0\.393 95 ci 0\.325 to$", "0.459", "mmlu_overall_d_phi_ci_high", 3),
    (r"ensembles generate unanimous incorrect decisions at$", "1.84",
     "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"of fully heterogeneous ensembles 95 ci$", "1.42",
     "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"heterogeneous ensembles 95 ci 1\.42 to$", "2.52",
     "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    # ------------------------------------------------------------------------- introduction
    (r"pre-registered empirical study comprising$", "54000", "calls_usable", 0),
    (r"increases with a primary contrast of$", "0.336", "primary_delta_kappa", 3),
    (r"and a 95 confidence interval of$", "0.304", "primary_ci_low", 3),
    (r"a 95 confidence interval of 0\.304$", "0.369", "primary_ci_high", 3),
    (r"configuration reduces agreement at an approximately$", "4.4",
     "cost_ratio_het_over_hom", 1),
    (r"generate unanimous incorrect directional decisions at$", "1.84",
     "revision_r1_4_unanimous_incorrect_ratio", 2),
    # ------------------------------------------------------- provider table (names + prices)
    (r"string in out openai primary gpt-$", "5.4", "!model name gpt-5.4-nano", 0),
    (r"openai primary gpt-5\.4-nano$", "0.20", "!API list price, USD per 1M input tokens", 0),
    (r"primary gpt-5\.4-nano 0\.20$", "1.25", "!API list price, USD per 1M output tokens", 0),
    (r"1\.25 google het\. gemini-$", "3.5", "!model name gemini-3.5-flash", 0),
    (r"google het\. gemini-3\.5-flash$", "1.50", "!API list price, USD per 1M input tokens", 0),
    (r"het\. gemini-3\.5-flash 1\.50$", "9.00", "!API list price, USD per 1M output tokens", 0),
    (r"9\.00 xai het\. grok-$", "4.3", "!model name grok-4.3", 0),
    (r"xai het\. grok-4\.3$", "1.25", "!API list price, USD per 1M input tokens", 0),
    (r"xai het\. grok-4\.3 1\.25$", "2.50", "!API list price, USD per 1M output tokens", 0),
    # ------------------------------------------------------------------------ method / design
    (r"r c s i sha -$", "256", "!algorithm name SHA-256", 0),
    (r"the confidence interval\. for each of$", "2000",
     "revision_r3_2_clustering_ticker_draws_used", 0),
    (r"three resampling schemes equity clustering over$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"rule in the confirmatory dataset all$", "54000", "calls_usable", 0),
    (r"the released log\. the experiment covers$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"sectors and 12 analysis dates in$", "2026", "!calendar year of the analysis dates", 0),
    (r"ensemble\. the complete design therefore contains$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"contains 100 12 3 3 5$", "54000", "grid_cells_total", 0),
    (r"are also chosen to span distinct$", "2026", "!calendar year of the analysis dates", 0),
    (r"executed using a sampling temperature of$", "0.7",
     "!protocol parameter: sampling temperature, data/configs/config.yaml", 1),
    (r"and secondary cluster bootstrap over equities$", "2000",
     "revision_r3_2_clustering_ticker_draws_used", 0),
    (r"resulting pre-registration was assigned a sha-$", "256",
     "!algorithm name SHA-256", 0),
    # ------------------------------------------------------- contrast table (Models section)
    (r"95 ci hom - het primary$", "0.336", "primary_delta_kappa", 3),
    (r"ci hom - het primary 0\.336$", "0.304", "primary_ci_low", 3),
    (r"hom - het primary 0\.336 0\.304$", "0.369", "primary_ci_high", 3),
    (r"0\.336 0\.304 0\.369 hom - het-lite$", "0.249", "contrast_dkappa_hom_hetlite", 3),
    (r"0\.304 0\.369 hom - het-lite 0\.249$", "0.218",
     "contrast_dkappa_hom_hetlite_ci_low", 3),
    (r"0\.369 hom - het-lite 0\.249 0\.218$", "0.280",
     "contrast_dkappa_hom_hetlite_ci_high", 3),
    (r"0\.249 0\.218 0\.280 het-lite - het$", "0.087", "contrast_dkappa_hetlite_het", 3),
    (r"0\.218 0\.280 het-lite - het 0\.087$", "0.067",
     "contrast_dkappa_hetlite_het_ci_low", 3),
    (r"0\.280 het-lite - het 0\.087 0\.067$", "0.105",
     "contrast_dkappa_hetlite_het_ci_high", 3),
    # ------------------------------------------------------------------------------- results
    (r"includes the complete planned set of$", "54000", "calls_usable", 0),
    (r"set of 54000 model calls across$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"as cross-provider heterogeneity increases\. fleiss is$", "0.552", "kappa_hom", 3),
    (r"increases\. fleiss is 0\.552 for hom$", "0.302", "frontier_het_lite_kappa", 3),
    (r"for hom 0\.302 for het-lite and$", "0.215", "kappa_het", 3),
    (r"contrast is hom-het hom - het$", "0.336", "primary_delta_kappa", 3),
    (r"a 95 cluster-bootstrap confidence interval of$", "0.304", "primary_ci_low", 3),
    (r"95 cluster-bootstrap confidence interval of 0\.304$", "0.369", "primary_ci_high", 3),
    # ------------------------------------------- agreement-statistic robustness (kappa/alpha/AC1)
    (r"proportion of hold responses decreases from$", "0.71", "rev_hom_share_hold", 2),
    (r"decreases from 0\.71 in hom to$", "0.56", "rev_het_share_hold", 2),
    (r"config ac1 buy hold sell hom$", "0.552", "rev_hom_fleiss_kappa", 3),
    (r"ac1 buy hold sell hom 0\.552$", "0.552", "rev_hom_krippendorff_alpha", 3),
    (r"buy hold sell hom 0\.552 0\.552$", "0.743", "rev_hom_gwet_ac1", 3),
    (r"hold sell hom 0\.552 0\.552 0\.743$", "0.212", "rev_hom_share_buy", 3),
    (r"sell hom 0\.552 0\.552 0\.743 0\.212$", "0.709", "rev_hom_share_hold", 3),
    (r"hom 0\.552 0\.552 0\.743 0\.212 0\.709$", "0.079", "rev_hom_share_sell", 3),
    (r"0\.552 0\.743 0\.212 0\.709 0\.079 het-lite$", "0.302",
     "rev_het_lite_fleiss_kappa", 3),
    (r"0\.743 0\.212 0\.709 0\.079 het-lite 0\.302$", "0.303",
     "rev_het_lite_krippendorff_alpha", 3),
    (r"0\.212 0\.709 0\.079 het-lite 0\.302 0\.303$", "0.548", "rev_het_lite_gwet_ac1", 3),
    (r"0\.709 0\.079 het-lite 0\.302 0\.303 0\.548$", "0.282", "rev_het_lite_share_buy", 3),
    (r"0\.079 het-lite 0\.302 0\.303 0\.548 0\.282$", "0.653", "rev_het_lite_share_hold", 3),
    (r"het-lite 0\.302 0\.303 0\.548 0\.282 0\.653$", "0.064", "rev_het_lite_share_sell", 3),
    (r"0\.303 0\.548 0\.282 0\.653 0\.064 het$", "0.215", "rev_het_fleiss_kappa", 3),
    (r"0\.548 0\.282 0\.653 0\.064 het 0\.215$", "0.216", "rev_het_krippendorff_alpha", 3),
    (r"0\.282 0\.653 0\.064 het 0\.215 0\.216$", "0.398", "rev_het_gwet_ac1", 3),
    (r"0\.653 0\.064 het 0\.215 0\.216 0\.398$", "0.358", "rev_het_share_buy", 3),
    (r"0\.064 het 0\.215 0\.216 0\.398 0\.358$", "0.556", "rev_het_share_hold", 3),
    (r"het 0\.215 0\.216 0\.398 0\.358 0\.556$", "0.085", "rev_het_share_sell", 3),
    # ------------------------------------------------------------------ agreement-cost frontier
    (r"llcc config h ensemble-decision hom 0$", "0.552", "frontier_hom_kappa", 3),
    (r"config h ensemble-decision hom 0 0\.552$", "6.48", "frontier_hom_cost", 2, 1e4),
    (r"0\.552 6\.48 10 -4 het-lite 1$", "0.302", "frontier_het_lite_kappa", 3),
    (r"6\.48 10 -4 het-lite 1 0\.302$", "1.52", "frontier_het_lite_cost", 2, 1e3),
    (r"0\.302 1\.52 10 -3 het 3$", "0.215", "frontier_het_kappa", 3),
    (r"1\.52 10 -3 het 3 0\.215$", "2.84", "frontier_het_cost", 2, 1e3),
    (r"five-agent ensemble decision increases from approximately$", "6.5",
     "frontier_hom_cost", 1, 1e4),
    (r"6\.5 10 -4 for hom to$", "1.5", "frontier_het_lite_cost", 1, 1e3),
    (r"1\.5 10 -3 for het-lite and$", "2.8", "frontier_het_cost", 1, 1e3),
    (r"therefore increases inference cost by approximately$", "4.4",
     "cost_ratio_het_over_hom", 1),
    # ------------------------------------------------------------------- clustering robustness
    (r"95 ci equity pre-reg\. 100 equities$", "0.3363",
     "revision_r3_2_clustering_ticker_point", 4),
    (r"resampled units 95 ci equity pre-reg\.$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"ci equity pre-reg\. 100 equities 0\.3363$", "0.3035",
     "revision_r3_2_clustering_ticker_ci_low", 4),
    (r"equity pre-reg\. 100 equities 0\.3363 0\.3035$", "0.3689",
     "revision_r3_2_clustering_ticker_ci_high", 4),
    (r"0\.3035 0\.3689 analysis date 12 dates$", "0.3363",
     "revision_r3_2_clustering_date_point", 4),
    (r"0\.3689 analysis date 12 dates 0\.3363$", "0.2989",
     "revision_r3_2_clustering_date_ci_low", 4),
    (r"analysis date 12 dates 0\.3363 0\.2989$", "0.3656",
     "revision_r3_2_clustering_date_ci_high", 4),
    # Table 5's two-way row now reads "100 x 12" rather than "1200", because 1,200 could be
    # misread as 1,200 independent clusters when it is the sampled intersection count.
    (r"12 dates 0\.3363 0\.2989 0\.3656 two-way$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"0\.3363 0\.2989 0\.3656 two-way 100 12$", "0.3363",
     "revision_r3_2_clustering_two_way_point", 4),
    (r"0\.2989 0\.3656 two-way 100 12 0\.3363$", "0.2786",
     "revision_r3_2_clustering_two_way_ci_low", 4),
    (r"0\.3656 two-way 100 12 0\.3363 0\.2786$", "0.3877",
     "revision_r3_2_clustering_two_way_ci_high", 4),
    # ---------------------------------------------------------------------- error correlation
    (r"agent pair\. error correlation decreases from$", "0.984",
     "revision_r3_3_error_correlation_scored_phi_hom", 3),
    (r"decreases from 0\.984 for hom to$", "0.742",
     "revision_r3_3_error_correlation_scored_phi_het_lite", 3),
    (r"hom to 0\.742 for het\-lite and$", "0.530",
     "revision_r3_3_error_correlation_scored_phi_het", 3),
    (r"and 0\.530 for het giving hom-het$", "0.454",
     "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"het giving hom-het 0\.454 95 ci$", "0.376",
     "revision_r3_3_error_correlation_scored_d_phi_ci_low", 3),
    (r"giving hom-het 0\.454 95 ci 0\.376$", "0.534",
     "revision_r3_3_error_correlation_scored_d_phi_ci_high", 3),
    (r"an error\. the corresponding values are$", "0.586",
     "revision_r3_3_error_correlation_strict_phi_hom", 3),
    (r"error\. the corresponding values are 0\.586$", "0.359",
     "revision_r3_3_error_correlation_strict_phi_het_lite", 3),
    (r"corresponding values are 0\.586 0\.359 and$", "0.277",
     "revision_r3_3_error_correlation_strict_phi_het", 3),
    (r"0\.586 0\.359 and 0\.277 with hom-het$", "0.309",
     "revision_r3_3_error_correlation_strict_d_phi", 3),
    (r"0\.277 with hom-het 0\.309 95 ci$", "0.262",
     "revision_r3_3_error_correlation_strict_d_phi_ci_low", 3),
    (r"with hom-het 0\.309 95 ci 0\.262$", "0.354",
     "revision_r3_3_error_correlation_strict_d_phi_ci_high", 3),
    # -------------------------------------------------- shared-seed dependence / measurement
    (r"the hom within-minus-cross difference is approximately$", "0.001",
     "ms_within_run_vs_cross_run_nondeterminism_check_hom_within_cross", 3),
    (r"pilot the estimated primary contrast was$", "0.485", "pilot_broken_delta_kappa", 3),
    (r"0\.485 under shared per-run seeding and$", "0.113", "pilot_clean_delta_kappa", 3),
    (r"het 3 runs 5 agents i\.e\.$", "480", "pilot_clean_n_rows", 0),
    (r"configurations produce within-minus-cross differences of -$", "0.048",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_lite_within_cross", 3),
    (r"within-minus-cross differences of -0\.048 and -$", "0.074",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_within_cross", 3),
    (r"within cross within - cross hom$", "0.552",
     "ms_within_run_vs_cross_run_nondeterminism_check_hom_within", 3),
    (r"cross within - cross hom 0\.552$", "0.551",
     "ms_within_run_vs_cross_run_nondeterminism_check_hom_cross", 3),
    (r"within - cross hom 0\.552 0\.551$", "0.001",
     "ms_within_run_vs_cross_run_nondeterminism_check_hom_within_cross", 3),
    (r"cross hom 0\.552 0\.551 0\.001 het-lite$", "0.302",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_lite_within", 3),
    (r"hom 0\.552 0\.551 0\.001 het-lite 0\.302$", "0.350",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_lite_cross", 3),
    (r"0\.551 0\.001 het-lite 0\.302 0\.350 -$", "0.048",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_lite_within_cross", 3),
    (r"0\.001 het-lite 0\.302 0\.350 -0\.048 het$", "0.215",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_within", 3),
    (r"het-lite 0\.302 0\.350 -0\.048 het 0\.215$", "0.289",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_cross", 3),
    (r"0\.350 -0\.048 het 0\.215 0\.289 -$", "0.074",
     "ms_within_run_vs_cross_run_nondeterminism_check_het_within_cross", 3),
    (r"the same model\. same\-model agreement is$", "0.800",
     "revision_r1_5_independence_by_pair_type_hom_same_model_agreement", 3),
    (r"same\-model agreement is 0\.800 in hom$", "0.794",
     "revision_r1_5_independence_by_pair_type_het_lite_same_model_agreement", 3),
    (r"in hom 0\.794 in het-lite and$", "0.862",
     "revision_r1_5_independence_by_pair_type_het_same_model_agreement", 3),
    (r"in het while different\-model agreement is$", "0.455",
     "revision_r1_5_independence_by_pair_type_het_lite_diff_model_agreement", 3),
    (r"agreement is 0\.455 in het\-lite and$", "0.490",
     "revision_r1_5_independence_by_pair_type_het_diff_model_agreement", 3),
    # ------------------------------------------------------------------- provider-pair agreement
    (r"agreement comes from\. same-provider agreement is$", "0.92",
     "ms_provider_pair_direction_agreement_descriptiv_google_google", 2),
    (r"0\.92 for google agent pairs and$", "0.80",
     "ms_provider_pair_direction_agreement_descriptiv_openai_openai", 2),
    (r"pairs whereas cross-provider agreement ranges from$", "0.43",
     "ms_provider_pair_direction_agreement_descriptiv_google_xai", 2),
    (r"cross-provider agreement ranges from 0\.43 to$", "0.63",
     "ms_provider_pair_direction_agreement_descriptiv_openai_xai", 2),
    (r"these effects further\. figure t width$", "0.85",
     "!\\includegraphics width fraction", 2),
    # ------------------------------------------------------------- secondary directional accuracy
    (r"the estimated directional hit rates are$", "0.438",
     "ms_accuracy_proxy_secondary_axis_study_powered__hom_hit_rate", 3),
    (r"hit rates are 0\.438 for hom$", "0.463",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_lite_hit_rate", 3),
    (r"for hom 0\.463 for het-lite and$", "0.488",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_hit_rate", 3),
    (r"hit rates at or modestly below$", "0.5",
     "!chance level for a binary directional call", 1),
    (r"hit-rate n 95 ci wilson hom$", "0.438",
     "ms_accuracy_proxy_secondary_axis_study_powered__hom_hit_rate", 3),
    (r"n 95 ci wilson hom 0\.438$", "315",
     "ms_accuracy_proxy_secondary_axis_study_powered__hom_n", 0),
    (r"95 ci wilson hom 0\.438 315$", "0.384",
     "ms_accuracy_proxy_secondary_axis_study_powered__hom_95_ci_wilson_low", 3),
    (r"ci wilson hom 0\.438 315 0\.384$", "0.493",
     "ms_accuracy_proxy_secondary_axis_study_powered__hom_95_ci_wilson_high", 3),
    (r"hom 0\.438 315 0\.384 0\.493 het-lite$", "0.463",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_lite_hit_rate", 3),
    (r"0\.438 315 0\.384 0\.493 het-lite 0\.463$", "339",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_lite_n", 0),
    (r"315 0\.384 0\.493 het-lite 0\.463 339$", "0.411",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_lite_95_ci_wilson_low", 3),
    (r"0\.384 0\.493 het-lite 0\.463 339 0\.411$", "0.516",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_lite_95_ci_wilson_high", 3),
    (r"het-lite 0\.463 339 0\.411 0\.516 het$", "0.488",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_hit_rate", 3),
    (r"0\.463 339 0\.411 0\.516 het 0\.488$", "525",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_n", 0),
    (r"339 0\.411 0\.516 het 0\.488 525$", "0.445",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_95_ci_wilson_low", 3),
    (r"0\.411 0\.516 het 0\.488 525 0\.445$", "0.530",
     "ms_accuracy_proxy_secondary_axis_study_powered__het_95_ci_wilson_high", 3),
    # ------------------------------------------------------------- exploratory consensus errors
    (r"the unanimity rate decreases from$", "0.591", "rev_hom_unanimous_rate", 3),
    (r"decreases from 0\.591 for hom to$", "0.315", "rev_het_lite_unanimous_rate", 3),
    (r"hom to 0\.315 for het-lite and$", "0.267", "rev_het_unanimous_rate", 3),
    (r"are unanimous directional and incorrect is$", "0.058",
     "rev_hom_unanimous_wrong_rate", 3),
    (r"and incorrect is 0\.058 for hom$", "0.030", "rev_het_lite_unanimous_wrong_rate", 3),
    (r"for hom 0\.030 for het-lite and$", "0.032", "rev_het_unanimous_wrong_rate", 3),
    (r"form of collective error at approximately$", "1.84",
     "revision_r1_4_unanimous_incorrect_ratio", 2),
    (r"gives a 95 confidence interval of$", "1.42",
     "revision_r1_4_unanimous_incorrect_ratio_ci_low", 2),
    (r"a 95 confidence interval of 1\.42$", "2.52",
     "revision_r1_4_unanimous_incorrect_ratio_ci_high", 2),
    # The same cost premium is stated twice, in the exploratory subsection and again in the
    # Discussion, and the rewrite gave the two sentences different lead-ins. One rule covered
    # both before; now each occurrence needs its own.
    (r"unanimous directional errors at an approximately$", "2.3",
     "cost_ratio_het_lite_over_hom", 1),
    (r"comparable to het at an approximately$", "2.3", "cost_ratio_het_lite_over_hom", 1),
    (r"approximately 2\.3 cost premium compared with$", "4.4", "cost_ratio_het_over_hom", 1),
    (r"endorsing the incorrect majority decreases from$", "0.824",
     "rev_hom_p_agree_majority_wrong", 3),
    (r"decreases from 0\.824 for hom to$", "0.761", "rev_het_lite_p_agree_majority_wrong", 3),
    (r"hom to 0\.761 for het-lite and$", "0.636", "rev_het_p_agree_majority_wrong", 3),
    (r"consensus structure by heterogeneity exploratory$", "3600", "rev_hom_scoreable", 0),
    (r"config unanimity unan\. wrong pile-on hom$", "0.591", "rev_hom_unanimous_rate", 3),
    (r"unanimity unan\. wrong pile-on hom 0\.591$", "0.058",
     "rev_hom_unanimous_wrong_rate", 3),
    (r"unan\. wrong pile-on hom 0\.591 0\.058$", "0.824",
     "rev_hom_p_agree_majority_wrong", 3),
    (r"pile-on hom 0\.591 0\.058 0\.824 het-lite$", "0.315",
     "rev_het_lite_unanimous_rate", 3),
    (r"hom 0\.591 0\.058 0\.824 het-lite 0\.315$", "0.030",
     "rev_het_lite_unanimous_wrong_rate", 3),
    (r"0\.591 0\.058 0\.824 het-lite 0\.315 0\.030$", "0.761",
     "rev_het_lite_p_agree_majority_wrong", 3),
    (r"0\.824 het-lite 0\.315 0\.030 0\.761 het$", "0.267", "rev_het_unanimous_rate", 3),
    (r"het-lite 0\.315 0\.030 0\.761 het 0\.267$", "0.032",
     "rev_het_unanimous_wrong_rate", 3),
    (r"0\.315 0\.030 0\.761 het 0\.267 0\.032$", "0.636",
     "rev_het_p_agree_majority_wrong", 3),
    (r"no configuration rises reliably above chance$", "0.5",
     "!chance level for a binary directional call", 1),
    # ------------------------------------------------------------------- cross-domain replication
    (r"task we repeated the protocol using$", "537", "mmlu_overall_n_items", 0),
    (r"to this task\. agreement decreases from$", "0.881", "mmlu_overall_kappa_hom", 3),
    (r"decreases from 0\.881 for hom to$", "0.809", "mmlu_overall_kappa_het", 3),
    (r"to 0\.809 for het giving hom-het$", "0.072", "mmlu_overall_d_kappa", 3),
    (r"giving hom-het 0\.072 95 ci$", "0.040", "mmlu_overall_d_kappa_ci_low", 3),
    (r"hom-het 0\.072 95 ci 0\.040$", "0.104", "mmlu_overall_d_kappa_ci_high", 3),
    (r"95 ci 0\.040 0\.104 compared with$", "0.336", "primary_delta_kappa", 3),
    (r"experiment\. error correlation decreases by hom\-het$", "0.393",
     "mmlu_overall_d_phi", 3),
    (r"decreases by hom\-het 0\.393 95 ci$", "0.325", "mmlu_overall_d_phi_ci_low", 3),
    (r"hom-het 0\.393 95 ci 0\.325$", "0.459", "mmlu_overall_d_phi_ci_high", 3),
    (r"95 ci 0\.325 0\.459 compared with$", "0.454",
     "revision_r3_3_error_correlation_scored_d_phi", 3),
    (r"pair have nearly identical member accuracy$", "0.951",
     "mmlu_capability_matched_matched_same_provider_member_accuracy", 3),
    (r"nearly identical member accuracy 0\.951 and$", "0.955",
     "mmlu_capability_matched_matched_cross_provider_member_accuracy", 3),
    (r"0\.955 respectively\. their error correlations are$", "0.954",
     "mmlu_capability_matched_matched_same_provider_phi", 3),
    (r"their error correlations are 0\.954 and$", "0.607",
     "mmlu_capability_matched_matched_cross_provider_phi", 3),
    (r"0\.954 and 0\.607 a difference of$", "0.347",
     "mmlu_capability_matched_matched_d_phi", 3),
    (r"a difference of 0\.347 95 ci$", "0.207",
     "mmlu_capability_matched_matched_d_phi_ci_low", 3),
    (r"difference of 0\.347 95 ci 0\.207$", "0.507",
     "mmlu_capability_matched_matched_d_phi_ci_high", 3),
    (r"to mean agent conviction\. aurc is$", "0.553",
     "revision_r1_1_r3_4_selective_prediction_hom_aurc", 3),
    (r"conviction\. aurc is 0\.553 for hom$", "0.568",
     "revision_r1_1_r3_4_selective_prediction_het_lite_aurc", 3),
    (r"for hom 0\.568 for het-lite and$", "0.554",
     "revision_r1_1_r3_4_selective_prediction_het_aurc", 3),
    # ------------------------------------------------------- capability-matched control (finance)
    (r"three model families\. across the same$", "100",
     "revision_r3_2_clustering_ticker_n_clusters", 0),
    (r"grid the homogeneous baseline produces hom$", "0.552", "control_kappa_hom", 3),
    (r"heterogeneous configuration produces het - sametier$", "0.236",
     "control_kappa_het_sametier", 3),
    (r"the resulting contrast is hom-sametier$", "0.315", "control_delta_kappa", 3),
    (r"contrast is hom-sametier 0\.315 95 ci$", "0.288", "control_ci_low", 3),
    (r"is hom-sametier 0\.315 95 ci 0\.288$", "0.341", "control_ci_high", 3),
    # ------------------------------------------------------------------ temperature sensitivity
    (r"the main operating point of t$", "0.7", "!temperature setting", 1),
    (r"and three independent runs at t$", "0.0", "!temperature setting", 1),
    (r"three independent runs at t 0\.0$", "0.7", "!temperature setting", 1),
    (r"independent runs at t 0\.0 0\.7$", "1.0", "!temperature setting", 1),
    (r"temperature\. the corresponding hom-to-het contrasts are$", "0.299",
     "temp_T00_dk_hom_het", 3),
    (r"corresponding hom-to-het contrasts are 0\.299$", "0.509", "temp_T07_dk_hom_het", 3),
    (r"hom-to-het contrasts are 0\.299 0\.509 and$", "0.385", "temp_T10_dk_hom_het", 3),
    (r"0\.299 0\.509 and 0\.385 at t$", "0.0", "!temperature setting", 1),
    (r"0\.509 and 0\.385 at t 0\.0$", "0.7", "!temperature setting", 1),
    (r"0\.385 at t 0\.0 0\.7 and$", "1.0", "!temperature setting", 1),
    (r"for example hom ranges from approximately$", "0.33", "temp_T00_kappa_hom", 2),
    (r"hom ranges from approximately 0\.33 to$", "0.67", "temp_T07_kappa_hom", 2),
    (r"uniform label distribution whereas at t$", "0.7", "!temperature setting", 1),
    (r"whereas at t 0\.7 and t$", "1.0", "!temperature setting", 1),
    (r"contrast at the main operating point$", "0.509", "temp_T07_dk_hom_het", 3),
    (r"main operating point 0\.509 at t$", "0.7", "!temperature setting", 1),
    (r"0\.7 differs from the full-grid estimate$", "0.336", "primary_delta_kappa", 3),
    (r"2 subgrid whose wide confidence interval$", "0.21", "temp_T07_ci_low", 2),
    (r"subgrid whose wide confidence interval 0\.21$", "0.78", "temp_T07_ci_high", 2),
    (r"het - lite het 95 ci$", "0.0", "!temperature setting, table row label", 1),
    (r"- lite het 95 ci 0\.0$", "0.33", "temp_T00_kappa_hom", 2),
    (r"lite het 95 ci 0\.0 0\.33$", "0.17", "temp_T00_kappa_het_lite", 2),
    (r"het 95 ci 0\.0 0\.33 0\.17$", "0.03", "temp_T00_kappa_het", 2),
    (r"95 ci 0\.0 0\.33 0\.17 0\.03$", "0.30", "temp_T00_dk_hom_het", 2),
    (r"ci 0\.0 0\.33 0\.17 0\.03 0\.30$", "0.16", "temp_T00_ci_low", 2),
    (r"0\.0 0\.33 0\.17 0\.03 0\.30 0\.16$", "0.44", "temp_T00_ci_high", 2),
    (r"0\.33 0\.17 0\.03 0\.30 0\.16 0\.44$", "0.7",
     "!temperature setting, table row label", 1),
    (r"0\.17 0\.03 0\.30 0\.16 0\.44 0\.7$", "0.67", "temp_T07_kappa_hom", 2),
    (r"0\.03 0\.30 0\.16 0\.44 0\.7 0\.67$", "0.38", "temp_T07_kappa_het_lite", 2),
    (r"0\.30 0\.16 0\.44 0\.7 0\.67 0\.38$", "0.16", "temp_T07_kappa_het", 2),
    (r"0\.16 0\.44 0\.7 0\.67 0\.38 0\.16$", "0.51", "temp_T07_dk_hom_het", 2),
    (r"0\.44 0\.7 0\.67 0\.38 0\.16 0\.51$", "0.21", "temp_T07_ci_low", 2),
    (r"0\.7 0\.67 0\.38 0\.16 0\.51 0\.21$", "0.78", "temp_T07_ci_high", 2),
    (r"0\.67 0\.38 0\.16 0\.51 0\.21 0\.78$", "1.0",
     "!temperature setting, table row label", 1),
    (r"0\.38 0\.16 0\.51 0\.21 0\.78 1\.0$", "0.53", "temp_T10_kappa_hom", 2),
    (r"0\.16 0\.51 0\.21 0\.78 1\.0 0\.53$", "0.27", "temp_T10_kappa_het_lite", 2),
    (r"0\.51 0\.21 0\.78 1\.0 0\.53 0\.27$", "0.15", "temp_T10_kappa_het", 2),
    (r"0\.21 0\.78 1\.0 0\.53 0\.27 0\.15$", "0.38", "temp_T10_dk_hom_het", 2),
    (r"0\.78 1\.0 0\.53 0\.27 0\.15 0\.38$", "0.19", "temp_T10_ci_low", 2),
    (r"1\.0 0\.53 0\.27 0\.15 0\.38 0\.19$", "0.54", "temp_T10_ci_high", 2),
    (r"section provides a pre-registered replication on$", "537", "mmlu_overall_n_items", 0),
    # --------------------------------------------------- R3.4 paired equity-clustered CIs
    (r"het agreement contrast\. the contrast is$", "0.485", "pilot_broken_delta_kappa", 3),
    (r"0\.485 under a shared seed and$", "0.113", "pilot_clean_delta_kappa", 3),
    (r"paired equity-clustered bootstrap over the same$", "100",
     "revision_r3_4_paired_cluster_contrasts_pile_on_n_clusters", 0),
    (r"over the same 100 equities using$", "2000", "revision_r3_4_paired_cluster_contrasts_pile_on_draws_used", 0),
    (r"a hom - het difference of$", "0.189", "revision_r3_4_paired_cluster_contrasts_pile_on_delta_hom_het", 3),
    (r"with a 95 confidence interval of$", "0.160", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_low", 3),
    (r"a 95 confidence interval of 0\.160$", "0.216", "revision_r3_4_paired_cluster_contrasts_pile_on_ci_high", 3),
    (r"hom \- het difference is \-$", "0.001",
     "revision_r3_4_paired_cluster_contrasts_aurc_delta_hom_het", 3),
    (r"difference is \-0\.001 95 ci \-$", "0.059", "revision_r3_4_paired_cluster_contrasts_aurc_ci_low", 3),
    (r"difference is \-0\.001 95 ci \-0\.059$", "0.060", "revision_r3_4_paired_cluster_contrasts_aurc_ci_high", 3),
    (r"primary endpoint the interval widens to$", "0.140", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_low", 3),
    (r"endpoint the interval widens to 0\.140$", "0.232", "revision_r3_4_paired_cluster_contrasts_pile_on_two_way_ci_high", 3),
    (r"the corresponding two\-way interval is \-$", "0.113", "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_low", 3),
    (r"the corresponding two\-way interval is \-0\.113$", "0.115",
     "revision_r3_4_paired_cluster_contrasts_aurc_two_way_ci_high", 3),
    # --------------------------------------------- two-way sensitivity on inferential claims
    (r"primary endpoint the interval widens to$", "1.13", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_low", 2),
    (r"endpoint the interval widens to 1\.13$", "3.06", "revision_r1_4_unanimous_incorrect_ratio_two_way_ci_high", 2),
    (r"date dependence the interval widens to$", "0.328",
     "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_low", 3),
    (r"dependence the interval widens to 0\.328$", "0.586",
     "revision_r3_3_error_correlation_scored_d_phi_two_way_ci_high", 3),
    (r"0\.309 95 ci 0\.262 0\.354 two-way$", "0.227",
     "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_low", 3),
    (r"95 ci 0\.262 0\.354 two-way 0\.227$", "0.387",
     "revision_r3_3_error_correlation_strict_d_phi_two_way_ci_high", 3),
    # ------------------------------------ R3.2 two-way sensitivity on the pre-registered endpoints
    (r"of section they remain so at$", "0.208", "contrast_dkappa_hom_hetlite_two_way_ci_low", 3),
    (r"section they remain so at 0\.208$", "0.290",
     "contrast_dkappa_hom_hetlite_two_way_ci_high", 3),
    (r"remain so at 0\.208 0\.290 and$", "0.045",
     "contrast_dkappa_hetlite_het_two_way_ci_low", 3),
    (r"so at 0\.208 0\.290 and 0\.045$", "0.123",
     "contrast_dkappa_hetlite_het_two_way_ci_high", 3),
    (r"0\.341 with a two-way interval of$", "0.270", "control_two_way_ci_low", 3),
    (r"with a two-way interval of 0\.270$", "0.361", "control_two_way_ci_high", 3),
    # ---------------------------------------------- freeze receipts and the relabelled Table 5
    (r"the frozen artifacts and the sha-$", "256", "!algorithm name SHA-256", 0),
    # ---------------------------------------------------------------------------- discussion
    (r"inference cost\. within-ensemble agreement decreases from$", "0.552",
     "kappa_hom", 3),
    (r"0\.552 for the homogeneous configuration to$", "0.215", "kappa_het", 3),
    (r"while inference cost increases by approximately$", "4.4",
     "cost_ratio_het_over_hom", 1),
    (r"unanimous incorrect directional decisions at approximately$", "1.84",
     "revision_r1_4_unanimous_incorrect_ratio", 2),
    # ------------------------------------------------------- collection provenance / retries
    (r"retry accounting the confirmatory grid contains$", "54000", "calls_usable", 0),
    (r"valid outputs\. completing the grid required$", "94566", "capture_requests_total", 0),
    (r"required 94566 api requests\. of the$", "40566",
     "capture_requests_unsuccessful", 0),
    (r"requests\. of the 40566 unsuccessful requests$", "40544",
     "capture_unsuccessful_ratelimit_or_quota", 0),
    (r"were fixed across configurations including temperature$", "0.7",
     "!protocol parameter: sampling temperature, data/configs/config.yaml", 1),
    (r"temperature 0\.7 per-agent seed construction a$", "256",
     "!completion token cap, protocol parameter", 0),
    # ---------------------------------------------------------------------- threats to validity
    (r"substantially higher agreement for same-provider pairs$", "0.80",
     "ms_provider_pair_direction_agreement_descriptiv_openai_openai", 2),
    (r"agreement for same-provider pairs 0\.80 --$", "0.92",
     "ms_provider_pair_direction_agreement_descriptiv_google_google", 2),
    (r"-- 0\.92 than for cross-provider pairs$", "0.43",
     "ms_provider_pair_direction_agreement_descriptiv_google_xai", 2),
    (r"than for cross-provider pairs 0\.43 --$", "0.63",
     "ms_provider_pair_direction_agreement_descriptiv_openai_xai", 2),
    (r"google and produces a contrast of$", "0.315", "control_delta_kappa", 3),
    # ---------------------------------------------------------------------------- conclusion
    (r"of increasing cross-provider heterogeneity\. across a$", "54000", "calls_usable", 0),
    (r"with a primary hom-to-het contrast of$", "0.336", "primary_delta_kappa", 3),
    (r"hom-to-het contrast of 0\.336 95 ci$", "0.304", "primary_ci_low", 3),
    (r"contrast of 0\.336 95 ci 0\.304$", "0.369", "primary_ci_high", 3),
    (r"reduction is accompanied by an approximately$", "4.4",
     "cost_ratio_het_over_hom", 1),
    # ----------------------------------------------------------------- data/code availability
    (r"release i the immutable read-only sha-$", "256", "!algorithm name SHA-256", 0),
    (r"read-only sha-256-stamped raw dataset runs\.csv containing$", "54000",
     "calls_usable", 0),
    (r"keys-free reproduction is available at doi$", "10.24433",
     "!Code Ocean DOI prefix", 5),
    (r"10\.24433 co\.9524962\.v1 \. the dataset sha-$", "256",
     "!algorithm name SHA-256", 0),
    # ----------------------------------------------------------- generative-AI note, biography
    (r"specifically openai s chatgpt gpt-5$", "2025", "!model release year", 0),
    (r"the university of mumbai india in$", "2013", "!degree year, author biography", 0),
    (r"management studies university of mumbai in$", "2016",
     "!degree year, author biography", 0),
    (r"at urbana-champaign urbana il usa in$", "2019",
     "!degree year, author biography", 0),
]


def normalize(raw: str) -> str:
    t = re.sub(r"(?m)(?<!\\)%.*", "", raw)
    t = re.sub(r"\\(?:label|ref|cite[a-z]*|includegraphics|input|url|eqref|doi)\{[^}]*\}",
               " ", t)
    # An ORCID is an identifier, not a quantity -- the same reason \doi{} is stripped above.
    # Declaring its segments (0009, 0007, ...) as bare-string non-results would excuse those
    # digits anywhere in the paper, which is exactly the string-keyed weakness this gate removed.
    t = re.sub(r"ORCID:\s*[0-9X-]+", " ", t)
    t = re.sub(r"(\d)\{,\}(\d)", r"\1\2", t)
    return t


def words_before(t: str, start: int, n: int = 6) -> str:
    pre = t[max(0, start - 200):start]
    pre = re.sub(r"\\[a-zA-Z@]+\*?", " ", pre)
    pre = re.sub(r"[^0-9A-Za-z.\-]+", " ", pre)
    return " ".join(pre.split()[-n:]).lower()


def rounds_to(value: float, lit: str, nd: int, scale: float) -> bool:
    v = abs(value) * scale
    q = Decimal(repr(v)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    if f"{q}" == lit:
        return True
    # an integer claim written without a trailing ".0"
    return nd == 0 and f"{q}".rstrip("0").rstrip(".") == lit


def main() -> int:
    if not CLAIMS.exists():
        print("[binding] claims.json absent -- run make_claims.py")
        return 2
    if not TEX.exists():
        print("[binding] paper/main.tex not published in this copy (capsule layout)")
        return 2
    claims = json.loads(CLAIMS.read_text())
    raw = TEX.read_text()
    t = normalize(raw)

    fails: list[str] = []

    for m in PLACEHOLDER.finditer(t):
        fails.append(f"unsubstituted placeholder {m.group(0)!r} in main.tex "
                     f"...{' '.join(t[max(0, m.start()-70):m.end()].split())[-70:]}")

    occ = [(m.start(), m.group(1), words_before(t, m.start())) for m in LIT.finditer(t)]

    used = Counter()
    bound = 0
    for pos, lit, ctx in occ:
        hits = [i for i, r in enumerate(R)
                if r[1] == lit and re.search(r[0], ctx)]
        if not hits:
            fails.append(f"UNBOUND {lit}  after \"{ctx}\"  -- no rule in check_binding.R "
                         f"says which claim this number is")
            continue
        if len(hits) > 1:
            fails.append(f"AMBIGUOUS {lit} after \"{ctx}\" matches {len(hits)} rules: "
                         f"{[R[i][0] for i in hits]}")
            continue
        i = hits[0]
        used[i] += 1
        rule = R[i]
        target, nd = rule[2], rule[3]
        scale = rule[4] if len(rule) > 4 else 1.0
        bound += 1
        if target.startswith("!"):
            continue
        if target not in claims:
            fails.append(f"{lit} after \"{ctx}\" is bound to {target}, which is not in "
                         f"claims.json")
            continue
        v = claims[target]
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            fails.append(f"{lit} bound to {target}, which is not numeric ({v!r})")
            continue
        if not rounds_to(float(v), lit, nd, scale):
            shown = f"{abs(float(v)) * scale:.6f}".rstrip("0")
            fails.append(f"MISMATCH main.tex says {lit} after \"{ctx}\" but {target} = {v} "
                         f"(= {shown} at the printed scale, {nd}dp)")

    unused = [R[i][0] for i in range(len(R)) if not used[i]]
    for u in unused:
        fails.append(f"UNUSED RULE {u!r} matched nothing -- the sentence it binds has been "
                     f"edited or removed, so its number is no longer gated")

    results = sum(1 for i, r in enumerate(R) if used[i] and not r[2].startswith("!"))
    declared = sum(1 for i, r in enumerate(R) if used[i] and r[2].startswith("!"))
    print(f"[binding] {bound}/{len(occ)} manuscript numbers bound to a named claim or a "
          f"declared non-result ({results} rules bind a claim, {declared} declare a "
          f"non-result; {len(claims)} claims available)")
    for f in fails:
        print(f"  {f}")
    if fails:
        print(f"[binding] {len(fails)} binding failure(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
