import json

import streamlit as st
from dotenv import load_dotenv

from rewriter import RewriterError, rewrite_description
from scraper import NetworkError, PageUnavailableError, ScraperError, scrape_product

load_dotenv()

APP_NAME = "Product Lens"


def _show_value(label, value):
    st.markdown(f"**{label}**")
    st.write(value if value not in (None, "") else "Not available")


def main():
    st.set_page_config(page_title=APP_NAME, layout="centered")
    st.title("Product Lens")
    st.caption("Product Page Extractor & Rewriter")
    st.write(
        "Enter a product page URL. The app downloads a limited amount of the page, "
        "extracts product details, validates them, and can optionally rewrite the "
        "description with OpenAI."
    )

    with st.form("product_form"):
        url = st.text_input(
            "Product page URL",
            placeholder="https://www.example.com/product/...",
        )
        rewrite = st.checkbox("Rewrite the extracted description with OpenAI")
        tone = st.selectbox(
            "Rewrite tone",
            ["Clear and professional", "Concise", "Friendly", "Neutral"],
            disabled=not rewrite,
        )
        submitted = st.form_submit_button("Extract product")

    if not submitted:
        return

    if not url.strip():
        st.warning("Enter a product page URL first.")
        return

    with st.spinner("Downloading and extracting product information..."):
        try:
            product = scrape_product(url)
        except PageUnavailableError as exc:
            st.error(str(exc))
            return
        except NetworkError as exc:
            st.error(str(exc))
            return
        except ScraperError as exc:
            st.error(str(exc))
            return
        except Exception:
            st.error("The product page could not be processed safely.")
            return

    st.success("Product page processed successfully.")
    st.subheader("Validated product data")

    _show_value("Product name", product.product_name)
    _show_value("Price", product.price)
    _show_value("Description", product.description)
    _show_value("Review rating", product.review_rating)
    _show_value("Source URL", str(product.source_url))

    with st.expander("Structured data"):
        st.code(
            json.dumps(product.model_dump(mode="json"), indent=2, ensure_ascii=False),
            language="json",
        )

    if rewrite:
        st.subheader("OpenAI rewritten description")
        if not product.description:
            st.info("No description was extracted, so there is nothing to rewrite.")
            return

        with st.spinner("Rewriting description with OpenAI..."):
            try:
                rewritten = rewrite_description(product.description, tone=tone)
            except RewriterError as exc:
                st.warning(str(exc))
                return
            except Exception:
                st.warning("The description could not be rewritten, but the extracted data above is still available.")
                return

        st.write(rewritten)
        st.caption(
            "The model receives only the validated extracted description. "
            "Instructions found inside webpage content are treated as untrusted data and are not followed."
        )


if __name__ == "__main__":
    main()
