import re
import json
from unidecode import unidecode
import pandas as pd
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
import streamlit as st
from .web_utilities import st_cache_data_if, st_cache_resource_if, supported_cache



@st_cache_data_if(supported_cache, max_entries=5, ttl=3600)
def anonymize_analyzer(MarianText_letter, _analyzer, proper_noun, Last_name, First_name):
    MarianText_anonymize_letter = MarianText_letter
    # st.write(MarianText_anonymize_letter)
    analyzer_results_keep = []
    analyzer_results_return = []
    analyzer_results_saved = []
    analyzer_results = _analyzer.analyze(
        text=MarianText_letter,
        language="en",
        entities=["DATE_TIME", "PERSON", "FRENCH_CITY"],
        allow_list=[
            "evening",
            "day",
            "the day",
            "the age of",
            "age",
            "years",
            "week",
            "years old",
            "months",
            "hours",
            "night",
            "noon",
            "nights",
            "tomorrow",
            "today",
            "yesterday",
        ],
    )
    len_to_add = 0
    analyser_results_to_sort = {}
    i = 0
    detect_duplicated = []
    for element in analyzer_results:
        if element.start not in detect_duplicated:
            analyser_results_to_sort[i] = element.start
            detect_duplicated.append(element.start)
        else:
            pass
        i = i + 1
    sorted_tuples = sorted(analyser_results_to_sort.items(), key=lambda x: x[1])
    sorted_dict = {k: v for k, v in sorted_tuples}
    print(sorted_dict)
    exception_list_presidio = ["age", "year", "month", "day", "hour", "week"]

    for element_raw in sorted_dict:
        element = analyzer_results[element_raw]
        word = MarianText_letter[element.start : element.end]
        exception_detected = [e for e in exception_list_presidio if e in word.lower()]
        if word.count("/") == 1 or word.count("/") > 2:
            exception_detected.append("/ or ///")
        if len(exception_detected) == 0:
            if word.lower().strip() in proper_noun:
                word_to_replace = (
                    "**:green[" + word + "]** `[" + element.entity_type + "]`"
                )
                MarianText_anonymize_letter = (
                    MarianText_anonymize_letter[: element.start + len_to_add]
                    + word_to_replace
                    + MarianText_anonymize_letter[element.end + len_to_add :]
                )
                analyzer_results_saved.append(
                    {
                        "name": Last_name,
                        "surname": First_name,
                        "type": "deidentification",
                        "value": word,
                        "correction": element.entity_type,
                        "lf_detected": False,
                        "manual_validation": False,
                    }
                )
            # analyzer_results_saved.append(str(element) + ", word:" + word)
            else:
                word_to_replace = (
                    "**:red[" + word + "]** `[" + element.entity_type + "]`"
                )
                MarianText_anonymize_letter = (
                    MarianText_anonymize_letter[: element.start + len_to_add]
                    + word_to_replace
                    + MarianText_anonymize_letter[element.end + len_to_add :]
                )
                analyzer_results_keep.append(
                    {
                        "name": Last_name,
                        "surname": First_name,
                        "type": "deidentification",
                        "value": word,
                        "correction": element.entity_type,
                        "lf_detected": True,
                        "manual_validation": True,
                    }
                )
                # analyzer_results_keep.append(str(element) + ", word:" + word)
                analyzer_results_return.append(element)
            len_to_add = len_to_add + len(word_to_replace) - len(word)
        else:
            analyzer_results_saved.append(
                {
                    "name": Last_name,
                    "surname": First_name,
                    "type": "deidentification",
                    "value": word,
                    "correction": element.entity_type,
                    "lf_detected": False,
                    "manual_validation": False,
                }
            )
            # analyzer_results_saved.append(str(element) + ", word:" + word)
    del analyzer_results
    del len_to_add
    del exception_list_presidio
    del analyser_results_to_sort
    del sorted_tuples
    del sorted_dict

    return (
        MarianText_anonymize_letter,
        analyzer_results_return,
        analyzer_results_keep,
        analyzer_results_saved,
    )


@st_cache_data_if(supported_cache, max_entries=5, ttl=3600)
def anonymize_engine(MarianText_letter, _analyzer_results_return, _engine, _nlp):
    result = _engine.anonymize(
        text=MarianText_letter,
        analyzer_results=_analyzer_results_return,
        operators={
            "PERSON": OperatorConfig("replace", {"new_value": ""}),
            "LOCATION": OperatorConfig("replace", {"new_value": ""}),
            "FRENCH_CITY": OperatorConfig("replace", {"new_value": ""}),
        },
    )
    return reformat_to_report(result.text, _nlp)


@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def add_space_to_comma(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\,)(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " , ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def add_space_to_endpoint(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\.)(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " . ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def add_space_to_leftp(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\()(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ( ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def add_space_to_rightp(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\))(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ) ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def add_space_to_stroph(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(')(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ' ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def add_space_to_comma_endpoint(texte, _nlp):
    text_fr_comma = add_space_to_comma(texte, _nlp)
    text_fr_comma_endpoint = add_space_to_endpoint(text_fr_comma, _nlp)
    text_fr_comma_endpoint_leftpc = add_space_to_leftp(text_fr_comma_endpoint, _nlp)
    text_fr_comma_endpoint_leftpc_right_pc = add_space_to_rightp(
        text_fr_comma_endpoint_leftpc, _nlp
    )
    del text_fr_comma
    del text_fr_comma_endpoint
    del text_fr_comma_endpoint_leftpc
    return text_fr_comma_endpoint_leftpc_right_pc


@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def get_abbreviation_dict_correction():
    # dict_correction = {}
    with open("data/fr_abbreviations.json", "r") as outfile:
        hpo_abbreviations = json.load(outfile)
    return hpo_abbreviations  # dict_correction



@st_cache_data_if(supported_cache, max_entries=10, ttl=3600)
def reformat_to_report(text, _nlp):
    cutsentence = []
    for sentence in _nlp.process(text).sentences:
        cutsentence.append(
            sentence.text.replace(" ,", ",")
            .replace(" .", ".")
            .replace(" )", ")")
            .replace(" (", "(")
            .replace(" '", "'")
        )
    return "  \n".join(cutsentence)


@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def get_cities_list():
    cities = pd.read_csv("data/proper_noun_location_sort.csv")
    cities.columns = ["ville"]
    whole_cities_patterns = []
    list_cities = cities["ville"].to_list()
    for element in list_cities:
        whole_cities_patterns.append(element)
        whole_cities_patterns.append(element.lower().capitalize())
        whole_cities_patterns.append(element.upper())
        whole_cities_patterns.append(unidecode(element))
        whole_cities_patterns.append(unidecode(element).lower().capitalize())
        whole_cities_patterns.append(unidecode(element).upper())
    del cities
    del list_cities
    return whole_cities_patterns


@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def get_list_not_deidentify():
    proper_noun_data = pd.read_csv(
        "data/exception_list_anonymization.tsv", sep="\t", header=None
    ).astype(str)

    drug_data = pd.read_csv("data/drug_name.tsv", sep="\t", header=None).astype(str)

    gene_data = pd.read_csv("data/gene_name.tsv", sep="\t", header=None).astype(str)

    proper_noun_list = (
        proper_noun_data[0].to_list()
        + drug_data[0].to_list()
        + gene_data[0].to_list()
        + [
            "PN",
            "TN",
            "SD",
            "PCN",
            "cher",
            "chere",
            "CAS",
            "INDEX",
            "APGAR",
            "M",
            "Ms",
            "Mr",
            "Behçet",
            "hypoacousia",
        ]
    )
    proper_noun = [x.lower() for x in proper_noun_list]

    del proper_noun_data
    del drug_data
    del gene_data
    del proper_noun_list
    return proper_noun



@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def change_name_patient_abbreviations(Report, Last_name, First_name, abbreviations_dict):
    Report_name = Report

    dict_correction_name_abbreviations = {
        "M.": "M",
        "Mme.": "Mme",
        "Mlle.": "Mlle",
        "Dr.": "Docteur",
        "Dr": "Docteur",
        "Pr.": "Professeur",
        "Pr": "Professeur",
    }

    for firstname in First_name.split():
        dict_correction_name_abbreviations[firstname] = "CAS"
    for lastname in Last_name.split():
        dict_correction_name_abbreviations[lastname] = "INDEX"
    for key, value in abbreviations_dict.items():
        dict_correction_name_abbreviations[key] = value  # + " [" + key + "]"

    list_replaced = []
    splitted_Report = Report_name.replace("\n", " ").split(" ")
    replaced_Report = []
    for i in splitted_Report:
        append_word = i
        replace_word = None
        for key, value in dict_correction_name_abbreviations.items():
            i_check = i.lower().strip().replace(",", "").replace(".", "")
            if i_check == key.lower().strip():
                to_replace = i.strip().replace(",", "").replace(".", "")
                replace_word = value
                if i_check == Last_name or i_check == First_name:
                    list_replaced.append(
                        {
                            "name": Last_name,
                            "surname": First_name,
                            "type": "index_case",
                            "value": i.strip().replace(",", "").replace(".", ""),
                            "correction": value,
                            "lf_detected": True,
                            "manual_validation": True,
                        }
                    )
                else:
                    list_replaced.append(
                        {
                            "name": Last_name,
                            "surname": First_name,
                            "type": "abbreviations",
                            "value": i.strip().replace(",", "").replace(".", ""),
                            "correction": value,
                            "lf_detected": True,
                            "manual_validation": True,
                        }
                    )
        if replace_word:
            append_word = append_word.replace(to_replace, replace_word)
        replaced_Report.append(append_word)
    del dict_correction_name_abbreviations
    del splitted_Report
    return " ".join(replaced_Report), list_replaced


@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def config_deidentify(cities_list):
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }

    # Create NLP engine based on configuration
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    frcity_recognizer = PatternRecognizer(
        supported_entity="FRENCH_CITY", deny_list=cities_list
    )

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    analyzer.registry.add_recognizer(frcity_recognizer)
    engine = AnonymizerEngine()
    del configuration
    del provider
    del nlp_engine
    del frcity_recognizer
    return analyzer, engine