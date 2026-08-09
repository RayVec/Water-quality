"""DOM-substitution translation with an on-disk dictionary per type, plus a
live Google Translate fallback (and cache write-back) for anything the
dictionary doesn't have yet.

There is no cross-type shared word list yet — only one type exists, so
there is nothing to share. See docs/multi-type-refactor.md, section 9.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Dict, List, Set

import pandas as pd
from bs4 import BeautifulSoup, Comment, NavigableString
from googletrans import Translator

# One in-memory dictionary per type, loaded from disk on first use.
_DICTIONARIES: Dict[str, Dict[str, str]] = {}


def _load_dictionary(translations_file: str, english_col: str, spanish_col: str) -> Dict[str, str]:
    """Loads translations from the Excel file into a dictionary."""
    translations_dict: Dict[str, str] = {}
    if not os.path.exists(translations_file):
        logging.warning(f"Translations file '{translations_file}' not found. Starting with empty dictionary.")
        return translations_dict

    try:
        logging.info(f"Loading translations from {translations_file}...")
        df = pd.read_excel(translations_file)

        if english_col not in df.columns or spanish_col not in df.columns:
            logging.error(f"Translations file '{translations_file}' must contain '{english_col}' and '{spanish_col}' columns.")
            return translations_dict

        df = df.fillna('')
        for _, row in df.iterrows():
            key = str(row[english_col])
            value = str(row[spanish_col])
            if key:
                translations_dict[key] = value

        logging.info(f"Successfully loaded {len(translations_dict)} translations.")
    except Exception as e:
        logging.error(f"Failed to load translations from '{translations_file}': {e}", exc_info=True)
        translations_dict = {}

    return translations_dict


def _save_dictionary(translations_file: str, english_col: str, spanish_col: str, dictionary: Dict[str, str]) -> None:
    """Saves the current state of a type's dictionary back to its Excel file."""
    logging.info(f"Saving updated translations to {translations_file}...")
    try:
        items = list(dictionary.items())
        df = pd.DataFrame(items, columns=[english_col, spanish_col])
        df = df.sort_values(by=english_col)
        df.to_excel(translations_file, index=False, engine='openpyxl')
        logging.info(f"Successfully saved {len(df)} translations to {translations_file}.")
    except Exception as e:
        logging.error(f"Failed to save translations to {translations_file}: {e}", exc_info=True)


async def _fetch_translations_async(texts_to_translate: List[str]) -> Dict[str, str]:
    """Translates a list of texts using googletrans API asynchronously."""
    api_translations: Dict[str, str] = {}
    if not texts_to_translate:
        return api_translations

    logging.info(f"Calling Google Translate API for {len(texts_to_translate)} unique texts...")
    try:
        async with Translator() as translator:
            results = await translator.translate(texts_to_translate, dest='es', src='en')

        if isinstance(results, list):
            for i, result in enumerate(results):
                if result and result.text:
                    original = texts_to_translate[i]
                    plain_text_translation = re.sub(r'<[^>]+>', '', result.text)
                    api_translations[original] = plain_text_translation
                else:
                    logging.warning(f"Google Translate API returned no text for: '{texts_to_translate[i]}'")
        elif results and results.text:
            plain_text_translation = re.sub(r'<[^>]+>', '', results.text)
            api_translations[texts_to_translate[0]] = plain_text_translation
        else:
            logging.warning("Google Translate API returned unexpected result type or no text.")

        logging.info(f"Received {len(api_translations)} translations from API.")
    except Exception as e:
        logging.error(f"Google Translate API error during batch call: {e}", exc_info=True)
        api_translations = {}

    return api_translations


def translate_html(rendered_html: str, type_name: str, type_dir: str, config: dict) -> str:
    """Walk rendered_html's text nodes and replace anything with a known
    Spanish translation, fetching (and caching to disk) anything the type's
    dictionary doesn't have yet. Falls back to the untranslated HTML on error.
    """
    translations_file = os.path.join(type_dir, config['files']['translations'])
    english_col = config['files']['translationColumns']['english']
    spanish_col = config['files']['translationColumns']['spanish']

    if type_name not in _DICTIONARIES:
        _DICTIONARIES[type_name] = _load_dictionary(translations_file, english_col, spanish_col)
    dictionary = _DICTIONARIES[type_name]

    try:
        soup = BeautifulSoup(rendered_html, 'html.parser')

        texts_to_translate_set: Set[str] = set()
        all_text_nodes = soup.find_all(string=True)

        for node in all_text_nodes:
            if node.parent.name in ['script', 'style', '[document]', 'head', 'title', 'meta'] or isinstance(node, Comment):
                continue
            original_text = node.strip()
            if original_text and original_text != "None" and original_text not in dictionary:
                texts_to_translate_set.add(original_text)

        logging.info(f"Found {len(texts_to_translate_set)} unique texts not in local dictionary.")

        if texts_to_translate_set:
            api_translations = asyncio.run(_fetch_translations_async(list(texts_to_translate_set)))
            if api_translations:
                logging.info(f"Updating local translation dictionary with {len(api_translations)} new entries...")
                dictionary.update(api_translations)
                _save_dictionary(translations_file, english_col, spanish_col, dictionary)

        combined_translations = dictionary.copy()

        replaced_count = 0
        for node in all_text_nodes:
            if node.parent.name in ['script', 'style', '[document]', 'head', 'title', 'meta'] or isinstance(node, Comment):
                continue
            original_text = node.strip()
            if not original_text:
                continue

            translated_text = combined_translations.get(original_text)
            if translated_text and translated_text != original_text:
                plain_translation = re.sub(r'<[^>]+>', '', translated_text)
                node.replace_with(NavigableString(plain_translation))
                replaced_count += 1

        logging.info(f"Applied {replaced_count} translations to HTML structure.")
        return str(soup)
    except Exception as e:
        logging.error(f"Error during translation processing: {e}", exc_info=True)
        return rendered_html
