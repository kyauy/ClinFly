import streamlit as st

from PIL import Image


def display_page_title(title: str):
    st.set_page_config(page_title=title, page_icon=":small_airplane:", layout="wide")


def display_sidebar():
    image_pg = Image.open("img/clinfly_logo.png")
    st.sidebar.image(image_pg, caption=None, width=200)
    st.sidebar.title("ClinFly")

    st.sidebar.header(
        "Share medical consultation letter automatically translated, de-identified and summarized using deep learning"
    )

    st.sidebar.markdown(
        """
    Currently only working from :fr: to :gb:.  

    If any questions or suggestions, please contact: [kevin.yauy@chu-montpellier.fr](kevin.yauy@chu-montpellier.fr) and [lucas.gauthier@chu-lyon.fr](lucas.gauthier@chu-lyon.fr) 

    Code source is available in GitHub:
    [https://github.com/kyauy/ClinFly](https://github.com/kyauy/ClinFly)

    ClinFly is an initiative from:
    """
    )
    image_univ = Image.open("img/logosfacmontpellier.png")
    st.sidebar.image(image_univ, caption=None, width=190)

    image_chu = Image.open("img/CHU-montpellier.png")
    st.sidebar.image(image_chu, caption=None, width=95)

    # with open("data/Mentions_legales_lf.pdf", "rb") as pdf_file:
    #    PDFbyte = pdf_file.read()


#
# st.sidebar.download_button(label="Mentions légales",
#                    data=PDFbyte,
#                    file_name="Mentions_legales_lf.pdf",
#                    mime='application/octet-stream')
# st.sidebar.markdown("[Mentions légales](data/Mentions_legales_lf.pdf)")
