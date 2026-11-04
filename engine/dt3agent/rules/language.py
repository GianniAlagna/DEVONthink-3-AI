"""Language of a document: de / fr / it / en by counting distinctive words (brief A2, ADR-0009).

Phase 0 found the AI wrong on language in a fixed way; this rule decides instead. Only words that belong to
exactly one of the four languages are listed (e.g. "april", "total", "payable", "la" are shared and left out).
Returns (language, share of hits) or (None, share) when the evidence is too thin or too mixed.
"""
import re

WORDS = {
    "de": """der die das und ist nicht mit für von zu den dem ein eine einer auf im bis bei sie wir ihr ihre
             unser sehr damen herren geehrte rechnung betrag zahlbar innert tagen mwst gemäss bitte freundlichen
             grüssen januar februar märz juni juli oktober dezember nr zahlung forderung danken ende monat""",
    "fr": """le les et est pas avec pour de du une sur au aux dans vous nous votre notre madame monsieur
             facture montant jours tva veuillez salutations janvier février mars avril juin juillet août octobre
             décembre plus tard ci joint mois remercions""",
    "it": """il lo gli è non con di del della dei una sul nel entro giorni fattura importo iva pagabile totale
             gentile distinti saluti gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre
             dicembre allegato trova cliente mese""",
    "en": """the and is not with of to an on by we you your our dear sincerely invoice amount within days vat
             please january february march june july october december attached find customer month for""",
}
LEXICON = {w: lang for lang, words in WORDS.items() for w in words.split()}

MIN_HITS = 3
MIN_SHARE = 0.6
TOKEN = re.compile(r"[^\W\d_]+")


def detect(text: str) -> tuple[str | None, float]:
    counts = dict.fromkeys(WORDS, 0)
    for token in TOKEN.findall(text.casefold()):
        lang = LEXICON.get(token)
        if lang:
            counts[lang] += 1
    total = sum(counts.values())
    if not total:
        return None, 0.0
    best = max(counts, key=counts.get)
    share = round(counts[best] / total, 2)
    if counts[best] < MIN_HITS or share < MIN_SHARE:
        return None, share
    return best, share
