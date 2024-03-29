import json
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence

import nltk
import pandas as pd
import spacy
import stanza

import streamlit as st
import transformers
from clinphen_src import get_phenotypes_lf
from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from unidecode import unidecode
from utilities.web_utilities import display_page_title, display_sidebar
import gc

# -- Set page config
app_title: str = "ClinFly"

display_page_title(app_title)
display_sidebar()


@dataclass(frozen=True)
class SentenceBoundary:
    text: str
    prefix: str

    def __str__(self):
        return self.prefix + self.text


@dataclass
class SentenceBoundaries:
    def __init__(self) -> None:
        self._sentence_boundaries: List[SentenceBoundary] = []

    @property
    def sentence_boundaries(self):
        return self._sentence_boundaries

    def update_sentence_boundaries(
        self, sentence_boundaries_list: List[SentenceBoundary]
    ):
        self._sentence_boundaries = sentence_boundaries_list
        return self

    def from_doc(self, doc: stanza.Document):
        start_idx = 0
        for sent in doc.sentences:
            self.sentence_boundaries.append(
                SentenceBoundary(
                    text=sent.text,
                    prefix=doc.text[start_idx : sent.tokens[0].start_char],
                )
            )
            start_idx = sent.tokens[-1].end_char
        self.sentence_boundaries.append(
            SentenceBoundary(text="", prefix=doc.text[start_idx:])
        )
        return self

    @property
    def nonempty_sentences(self) -> List[str]:
        return [item.text for item in self.sentence_boundaries if item.text]

    def map_sentence_boundaries(self, d: Dict[str, str]) -> List:
        return SentenceBoundaries().update_sentence_boundaries(
            [
                SentenceBoundary(text=d.get(sb.text, sb.text), prefix=sb.prefix)
                for sb in self.sentence_boundaries
            ]
        )

    def __str__(self) -> str:
        return "".join(map(str, self.sentence_boundaries))


@st.cache_resource(max_entries=5, ttl=3600)
def minibatch(seq, size):
    items = []
    for x in seq:
        items.append(x)
        if len(items) >= size:
            yield items
            items = []
    if items:
        yield items


# @dataclass(frozen=True)
class Translator:
    def __init__(self, source_lang: str, dest_lang: str, use_gpu: bool = False) -> None:
        # self.use_gpu = use_gpu
        self.model_name = "Helsinki-NLP/opus-mt-" + source_lang + "-" + dest_lang
        self.model = transformers.MarianMTModel.from_pretrained(self.model_name)
        # if use_gpu:
        #    self.model = self.model.cuda()
        self.tokenizer = transformers.MarianTokenizer.from_pretrained(self.model_name)
        self.sentencizer = stanza.Pipeline(
            source_lang, processors="tokenize", verbose=False, use_gpu=use_gpu
        )

    def sentencize(self, texts: Sequence[str]) -> List[SentenceBoundaries]:
        return [
            SentenceBoundaries().from_doc(doc=self.sentencizer.process(text))
            for text in texts
        ]

    def translate(
        self, texts: Sequence[str], batch_size: int = 10, truncation=True
    ) -> Sequence[str]:
        if isinstance(texts, str):
            raise ValueError("Expected a sequence of texts")
        text_sentences = self.sentencize(texts)
        translations = {
            sent: None for text in text_sentences for sent in text.nonempty_sentences
        }

        for text_batch in minibatch(
            sorted(translations, key=len, reverse=True), batch_size
        ):
            tokens = self.tokenizer(
                text_batch, return_tensors="pt", padding=True, truncation=truncation
            )
            # if self.use_gpu:
            #    tokens = {k:v.cuda() for k, v in tokens.items()}
            translate_tokens = self.model.generate(**tokens)
            translate_batch = [
                self.tokenizer.decode(t, skip_special_tokens=True)
                for t in translate_tokens
            ]
            for text, translated in zip(text_batch, translate_batch):
                translations[text] = translated

        return [
            str(text.map_sentence_boundaries(translations)) for text in text_sentences
        ]


@st.cache_resource(max_entries=5, ttl=3600)
def get_models():
    stanza.download("fr")
    stanza.download("de")
    # stanza.download("it")
    stanza.download("es")
    Translator("fr", "en")
    Translator("de", "en")
    # Translator("it", "en")
    Translator("es", "en")
    try:
        nltk.data.find("omw-1.4")
    except LookupError:
        nltk.download("omw-1.4")
    try:
        nltk.data.find("wordnet")
    except LookupError:
        nltk.download("wordnet")

    spacy_model_name = "en_core_web_lg"
    if not spacy.util.is_package(spacy_model_name):
        spacy.cli.download(spacy_model_name)
    else:
        print(spacy_model_name + " already downloaded")
    return "Done"


@st.cache_resource(max_entries=5, ttl=3600)
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


@st.cache_resource(max_entries=5, ttl=3600)
def get_list_not_deidentify():
    nom_propre_data = pd.read_csv(
        "data/exception_list_anonymization.tsv", sep="\t", header=None
    ).astype(str)

    drug_data = pd.read_csv("data/drug_name.tsv", sep="\t", header=None).astype(str)

    gene_data = pd.read_csv("data/gene_name.tsv", sep="\t", header=None).astype(str)

    nom_propre_list = (
        nom_propre_data[0].to_list()
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
    nom_propre = [x.lower() for x in nom_propre_list]

    del nom_propre_data
    del drug_data
    del gene_data
    del nom_propre_list
    return nom_propre


@st.cache_resource(max_entries=5, ttl=3600)
def config_deidentify():
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


@st.cache_resource(max_entries=5, ttl=3600)
def get_nlp_marian(source_lang):
    nlp_fr = stanza.Pipeline(source_lang, processors="tokenize")
    marian_fr_en = Translator(source_lang, "en")
    return nlp_fr, marian_fr_en


# @st.cache_resource()
# def get_nlp_en():
#    nlp_en = stanza.Pipeline("en", processors="tokenize")
#    return nlp_en


@st.cache_data(max_entries=5, ttl=3600)
def anonymize_analyzer(MarianText_letter, _analyzer, nom_propre, nom, prenom):
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
            if word.lower().strip() in nom_propre:
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
                        "name": nom,
                        "surname": prenom,
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
                        "name": nom,
                        "surname": prenom,
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
                    "name": nom,
                    "surname": prenom,
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


@st.cache_data(max_entries=5, ttl=3600)
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
    return reformat_to_letter(result.text, _nlp)


@st.cache_data(max_entries=10, ttl=3600)
def add_space_to_comma(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\,)(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " , ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=10, ttl=3600)
def add_space_to_endpoint(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\.)(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " . ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=10, ttl=3600)
def add_space_to_leftp(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\()(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ( ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=10, ttl=3600)
def add_space_to_rightp(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\))(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ) ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=10, ttl=3600)
def add_space_to_stroph(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(')(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ' ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=10, ttl=3600)
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


@st.cache_resource(max_entries=5, ttl=3600)
def get_abbreviation_dict_correction():
    # dict_correction = {}
    with open("data/fr_abbreviations.json", "r") as outfile:
        hpo_abbreviations = json.load(outfile)
    return hpo_abbreviations  # dict_correction


@st.cache_resource(max_entries=5, ttl=3600)
def get_translation_dict_correction():
    dict_correction_FRspec = {
        "PC": "head circumference",
        "palatine slot": "cleft palate",
        "ASD": "autism",
        "ADHD": "attention deficit hyperactivity disorder",
        "IUGR": "intrauterin growth retardation",
        "QI": "IQ ",
        "QIT": "FSIQ ",
        "ITQ": "FSIQ ",
        "DS": "SD",
        "FOP": "patent foramen ovale",
        "PFO": "patent foramen ovale",
        "ARCF": "fetal distress",
        "\n": " ",
        "associated": "with",
        "Mr.": "Mr",
        "Mrs.": "Mrs",
    }

    dict_correction = {}
    for key, value in dict_correction_FRspec.items():
        dict_correction[" " + key + " "] = " " + value + " "

    with open("data/hp_fr_en_translated_marian_review_lwg.json", "r") as outfile:
        hpo_translated = json.load(outfile)

    for key, value in hpo_translated.items():
        dict_correction[" " + key + " "] = " " + value + " "

    with open("data/fr_abbreviations_translation.json", "r") as outfile:
        hpo_translated_abbreviations = json.load(outfile)

    for key, value in hpo_translated_abbreviations.items():
        dict_correction[" " + key + " "] = " " + value + " "

    del hpo_translated
    del hpo_translated_abbreviations
    return dict_correction


@st.cache_resource(max_entries=5, ttl=3600)
def change_name_patient_abbreviations(courrier, nom, prenom, abbreviations_dict):
    courrier_name = courrier

    dict_correction_name_abbreviations = {
        "M.": "M",
        "Mme.": "Mme",
        "Mlle.": "Mlle",
        "Dr.": "Docteur",
        "Dr": "Docteur",
        "Pr.": "Professeur",
        "Pr": "Professeur",
    }

    for firstname in prenom.split():
        dict_correction_name_abbreviations[firstname] = "CAS"
    for lastname in nom.split():
        dict_correction_name_abbreviations[lastname] = "INDEX"
    for key, value in abbreviations_dict.items():
        dict_correction_name_abbreviations[key] = value  # + " [" + key + "]"

    list_replaced = []
    splitted_courrier = courrier_name.replace("\n", " ").split(" ")
    replaced_courrier = []
    for i in splitted_courrier:
        append_word = i
        replace_word = None
        for key, value in dict_correction_name_abbreviations.items():
            i_check = i.lower().strip().replace(",", "").replace(".", "")
            if i_check == key.lower().strip():
                to_replace = i.strip().replace(",", "").replace(".", "")
                replace_word = value
                if i_check == nom or i_check == prenom:
                    list_replaced.append(
                        {
                            "name": nom,
                            "surname": prenom,
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
                            "name": nom,
                            "surname": prenom,
                            "type": "abbreviations",
                            "value": i.strip().replace(",", "").replace(".", ""),
                            "correction": value,
                            "lf_detected": True,
                            "manual_validation": True,
                        }
                    )
        if replace_word:
            append_word = append_word.replace(to_replace, replace_word)
        replaced_courrier.append(append_word)
    del dict_correction_name_abbreviations
    del splitted_courrier
    return " ".join(replaced_courrier), list_replaced


@st.cache_resource(max_entries=5, ttl=3600)
def translate_marian(courrier_name, _nlp, _marian_fr_en):
    list_of_sentence = []
    for sentence in _nlp.process(courrier_name).sentences:
        list_of_sentence.append(sentence.text)
    MarianText_raw = "\n".join(_marian_fr_en.translate(list_of_sentence))
    del list_of_sentence
    return MarianText_raw


@st.cache_data(max_entries=5, ttl=3600)
def correct_marian(MarianText_space, dict_correction, nom, prenom):
    MarianText = MarianText_space
    list_replaced = []
    for key, value in dict_correction.items():
        if key in MarianText:
            list_replaced.append(
                {
                    "name": nom,
                    "surname": prenom,
                    "type": "marian_correction",
                    "value": key,
                    "correction": value,
                    "lf_detected": True,
                    "manual_validation": True,
                }
            )
            MarianText = MarianText.replace(key, value)
    return MarianText, list_replaced


@st.cache_data(max_entries=5, ttl=3600)
def translate_letter(
    courrier, nom, prenom, _nlp, _marian_fr_en, dict_correction, abbreviation_dict
):
    courrier_name, list_replaced_abb_name = change_name_patient_abbreviations(
        courrier, nom, prenom, abbreviation_dict
    )
    MarianText_raw = translate_marian(courrier_name, _nlp, _marian_fr_en)
    MarianText_space = add_space_to_comma_endpoint(MarianText_raw, _nlp)
    MarianText, list_replaced = correct_marian(
        MarianText_space, dict_correction, nom, prenom
    )
    del MarianText_raw
    del MarianText_space
    return MarianText, list_replaced, list_replaced_abb_name


@st.cache_data(max_entries=10, ttl=3600)
def reformat_to_letter(text, _nlp):
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


@st.cache_data(max_entries=10, ttl=3600)
def convert_df(df):
    return df.dropna(how="all").to_csv(sep="\t", index=False).encode("utf-8")


@st.cache_data(max_entries=10, ttl=3600)
def convert_df_no_header(df):
    return (
        df.dropna(how="all").to_csv(sep="\t", index=False, header=None).encode("utf-8")
    )


@st.cache_data(max_entries=10, ttl=3600)
def convert_json(df):
    dict_return = {"features": []}
    df_check = df.dropna(subset=["HPO ID", "Phenotype name"])
    if len(df_check) > 0:
        df_dict_list = df[["HPO ID", "Phenotype name"]].to_dict(orient="index")
        for key, value in df_dict_list.items():
            dict_return["features"].append(
                {
                    "id": value["HPO ID"],
                    "observed": "yes",
                    "label": value["Phenotype name"],
                    "type": "phenotype",
                }
            )
        return json.dumps(dict_return)
    else:
        return json.dumps(dict_return)


@st.cache_data(max_entries=10, ttl=3600)
def convert_list_phenogenius(df):
    df_check = df.dropna(subset=["HPO ID", "Phenotype name"])
    if len(df_check) > 0:
        return ",".join(df_check["HPO ID"].to_list())
    else:
        return "No HPO in letters."


@st.cache_data(max_entries=5, ttl=3600)
def add_biometrics(text, _nlp):
    cutsentence_with_biometrics = []
    cutsentence = []
    additional_terms = []
    for sentence in _nlp.process(text).sentences:
        cutsentence.append(sentence.text)
    keep_element = ["cm", "kg", "qit", "qi"]
    for sentence in cutsentence:
        if any(ext in sentence.lower() for ext in keep_element):
            if "SD" in sentence or "DS" in sentence:
                sentence = sentence.replace("DS", "SD")
                try:
                    kg_sd = re.findall("kg(.*?)sd", sentence.lower())[0]
                    num_kg_sd = re.findall("\(\s*([-+].?\d+(?:\.\d+)?)\s*", kg_sd)[0]
                    # print(kg_sd)
                    kg_sd = float(num_kg_sd)
                    print(kg_sd)
                    if kg_sd >= 2:
                        additional_terms.append("Increased body weight")
                    if kg_sd <= -2:
                        additional_terms.append("Decreased body weight")
                except:
                    print("Incorrect weight recognition pattern")
                    print(sentence)
                try:
                    if "is" in sentence.lower():
                        height_sd_alpha = re.findall("\ is(.*?)d", sentence.lower())[0]
                        if "cm" not in height_sd_alpha:
                            height_sd_raw = height_sd_alpha
                    if "easure" in sentence.lower():
                        height_sd_raw = re.findall("easure(.*?)d", sentence.lower())[0]
                        print(height_sd_raw)
                    height_sd = re.findall("m(.*?)s", height_sd_raw)[0]
                    print(height_sd)
                    num_height_sd = re.findall(
                        "\(\s*([-+].?\d+(?:\.\d+)?)\s*", height_sd
                    )[0]
                    height_sd = float(num_height_sd)
                    print(height_sd)
                    if height_sd >= 2:
                        additional_terms.append("Tall stature")
                    if height_sd <= -2:
                        additional_terms.append("Short stature")
                except:
                    print("Incorrect height recognition pattern")
                    print(sentence)
                try:
                    pc_sd_raw = (
                        re.findall("head(.*?)d", sentence.lower())[0]
                        .replace("(", "")
                        .replace(")", "")
                        .replace(" ", "")
                    )
                    pc_sd = re.findall("cm(.*?)s", pc_sd_raw)[0]
                    num_pc_sd = re.findall("\(\s*([-+].?\d+(?:\.\d+)?)\s*", pc_sd)[0]
                    pc_sd = float(num_pc_sd)
                    print(pc_sd)
                    if pc_sd >= 2:
                        additional_terms.append("Macrocephaly")
                    elif pc_sd <= -2:
                        additional_terms.append("Microcephaly")
                except:
                    print("Incorrect head circumference recognition pattern")
                    print(sentence)
                print(additional_terms)
            if "FSIQ" in sentence or "IQ" in sentence:
                try:
                    iq_score = re.findall("iq.*?(\d.*?)\D", sentence.lower())[0]
                    iq_score = float(iq_score)
                    print(iq_score)
                    if iq_score >= 70 and iq_score < 84:
                        additional_terms.append("Intellectual disability, borderline")
                    elif iq_score >= 50 and iq_score < 69:
                        additional_terms.append("Intellectual disability, mild")
                    elif iq_score >= 35 and iq_score < 49:
                        additional_terms.append("Intellectual disability, moderate")
                    elif iq_score >= 20 and iq_score < 34:
                        additional_terms.append("Intellectual disability, severe")
                    elif iq_score < 20:
                        additional_terms.append("Intellectual disability, profound")
                    print(additional_terms)
                except:
                    print("Incorrect IQ recognition pattern")
                    print(sentence)
            cutsentence_with_biometrics.append(
                sentence + " This means " + ", ".join(additional_terms) + "."
            )
        else:
            cutsentence_with_biometrics.append(sentence)
    print(cutsentence_with_biometrics)
    cutsentence_with_biometrics_return = [
        i for i in cutsentence_with_biometrics if i != "."
    ]
    del cutsentence_with_biometrics
    del cutsentence
    del keep_element
    return " ".join(cutsentence_with_biometrics_return), additional_terms


# @profile
@st.cache_data(max_entries=5, ttl=3600)
def main_function(inputStr):
    hpo_to_name = get_phenotypes_lf.getNames()
    returnString, returnStringUnsafe = get_phenotypes_lf.extract_phenotypes(
        inputStr, hpo_to_name
    )
    returnDf = get_phenotypes_lf.get_dataframe_from_clinphen(returnString)
    returnDfUnsafe = get_phenotypes_lf.get_dataframe_from_clinphen(returnStringUnsafe)
    del hpo_to_name
    del returnString
    del returnStringUnsafe
    return returnDf, returnDfUnsafe


models_status = get_models()
cities_list = get_cities_list()
dict_correction = get_translation_dict_correction()
dict_abbreviation_correction = get_abbreviation_dict_correction()
nom_propre = get_list_not_deidentify()
analyzer, engine = config_deidentify()


source_lang = st.selectbox(
    "Which is the language of the letter :fr: :es: :de: ?", ("fr", "es", "de")  # "it"
)

nlp_fr, marian_fr_en = get_nlp_marian(source_lang)

if "load_state" not in st.session_state:
    st.session_state.load_state = False

with st.form("my_form"):
    c1, c2 = st.columns(2)
    with c1:
        nom = st.text_input("Last name", "Doe", key="name")
    with c2:
        prenom = st.text_input("First name", "John", key="surname")
    courrier = st.text_area(
        "Paste medical letter",
        "Chers collegues, j'ai recu en consultation M. John Doe né le 14/07/1789 pour une fièvre récurrente et une maladie de Crohn. Il a pour antécédent des epistaxis recurrents. Parmi les antécédants familiaux, sa maman a présenté un cancer des ovaires. Il mesure 1.90 m (+2.5  DS),  pèse 93 kg (+3.6 DS) et son PC est à 57 cm (+0DS) ...",
        height=200,
        key="letter",
    )

    submit_button = st.form_submit_button(label="Submit")


if submit_button or st.session_state.load_state:
    st.session_state.load_state = True
    MarianText, list_replaced, list_replaced_abb_name = translate_letter(
        courrier,
        nom,
        prenom,
        nlp_fr,
        marian_fr_en,
        dict_correction,
        dict_abbreviation_correction,
    )
    MarianText_letter = reformat_to_letter(MarianText, nlp_fr)
    del MarianText

    st.subheader("Translation and De-identification")
    (
        MarianText_anonymize_letter_analyze,
        analyzer_results_return,
        analyzer_results_keep,
        analyzer_results_saved,
    ) = anonymize_analyzer(MarianText_letter, analyzer, nom_propre, nom, prenom)

    st.caption(MarianText_anonymize_letter_analyze)

    MarianText_anonymize_letter_engine = anonymize_engine(
        MarianText_letter, analyzer_results_return, engine, nlp_fr
    )

    MarianText_anonymize_letter_engine_modif = pd.DataFrame(
        [x for x in MarianText_anonymize_letter_engine.split("\n")]
    )
    MarianText_anonymize_letter_engine_modif.columns = [
        "Modify / curate the automatically translated and de-identified letter before downloading:"
    ]
    MarianText_anonymize_letter_engine_df = st.experimental_data_editor(
        MarianText_anonymize_letter_engine_modif,
        num_rows="dynamic",
        key="letter_editor",
        use_container_width=True,
    )

    st.caption("Modify cells above 👆 or even ➕ add rows, before downloading 👇")

    st.download_button(
        "Download translated and de-identified letter",
        convert_df_no_header(MarianText_anonymize_letter_engine_df),
        nom + "_" + prenom + "_translated_and_deindentified_letter.txt",
        "text",
        key="download-translation-deindentification",
    )

    st.subheader("Summarization")

    MarianText_anonymized_reformat_space = add_space_to_comma_endpoint(
        MarianText_anonymize_letter_engine, nlp_fr
    )
    MarianText_anonymized_reformat_biometrics, additional_terms = add_biometrics(
        MarianText_anonymized_reformat_space, nlp_fr
    )
    clinphen, clinphen_unsafe = main_function(MarianText_anonymized_reformat_biometrics)

    del MarianText_anonymize_letter_engine
    del MarianText_anonymized_reformat_space
    del MarianText_anonymized_reformat_biometrics

    clinphen_unsafe_check_raw = clinphen_unsafe
    # clinphen_unsafe_check_raw["name"] = nom
    # clinphen_unsafe_check_raw["surname"] = prenom
    clinphen_unsafe_check_raw["To keep in list"] = False
    clinphen_unsafe_check_raw["Confidence on extraction"] = "low"

    del clinphen_unsafe

    # clinphen["name"] = nom
    # clinphen["surname"] = prenom
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
    clinphen_df = st.experimental_data_editor(
        clinphen_all, num_rows="dynamic", key="data_editor"
    )
    clinphen_df_without_low_confidence = clinphen_df[clinphen_df["To keep in list"]== True]
    del clinphen
    del clinphen_unsafe_check_raw
    gc.collect()

    st.caption(
        "Modify cells above 👆, click ☐ to keep low confidence symptoms in list, or even ➕ add rows, before downloading 👇"
    )

    st.download_button(
        "Download summarized letter in HPO CSV format",
        convert_df(clinphen_df),
        nom + "_" + prenom + "_summarized_letter.tsv",
        "text/csv",
        key="download-summarization",
    )

    st.download_button(
        "Download summarized letter in Phenotips JSON format (hygen compatible)",
        convert_json(clinphen_df_without_low_confidence),
        nom + "_" + prenom + "_summarized_letter.json",
        "json",
        key="download-summarization-json",
    )

    st.download_button(
        "Download summarized letter in PhenoGenius list of HPO format",
        convert_list_phenogenius(clinphen_df_without_low_confidence),
        nom + "_" + prenom + "_summarized_letter.txt",
        "text",
        key="download-summarization-phenogenius",
    )
