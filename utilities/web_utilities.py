import streamlit as st
from PIL import Image
import inspect
import os


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
    
    Currently compatible with :fr:, :de:, :es: and optimized for :fr: to :gb:.  
    If you want to collaborate to improve another language, please contact us.  

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


def st_cache_data_if(condition, *args, **kwargs):
    def decorator(func):
        if condition:
            return st.cache_data(*args, **kwargs)(func)
        else:
            return func
    return decorator


def st_cache_resource_if(condition, *args, **kwargs):
    def decorator(func):
        if condition:
            return st.cache_resource(*args, **kwargs)(func)
        else:
            return func
    return decorator


supported_cache = False

def stack_checker():
    caller_frame = inspect.stack()
    for e in caller_frame:
        if os.path.basename(e.filename) == "clinfly_app_st.py":
            global supported_cache
            supported_cache = True

stack_checker()
