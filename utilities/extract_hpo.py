import re
from clinphen_src import get_phenotypes_lf
import streamlit as st
from .web_utilities import st_cache_data_if, supported_cache



@st_cache_data_if(supported_cache, max_entries=5, ttl=3600)
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



@st_cache_data_if(supported_cache, max_entries=5, ttl=3600)
def extract_hpo(inputStr):
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