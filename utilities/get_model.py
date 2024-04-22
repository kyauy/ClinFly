import stanza
import nltk
import os
import spacy
import streamlit as st
from .web_utilities import st_cache_resource_if, supported_cache
from .translate import Translator

@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def get_models(langue,output=os.path.expanduser("~")):
    if langue == "fr":
        stanza.download(langue,dir = os.path.join(output,"stanza_resources"))
        Translator(langue, "en")
    elif langue == "de":
        stanza.download(langue,dir = os.path.join(output,"stanza_resources"))
        Translator(langue, "en")
    else:
        stanza.download(langue,dir = os.path.join(output,"stanza_resources"))
        Translator(langue, "en")
    if os.path.join(output,"nltk_data") not in nltk.data.path:
        nltk.data.path.append(os.path.join(output,"nltk_data"))
    try:
        nltk.data.find("omw-1.4")
    except LookupError:
        nltk.download("omw-1.4",download_dir = os.path.join(output,"nltk_data"))
    try:
        nltk.data.find("wordnet")
    except LookupError:
        nltk.download("wordnet", download_dir = os.path.join(output,"nltk_data"))

    spacy_model_name = "en_core_web_lg"
    try:
        nlp = spacy.load(os.path.join(output,spacy_model_name))
        print(spacy_model_name + " already downloaded")
    except OSError:
        spacy.cli.download(spacy_model_name)
        nlp = spacy.load(spacy_model_name)
        nlp.to_disk(os.path.join(output,spacy_model_name))



@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def get_nlp_marian(source_lang):
    nlp_fr = stanza.Pipeline(source_lang, processors="tokenize")
    marian_fr_en = Translator(source_lang, "en")
    return nlp_fr, marian_fr_en


