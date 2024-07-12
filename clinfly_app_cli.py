import csv
import os
import argparse
import pandas as pd
from utilities.anonymize import (
    get_cities_list,
    get_abbreviation_dict_correction,
    reformat_to_report,
    anonymize_analyzer,
    anonymize_engine,
    add_space_to_comma_endpoint,
    get_list_not_deidentify,
    config_deidentify,
)
from utilities.translate import get_translation_dict_correction, translate_report
from utilities.convert import (
    convert_df_no_header,
    convert_df,
    convert_json,
    convert_list_phenogenius,
    convert_pdf_to_text,
)
from utilities.extract_hpo import add_biometrics, extract_hpo
from utilities.get_model import get_models, get_nlp_marian
import gc


def main():

    print("Code Starting")
    MarianText, _, _ = translate_report(
        Report,
        Last_name,
        First_name,
        nlp_fr,
        marian_fr_en,
        dict_correction,
        dict_abbreviation_correction,
    )
    MarianText_report = reformat_to_report(MarianText, nlp_fr)
    del MarianText

    print("Translation and De-identification")
    (
        MarianText_anonymize_report_analyze,
        analyzer_results_return,
        _,
        _,
    ) = anonymize_analyzer(
        MarianText_report, analyzer, proper_noun, Last_name, First_name
    )

    print(MarianText_anonymize_report_analyze)

    MarianText_anonymize_report_engine = anonymize_engine(
        MarianText_report, analyzer_results_return, engine, nlp_fr
    )

    MarianText_anonymize_report_engine_modif = pd.DataFrame(
        [x for x in MarianText_anonymize_report_engine.split("\n")]
    )

    MarianText_anonymize_report_engine_df = MarianText_anonymize_report_engine_modif
    with open(
        os.path.join(args.result_dir, "Reports", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_translated_and_deindentified_report.txt",
        "w",
    ) as file:
        file.write(
            convert_df_no_header(MarianText_anonymize_report_engine_df).decode("utf-8")
        )
    print(
        "Text file created successfully : "
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_translated_and_deindentified_report.txt"
    )

    print("Summarization")

    MarianText_anonymized_reformat_space = add_space_to_comma_endpoint(
        MarianText_anonymize_report_engine, nlp_fr
    )
    MarianText_anonymized_reformat_biometrics, _ = add_biometrics(
        MarianText_anonymized_reformat_space, nlp_fr
    )
    clinphen, clinphen_unsafe = extract_hpo(MarianText_anonymized_reformat_biometrics)

    del MarianText_anonymize_report_engine
    del MarianText_anonymized_reformat_space
    del MarianText_anonymized_reformat_biometrics

    clinphen_unsafe_check_raw = clinphen_unsafe
    clinphen_unsafe_check_raw["To keep in list"] = False
    clinphen_unsafe_check_raw["Confidence on extraction"] = "low"

    del clinphen_unsafe

    clinphen["Confidence on extraction"] = "high"
    clinphen["To keep in list"] = True

    cols = [
        "HPO ID",
        "Phenotype name",
        "To keep in list",
        "No. occurrences",
        "Earliness (lower = earlier)",
        "Confidence on extraction",
        "Example sentence",
    ]
    clinphen_all = pd.concat([clinphen, clinphen_unsafe_check_raw]).reset_index()
    clinphen_all = clinphen_all[cols]

    clinphen_df = clinphen_all
    clinphen_df_without_low_confidence = clinphen_df[
        clinphen_df["To keep in list"] == True
    ]
    del clinphen
    del clinphen_unsafe_check_raw
    gc.collect()

    with open(
        os.path.join(args.result_dir, "TSV", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_summarized_report.tsv",
        "w",
    ) as file:
        file.write(convert_df(clinphen_df).decode("utf-8"))
    print(
        "Tsv file created successfully : "
        + os.path.join(args.result_dir, "TSV", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_summarized_report.tsv"
    )

    with open(
        os.path.join(args.result_dir, "JSON", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_summarized_report.json",
        "w",
    ) as file:
        file.write(convert_json(clinphen_df_without_low_confidence))
    print(
        "JSON file created successfully : "
        + os.path.join(args.result_dir, "JSON", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_summarized_report.json"
    )

    with open(
        os.path.join(args.result_dir, "TXT", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_summarized_report.txt",
        "w",
    ) as file:
        file.write(convert_list_phenogenius(clinphen_df_without_low_confidence))
    print(
        "Text file created successfully : "
        + os.path.join(args.result_dir, "TXT", "")
        + Report_id
        + "_"
        + Last_name
        + "_"
        + First_name
        + "_summarized_report.txt"
    )


if __name__ == "__main__":

    print("Welcome to the Clinfly app")

    parser = argparse.ArgumentParser(description="Description of clinfly arguments")
    parser.add_argument(
        "--file",
        type=str,
        help="the input file which contains the visits informations",
        required=True,
    )
    parser.add_argument(
        "--language",
        choices=["fr", "es", "de"],
        type=str,
        help="The language of the input : fr, es , de",
        required=True,
    )
    parser.add_argument(
        "--model_dir",
        default=os.path.expanduser("~"),
        type=str,
        help="The directory where the models will be downloaded.",
    )
    parser.add_argument(
        "--result_dir",
        default="Results",
        type=str,
        help="The directory where the results will be placed.",
    )

    args = parser.parse_args()

    if not os.path.exists(args.model_dir):
        os.makedirs(args.model_dir)

    if not os.path.exists(args.result_dir):
        os.makedirs(args.result_dir)

    if not os.path.exists(os.path.join(args.result_dir, "Reports")):
        os.makedirs(os.path.join(args.result_dir, "Reports"))

    if not os.path.exists(os.path.join(args.result_dir, "TSV")):
        os.makedirs(os.path.join(args.result_dir, "TSV"))

    if not os.path.exists(os.path.join(args.result_dir, "JSON")):
        os.makedirs(os.path.join(args.result_dir, "JSON"))

    if not os.path.exists(os.path.join(args.result_dir, "TXT")):
        os.makedirs(os.path.join(args.result_dir, "TXT"))

    print("Language chosen :", args.language)
    models_status = get_models(args.language, args.model_dir)
    dict_correction = get_translation_dict_correction()
    dict_abbreviation_correction = get_abbreviation_dict_correction()
    proper_noun = get_list_not_deidentify()
    cities_list = get_cities_list()
    analyzer, engine = config_deidentify(cities_list)
    nlp_fr, marian_fr_en = get_nlp_marian(args.language)

    file_name = args.file
    Report_id: str
    Last_name: str
    First_name: str
    Report: str

    if os.path.isfile(args.file):
        with open(file_name, 'r') as fichier:
          for ligne in fichier:
            elements = ligne.strip().split('\t')
            Report_id, Last_name, First_name, text_or_link = elements
            print("Report_id:", Report_id)
            print("Last_name:", Last_name)
            print("First_name:", First_name)
            if os.path.exists(text_or_link):
                if text_or_link.lower().endswith('.pdf'):
                    print(f"Processing PDF file: {text_or_link}")
                    Report = convert_pdf_to_text(text_or_link)
                else:
                    print(f"Unsupported file type. Please provide a link to a PDF files.")
            else:
                Report = text_or_link
                print("Report:", Report)
            main()
            print()
    else:
        print("Input is not a file. Please provide a valid input.")
