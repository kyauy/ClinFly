from __future__ import annotations  # For Python 3.7
import streamlit as st
from PIL import Image
import pandas as pd
import re
import json
import nltk
import stanza
from dataclasses import dataclass
from typing import List
import transformers
from typing import Sequence
import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult, OperatorConfig
import subprocess
from clinphen_src import get_phenotypes_lf


# -- Set page config
apptitle = "Linguo Franca"

st.set_page_config(page_title=apptitle, page_icon=":incoming_envelope:", layout="wide")

# -- Set Sidebar
image_pg = Image.open("img/logo_300x.png")
st.sidebar.image(image_pg, caption=None, width=200)
st.sidebar.title("Linguo Franca")

st.sidebar.header(
    "Share medical consultation letter automatically translated, de-identified and summarized using deep learning"
)

st.sidebar.markdown(
    """
 Currently only working from :fr: to :gb:.  

 If any questions or suggestions, please contact: [kevin.yauy@chu-montpellier.fr](kevin.yauy@chu-montpellier.fr) and [lucas.gauthier@chu-lyon.fr](lucas.gauthier@chu-lyon.fr) 

 Code source is available in GitHub:
 [https://github.com/kyauy/Linguo-Franca](https://github.com/kyauy/Linguo-Franca)

 Linguo Franca is an initiative from:
"""
)
image_univ = Image.open("img/logosfacmontpellier.png")
st.sidebar.image(image_univ, caption=None, width=190)

image_chu = Image.open("img/CHU-montpellier.png")
st.sidebar.image(image_chu, caption=None, width=95)


@st.cache_resource(max_entries=30)
def get_models():
    nltk.download("omw-1.4")
    nltk.download('wordnet')
    stanza.download("fr")
    #stanza.download("en")
    spacy_model_name = "en_core_web_lg"
    if not spacy.util.is_package(spacy_model_name):
        spacy.cli.download(spacy_model_name)
    else:
        print(spacy_model_name + " already downloaded")
    return "Done"


@st.cache_data(max_entries=30)
def get_list_not_deidentify():
    nom_propre_data = pd.read_csv(
        "data/exception_list_anonymization.tsv", sep="\t", header=None
    ).astype(str)

    drug_data = pd.read_csv(
        "data/drug_name.tsv", sep="\t", header=None
    ).astype(str)

    gene_data = pd.read_csv(
        "data/gene_name.tsv", sep="\t", header=None
    ).astype(str)

    nom_propre_list = nom_propre_data[0].to_list() + drug_data[0].to_list() + gene_data[0].to_list() + [
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
    nom_propre = [x.lower() for x in nom_propre_list]
    return nom_propre


@st.cache_resource(max_entries=30)
def config_deidentify():
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }

    # Create NLP engine based on configuration
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    engine = AnonymizerEngine()
    return analyzer, engine


@st.cache_resource(max_entries=30)
def get_nlp_marian():
    nlp_fr = stanza.Pipeline("fr", processors="tokenize")
    marian_fr_en = Translator("fr", "en")
    return nlp_fr, marian_fr_en

#@st.cache_resource()
#def get_nlp_en():
#    nlp_en = stanza.Pipeline("en", processors="tokenize")
#    return nlp_en

@dataclass(frozen=True)
class SentenceBoundary:
    text: str
    prefix: str

    def __str__(self):
        return self.prefix + self.text


@dataclass(frozen=True)
class SentenceBoundaries:
    sentence_boundaries: List[SentenceBoundary]

    @classmethod
    def from_doc(cls, doc: stanza.Document) -> SentenceBoundaries:
        sentence_boundaries = []
        start_idx = 0
        for sent in doc.sentences:
            sentence_boundaries.append(
                SentenceBoundary(
                    text=sent.text,
                    prefix=doc.text[start_idx : sent.tokens[0].start_char],
                )
            )
            start_idx = sent.tokens[-1].end_char
        sentence_boundaries.append(
            SentenceBoundary(text="", prefix=doc.text[start_idx:])
        )
        return cls(sentence_boundaries)

    @property
    def nonempty_sentences(self) -> List[str]:
        return [item.text for item in self.sentence_boundaries if item.text]

    def map(self, d: dict[str, str]) -> SentenceBoundaries:
        return SentenceBoundaries(
            [
                SentenceBoundary(text=d.get(sb.text, sb.text), prefix=sb.prefix)
                for sb in self.sentence_boundaries
            ]
        )

    def __str__(self) -> str:
        return "".join(map(str, self.sentence_boundaries))


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
            SentenceBoundaries.from_doc(self.sentencizer.process(text))
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
            for (text, translated) in zip(text_batch, translate_batch):
                translations[text] = translated

        return [str(text.map(translations)) for text in text_sentences]


@st.cache_data(max_entries=30)
def anonymize_analyzer(MarianText_letter, _analyzer, nom_propre):
    MarianText_anonymize_letter = MarianText_letter
    # st.write(MarianText_anonymize_letter)
    analyzer_results_keep = []
    analyzer_results_return = []
    analyzer_results_saved = []
    analyzer_results = _analyzer.analyze(text=MarianText_letter, language="en", entities=["DATE_TIME", "PERSON"], allow_list=['evening', 'day', 'the day', 'the age of', 'age', 'years', 'years old', 'months', 'hours', 'night', 'noon'])
    len_to_add = 0
    analyser_results_to_sort = {}
    i = 0
    for element in analyzer_results:
        analyser_results_to_sort[i] = element.start
        i = i + 1
    sorted_tuples = sorted(analyser_results_to_sort.items(), key=lambda x: x[1])
    sorted_dict = {k: v for k, v in sorted_tuples}
    # st.write(sorted_dict)

    for element_raw in sorted_dict:
        element = analyzer_results[element_raw]
        word = MarianText_letter[element.start : element.end]
        exception_list_presidio = ['age', 'year', 'month', 'day', 'hour']
        exception_detected = [e for e in exception_list_presidio if e in word.lower()]
        if word.count('/') == 1 or word.count('/') > 2:
            exception_detected.append('/ or ///')
        if len(exception_detected) == 0:
            if word.lower().strip() in nom_propre:
                word_to_replace = "**:green[" + word + "]** `[" + element.entity_type + "]`"
                MarianText_anonymize_letter = (
                    MarianText_anonymize_letter[: element.start + len_to_add]
                    + word_to_replace
                    + MarianText_anonymize_letter[element.end + len_to_add :]
                )
                analyzer_results_saved.append(str(element) + ", word:" + word)
            else:
                word_to_replace = "**:red[" + word + "]** `[" + element.entity_type + "]`"
                MarianText_anonymize_letter = (
                    MarianText_anonymize_letter[: element.start + len_to_add]
                    + word_to_replace
                    + MarianText_anonymize_letter[element.end + len_to_add :]
                )
                analyzer_results_keep.append(str(element) + ", word:" + word)
                analyzer_results_return.append(element)
            len_to_add = len_to_add + len(word_to_replace) - len(word)
        else:
            analyzer_results_saved.append(str(element) + ", word:" + word)

    return (
        MarianText_anonymize_letter,
        analyzer_results_return,
        analyzer_results_keep,
        analyzer_results_saved,
    )


@st.cache_data(max_entries=30)
def anonymize_engine(MarianText_letter, _analyzer_results_return, _engine, _nlp):
    result = _engine.anonymize(
        text=MarianText_letter,
        analyzer_results=_analyzer_results_return,
        operators={
            "PERSON": OperatorConfig("replace", {"new_value": ""}),
            "LOCATION": OperatorConfig("replace", {"new_value": ""}),
        },
    )
    return reformat_to_letter(result.text, _nlp)


@st.cache_data(max_entries=60)
def add_space_to_comma(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\,)(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " , ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=60)
def add_space_to_endpoint(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\.)(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " . ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=60)
def add_space_to_leftp(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\()(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ( ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=60)
def add_space_to_rightp(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(\))(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ) ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=60)
def add_space_to_stroph(texte, _nlp):
    text_list = []
    regex = "(?<!\d)(')(?!\d)(?!.*\1)"
    for sentence in _nlp.process(texte).sentences:
        text_space = re.sub(regex, " ' ", sentence.text.replace("\n", " "))
        text_space_no_db = text_space.replace("  ", " ")
        text_list.append(text_space_no_db)
        # print(text_space_no_db)
    return " ".join(text_list)


@st.cache_data(max_entries=60)
def add_space_to_comma_endpoint(texte, _nlp):
    text_fr_comma = add_space_to_comma(texte,_nlp)
    text_fr_comma_endpoint = add_space_to_endpoint(text_fr_comma, _nlp)
    text_fr_comma_endpoint_leftpc = add_space_to_leftp(text_fr_comma_endpoint, _nlp)
    text_fr_comma_endpoint_leftpc_right_pc = add_space_to_rightp(
        text_fr_comma_endpoint_leftpc, _nlp
    )
    # text_fr_comma_endpoint_leftpc_right_pc_stroph = add_space_to_stroph(
    #    text_fr_comma_endpoint_leftpc_right_pc
    # )
    return text_fr_comma_endpoint_leftpc_right_pc

@st.cache_data(max_entries=30)
def get_abbreviation_dict_correction():
    dict_correction = {}
    with open("data/fr_abbreviations.json", "r") as outfile:
        hpo_abbreviations = json.load(outfile)
    #for key, value in hpo_abbreviations.items():
    #    dict_correction[" " + key + " "] = " " + value + " "
    return hpo_abbreviations#dict_correction

@st.cache_data(max_entries=30)
def get_translation_dict_correction():
    dict_correction_FRspec = {
        "PC": "head circumference",
        "CP": "head circumference",
        "palatine slot": "cleft palate",
        "TSA": "autism",
        "ASD": "autism",
        "TDAH": "attention deficit hyperactivity disorder",
        "ADHD": "attention deficit hyperactivity disorder",
        "IME": " medical-educational institute for his intellectual disability",
        "EMI": " medical-educational institute for his intellectual disability",
        "CAMSP": "medical and social center for his mild global developmental delay",
        "SESSAD": "specific education services for his mild global developmental delay",
        "ESAT": "establishment and service of help by work for his mild global developmental delay",
        "RDPM": "global developmental delay",
        "IUGR": "intrauterin growth retardation",
        "RCIU": "intrauterin growth retardation",
        "CRIU": "intrauterin growth retardation",
        "QI": "IQ ",
        "QIT": "FSIQ ",
        "ITQ": "FSIQ ",
        "DS": "SD",
        "FOP": "patent foramen ovale",
        "PFO": "patent foramen ovale",
        "ARCF": "fetal distress",
        "\n": " ",
        "associated": "with",
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
    return dict_correction


@st.cache_resource(max_entries=30)
def change_name_patient_abbreviations(courrier, nom, prenom, abbreviations_dict):
    courrier_name = courrier
    dict_correction_name_abbreviations = {
        prenom: "CAS",
        nom : "INDEX",
        "M.": "M",
        "Mme.": "Mme",
        "Mlle.": "Mlle",
        "Dr.": "Docteur",
        "Dr": "Docteur",
        "Pr.": "Professeur",
        "Pr": "Professeur",
    }     
    for key, value in abbreviations_dict.items():
        dict_correction_name_abbreviations[key] = value
    
    list_replaced = []
    splitted_courrier = courrier_name.split()
    for i in splitted_courrier:
        print(i)
        for key, value in dict_correction_name_abbreviations.items():
            if i.lower().strip() == key.lower().strip():
                list_replaced.append(
                    'Abbreviation or patient name ' + i + ' replaced by ' + value
                )
                courrier_name = courrier_name.replace(i, value)

    return courrier_name, list_replaced


@st.cache_resource(max_entries=30)
def translate_marian(courrier_name, _nlp, _marian_fr_en):
    list_of_sentence = []
    for sentence in _nlp.process(courrier_name).sentences:
        list_of_sentence.append(sentence.text)
    MarianText_raw = "\n".join(_marian_fr_en.translate(list_of_sentence))
    return MarianText_raw


@st.cache_resource(max_entries=30)
def correct_marian(MarianText_space, dict_correction):
    MarianText = MarianText_space
    list_replaced = []
    for key, value in dict_correction.items():
        if key in MarianText:
            list_replaced.append(
                'Marian translation replaced "' + key + '" by "' + value
            )
            MarianText = MarianText.replace(key, value)
    return MarianText, list_replaced


@st.cache_data(max_entries=30)
def translate_letter(courrier, nom, prenom, _nlp, _marian_fr_en, dict_correction, abbreviation_dict):
    #courrier_space = add_space_to_comma_endpoint(courrier, _nlp)
    courrier_name, list_replaced_abb_name = change_name_patient_abbreviations(courrier, nom, prenom, abbreviation_dict)
    MarianText_raw = translate_marian(courrier_name, _nlp, _marian_fr_en)
    MarianText_space = add_space_to_comma_endpoint(MarianText_raw, _nlp)
    MarianText, list_replaced = correct_marian(MarianText_space, dict_correction)
    return MarianText, list_replaced, list_replaced_abb_name


@st.cache_data(max_entries=60)
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


@st.cache_data(max_entries=60)
def convert_df(df):
    return df.to_csv(sep="\t", index=False, header=None).encode("utf-8")

@st.cache_data(max_entries=60)
def convert_json(df):
    dict_return = {"features":[]}
    if len(df) > 0:
        df_dict_list = df[['HPO ID', 'Phenotype name']].to_dict(orient='index')
        for key, value in df_dict_list.items():
            dict_return['features'].append({'id': value['HPO ID'], 'observed': 'yes', 'label': value['Phenotype name'], 'type': "phenotype"})
        return json.dumps(dict_return)
    else:
        return None

@st.cache_data(max_entries=30)
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
                    num_kg_sd = re.findall("([\-0-9.])", kg_sd)[0]
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
                    num_height_sd = re.findall("([\-0-9.])", height_sd)[0]
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
                    num_pc_sd = re.findall("([\-0-9.])", pc_sd)[0]
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
    return " ".join(cutsentence_with_biometrics_return), additional_terms
@st.cache_data(max_entries=30)
def main_function(inputStr):
  hpo_to_name = get_phenotypes_lf.getNames()
  returnString, returnStringUnsafe = get_phenotypes_lf.extract_phenotypes(inputStr, hpo_to_name)
  returnDf = get_phenotypes_lf.get_dataframe_from_clinphen(returnString)
  returnDfUnsafe = get_phenotypes_lf.get_dataframe_from_clinphen(returnStringUnsafe)
  return returnDf, returnDfUnsafe

models_status = get_models()
nlp_fr, marian_fr_en = get_nlp_marian()
#nlp_en = get_nlp_en()
dict_correction = get_translation_dict_correction()
dict_abbreviation_correction = get_abbreviation_dict_correction()
nom_propre = get_list_not_deidentify()
analyzer, engine = config_deidentify()

if "load_state" not in st.session_state:
    st.session_state.load_state = False

with st.form("my_form"):
    c1, c2 = st.columns(2)
    with c1:
        nom = st.text_input("Nom du patient ", "Doe", key="name")
    with c2:
        prenom = st.text_input("Prénom du patient", "John", key="surname")
    courrier = st.text_area(
        "Courrier à coller", "Chers collegues, j'ai recu en consultation M. John Doe né le 14/07/1789 pour une fièvre récurrente et une maladie de Crohn. Il a pour antécédent des epistaxis recurrents. Parmi les antécédants familiaux, sa maman a présenté un cancer des ovaires. Il mesure 1.90 m (+2.5  DS),  pèse 93 kg (+3.6 DS) et son PC est à 57 cm (+0DS) ...", height=200, key="letter"
    )

    submit_button = st.form_submit_button(
        label="Submit",
    )


if submit_button or st.session_state.load_state:
    st.session_state.load_state = True
    MarianText, list_replaced, list_replaced_abb_name = translate_letter(
        courrier, nom, prenom, nlp_fr, marian_fr_en, dict_correction, dict_abbreviation_correction
    )
    MarianText_letter = reformat_to_letter(MarianText, nlp_fr)

    st.subheader("Translation and De-identification")
    (
        MarianText_anonymize_letter_analyze,
        analyzer_results_return,
        analyzer_results_keep,
        analyzer_results_saved,
    ) = anonymize_analyzer(MarianText_letter, analyzer, nom_propre)
    with st.expander("See country abbreviation and name correction"):
        st.write(list_replaced_abb_name)
    with st.expander("See country-specific correction"):
        st.write(list_replaced)
    with st.expander("See de-identified element"):
        st.write("De-identified elements")
        st.write(analyzer_results_keep)
        st.write("Keep elements")
        st.write(analyzer_results_saved)

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
        convert_df(MarianText_anonymize_letter_engine_df),
        nom + "_" + prenom + "_translated_and_deindentified_letter.txt",
        "text",
        key="download-translation",
    )

    st.subheader("Summarization")

    MarianText_anonymized_reformat_space = add_space_to_comma_endpoint(
        MarianText_anonymize_letter_engine, nlp_fr
    )
    MarianText_anonymized_reformat_biometrics, additional_terms = add_biometrics(
        MarianText_anonymized_reformat_space, nlp_fr
    )
    clinphen, clinphen_unsafe = main_function(MarianText_anonymized_reformat_biometrics)

    with st.expander("See additional terms extracted with biometrics analysis"):
        st.write(additional_terms)

    with st.expander("See unsafe extracted terms"):
        st.write(clinphen_unsafe)

    clinphen_df = st.experimental_data_editor(
        clinphen, num_rows="dynamic", key="data_editor"
    )

    st.caption("Modify cells above 👆 or even ➕ add rows, before downloading 👇")

    st.download_button(
        "Download summarized letter in HPO CSV format",
        convert_df(clinphen_df),
        nom + "_" + prenom + "_summarized_letter.tsv",
        "text/csv",
        key="download-summarization",
    )

    st.download_button(
        "Download summarized letter in Phenotips JSON format",
        convert_json(clinphen_df),
        nom + "_" + prenom + "_summarized_letter.json",
        "json",
        key="download-summarization-json",
    )