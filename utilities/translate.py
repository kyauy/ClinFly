from dataclasses import dataclass
from typing import Dict, List, Sequence
import stanza
import transformers
import json
import streamlit as st
from .web_utilities import st_cache_data_if, st_cache_resource_if, supported_cache
from .anonymize import add_space_to_comma_endpoint, change_name_patient_abbreviations


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


@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
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



@st_cache_data_if(supported_cache, max_entries=5, ttl=3600)
def translate_report(
    Report, Last_name, First_name, _nlp, _marian_fr_en, dict_correction, abbreviation_dict
):
    Report_name, list_replaced_abb_name = change_name_patient_abbreviations(
        Report, Last_name, First_name, abbreviation_dict
    )
    MarianText_raw = translate_marian(Report_name, _nlp, _marian_fr_en)
    MarianText_space = add_space_to_comma_endpoint(MarianText_raw, _nlp)
    MarianText, list_replaced = correct_marian(
        MarianText_space, dict_correction, Last_name, First_name
    )
    del MarianText_raw
    del MarianText_space
    return MarianText, list_replaced, list_replaced_abb_name



@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
def translate_marian(Report_name, _nlp, _marian_fr_en):
    list_of_sentence = []
    for sentence in _nlp.process(Report_name).sentences:
        list_of_sentence.append(sentence.text)
    MarianText_raw = "\n".join(_marian_fr_en.translate(list_of_sentence))
    del list_of_sentence
    return MarianText_raw


@st_cache_data_if(supported_cache, max_entries=5, ttl=3600)
def correct_marian(MarianText_space, dict_correction, Last_name, First_name):
    MarianText = MarianText_space
    list_replaced = []
    for key, value in dict_correction.items():
        if key in MarianText:
            list_replaced.append(
                {
                    "name": Last_name,
                    "surname": First_name,
                    "type": "marian_correction",
                    "value": key,
                    "correction": value,
                    "lf_detected": True,
                    "manual_validation": True,
                }
            )
            MarianText = MarianText.replace(key, value)
    return MarianText, list_replaced



@st_cache_resource_if(supported_cache, max_entries=5, ttl=3600)
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


