import pandas as pd
from utilities.web_utilities import display_page_title, display_sidebar, stack_checker
from utilities.anonymize import get_cities_list,get_abbreviation_dict_correction, reformat_to_report, anonymize_analyzer, anonymize_engine, add_space_to_comma_endpoint,get_list_not_deidentify, config_deidentify
from utilities.translate import get_translation_dict_correction, translate_report
from utilities.convert import convert_df_no_header, convert_df, convert_json, convert_list_phenogenius, convert_pdf_to_text
from utilities.extract_hpo import add_biometrics, extract_hpo
from utilities.get_model import get_models, get_nlp_marian
import streamlit as st
import gc

# -- Set page config
app_title: str = "ClinFly"

display_page_title(app_title)
display_sidebar()
        
cities_list = get_cities_list()
dict_correction = get_translation_dict_correction()
dict_abbreviation_correction = get_abbreviation_dict_correction()
nom_propre = get_list_not_deidentify()
analyzer, engine = config_deidentify(cities_list)

if "load_models" not in st.session_state:
    st.session_state.load_models = False

if "select_lang" not in st.session_state:
    st.session_state.select_lang = False

if "nlp_fr" not in st.session_state:
    st.session_state.nlp_fr = False

if "marian_fr_en" not in st.session_state:
    st.session_state.marian_fr_en = False

if "load_report" not in st.session_state:
    st.session_state.load_report = False

if st.session_state.load_models is False:
    with st.form("language"):
        source_lang = st.selectbox(
            "Which is the language of the letter :fr: :es: :de: ?", ("fr", "es", "de")  # "it"
        )
        submit_button_L = st.form_submit_button(label="Submit language")

    if submit_button_L:
        with st.spinner('Downloading models, it takes a moment, please wait'):
            models_status = get_models(source_lang)
            nlp_fr, marian_fr_en = get_nlp_marian(source_lang)
            st.session_state.select_lang = source_lang
            st.session_state.nlp_fr = nlp_fr
            st.session_state.marian_fr_en = marian_fr_en
            st.session_state.load_models = True

if st.session_state.load_models is True:
    st.info('Selected language is : ' + st.session_state.select_lang)
    with st.form("my_form"):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Last name", "Doe", key="name")
        with c2:
            prenom = st.text_input("First name", "John", key="surname")
        courrier = st.text_area(
            "You can paste the medical letter",
            "Chers collegues, j'ai recu en consultation M. John Doe né le 14/07/1789 pour une fièvre récurrente et une maladie de Crohn. Il a pour antécédent des epistaxis recurrents. Parmi les antécédants familiaux, sa maman a présenté un cancer des ovaires. Il mesure 1.90 m (+2.5  DS),  pèse 93 kg (+3.6 DS) et son PC est à 57 cm (+0DS) ...",
            height=200,
            key="letter",
        )
        uploaded_file = st.file_uploader("Or upload it (only pdf files are supported)")

        submit_button = st.form_submit_button(label="Submit report")

    if uploaded_file is not None:
        # To read file as bytes:
        bytes_data = uploaded_file.getvalue()
        courrier = convert_pdf_to_text(bytes_data)

    if submit_button or st.session_state.load_report:
        st.session_state.load_report = True
        MarianText, list_replaced, list_replaced_abb_name = translate_report(
            courrier,
            nom,
            prenom,
            st.session_state.nlp_fr,
            st.session_state.marian_fr_en,
            dict_correction,
            dict_abbreviation_correction,
        )
        MarianText_letter = reformat_to_report(MarianText, st.session_state.nlp_fr)
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
            MarianText_letter, analyzer_results_return, engine, st.session_state.nlp_fr
        )

        MarianText_anonymize_letter_engine_modif = pd.DataFrame(
            [x for x in MarianText_anonymize_letter_engine.split("\n")]
        )
        MarianText_anonymize_letter_engine_modif.columns = [
            "Modify / curate the automatically translated and de-identified letter before downloading:"
        ]
        MarianText_anonymize_letter_engine_df = st.data_editor(
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
            MarianText_anonymize_letter_engine, st.session_state.nlp_fr
        )
        MarianText_anonymized_reformat_biometrics, additional_terms = add_biometrics(
            MarianText_anonymized_reformat_space, st.session_state.nlp_fr
        )
        clinphen, clinphen_unsafe = extract_hpo(MarianText_anonymized_reformat_biometrics)

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
        clinphen_df = st.data_editor(
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
