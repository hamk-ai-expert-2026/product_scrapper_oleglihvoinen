# Product Lens – Product Page Extractor & Rewriter

Assignment #15 – Product Page Scraper and Rewriter

Product Lens is a small Streamlit application that accepts a product page URL and extracts useful product information from the page. The extracted data is validated with Pydantic before it is shown to the user. If a product description is available, the user can optionally ask OpenAI to rewrite it in a selected tone.

## What the program does

The application accepts a public `http://` or `https://` product page URL, for example a product page from an ecommerce website.

It attempts to extract:

- product name
- price
- product description
- review rating, when available
- final source URL

The scraper first looks for structured Product data in JSON-LD, which is commonly used by ecommerce pages. If that is unavailable or incomplete, it falls back to common metadata and page elements such as Open Graph tags, `itemprop` values, product title elements, price elements, description elements, and rating text.

The returned result is not arbitrary JSON text. It is converted into the `ProductData` Pydantic model in `product_model.py`. Pydantic validates the URL, field types, maximum field lengths, and review rating range before the application displays the data.

A missing field does not crash the application. Missing values are shown as `Not available`.

## Optional OpenAI rewrite

After extraction, the user can select **Rewrite the extracted description with OpenAI**.

The rewrite is optional. Scraping works without an OpenAI API key.

When rewriting is enabled, only the already extracted product description is sent to OpenAI. The original page HTML is not sent to the model.

The prompt explicitly treats the product description as untrusted webpage data. Any instructions, commands, prompt injection text, links, or requests found inside the scraped description must be ignored. OpenAI is instructed to rewrite only the product information and not invent new specifications, ratings, guarantees, prices, certifications, or other claims.

The OpenAI integration uses the Responses API. The default model is `gpt-5.6-luna`, but it can be changed with the `OPENAI_MODEL` environment variable.

## Safety and reliability measures

The assignment requirements are handled in the following ways.

### Limit downloaded/input content

The scraper downloads a maximum of 2 MB from a page. It stops reading once that limit is reached. Extracted field lengths are also restricted before validation. The description sent to OpenAI is limited to 4,000 characters.

### Handle unavailable or blocked pages

HTTP errors such as 401, 403, 404, and 429 are handled and displayed as user-friendly messages. Other HTTP errors are also handled instead of crashing the application.

Some ecommerce websites actively block automated requests. If a site blocks the request, Product Lens reports that the page is unavailable or blocked. This is expected behavior and is preferable to trying to bypass a website's access controls.

### Handle network failures

Connection failures, DNS failures, and request timeouts are caught and displayed clearly to the user.

### Treat webpage instructions as untrusted data

The scraper extracts data using normal parsing logic. It does not execute webpage JavaScript or follow instructions contained in the product description.

For the optional OpenAI rewrite, the model receives only the extracted description and is explicitly instructed to treat all webpage text as untrusted data rather than as instructions.

### Never crash because a field is missing

All requested product fields except the source URL are optional in the `ProductData` model. If name, price, description, or rating cannot be found, the value becomes `None` and the interface displays `Not available`.

### Basic URL protection

The application accepts only HTTP and HTTPS URLs. It rejects localhost and private/local network addresses. Redirect destinations are checked again before downloading them.

## Project files

- `app.py` – Streamlit user interface and application flow
- `scraper.py` – bounded page download, error handling, JSON-LD extraction and fallback extraction
- `product_model.py` – validated Pydantic product data model
- `rewriter.py` – optional OpenAI description rewrite using the Responses API
- `requirements.txt` – required Python packages
- `.env.example` – example environment variables
- `.gitignore` – prevents local secrets and virtual environments from being committed

## Windows setup instructions

### 1. Install Python

Download and install a current Python 3 version from Python's official website.

During installation, select **Add python.exe to PATH**.

After installation, open Command Prompt and check Python:

```cmd
python --version
```

You should see a Python version number.

### 2. Clone the repository

Open Command Prompt and run:

```cmd
git clone https://github.com/hamk-ai-expert-2026/product_scrapper_oleglihvoinen.git
cd product_scrapper_oleglihvoinen
```

If Git is not installed, you can also download the repository as a ZIP from GitHub and extract it to a folder.

### 3. Create a virtual environment

In the project folder run:

```cmd
python -m venv venv
```

Activate it:

```cmd
venv\Scripts\activate
```

The command prompt should now begin with `(venv)`.

### 4. Install the dependencies

Run:

```cmd
pip install -r requirements.txt
```

The project uses Streamlit, Requests, Beautiful Soup, Pydantic, python-dotenv, and the official OpenAI Python package.

### 5. Configure OpenAI for optional rewriting

This step is required only if you want to use the description rewrite feature.

Copy `.env.example` to a new file named `.env`.

In Command Prompt you can run:

```cmd
copy .env.example .env
```

Open `.env` in Notepad and replace the placeholder key:

```text
OPENAI_API_KEY=your_real_openai_api_key
OPENAI_MODEL=gpt-5.6-luna
```

Save the file.

Do not upload `.env` to GitHub. It contains your private API key and is already excluded by `.gitignore`.

If you do not create `.env`, product extraction still works. Only the optional OpenAI rewrite will be unavailable.

### 6. Start the application

With the virtual environment active, run:

```cmd
streamlit run app.py
```

Streamlit normally opens the application automatically in your browser. If it does not, open the local address shown in Command Prompt, usually:

```text
http://localhost:8501
```

## How to use the application

1. Paste a product page URL into **Product page URL**.
2. Optionally select **Rewrite the extracted description with OpenAI**.
3. If rewriting is enabled, select a tone.
4. Click **Extract product**.
5. Review the validated product name, price, description, rating, and source URL.
6. Open **Structured data** to see the validated JSON representation.
7. If rewriting was selected and a description was found, the rewritten version appears below the extracted product information.

## Example result structure

```json
{
  "source_url": "https://example.com/product/123",
  "product_name": "Example Product",
  "price": "29.99 EUR",
  "description": "Example product description.",
  "review_rating": 4.5
}
```

If a field cannot be extracted, its value is `null` rather than causing an exception.

## Notes about Amazon, Temu, and similar websites

Large ecommerce sites often use dynamic rendering, bot protection, regional pages, login requirements, or frequently changing HTML. Because of this, a simple server-side scraper may not extract every field from every page, and some sites may return a blocked-page response.

The assignment allows Crawl4AI **or another suitable page extraction method**. This implementation uses Requests and Beautiful Soup because they provide a clear and lightweight way to demonstrate bounded downloading, structured extraction, validation, error handling, and prompt-injection protection. The scraper is organized separately from the interface so another extraction backend, such as Crawl4AI, could be added later without changing the validated product data model or OpenAI rewriter.

## Privacy and API keys

The application does not store the entered product URL or extracted results in a database.

Never put a real OpenAI API key into source code, `README.md`, `.env.example`, or a GitHub commit. Keep it only in your local `.env` file or another secure environment-variable system.
