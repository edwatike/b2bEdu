"""Train learning engine on successful parsing results."""
import sys
sys.path.insert(0, '.')
from learning_engine import LearningEngine

engine = LearningEngine()

session_id = 'training_session_2'

# Successful INN+Email results
successes = [
    {
        "domain": "betonolit.ru",
        "inn": "7804536482",
        "email": "egida@betonolit.ru",
        "inn_url": "https://betonolit.ru/kontakty.html",
        "source_urls": ["https://betonolit.ru/", "https://betonolit.ru/kontakty.html"]
    },
    {
        "domain": "materik-m.ru",
        "inn": "7801577949",
        "email": "812@materik-m.ru",
        "inn_url": "https://www.materik-m.ru/rekvizity/",
        "source_urls": ["https://www.materik-m.ru/", "https://www.materik-m.ru/contacts/", "https://www.materik-m.ru/about/", "https://www.materik-m.ru/rekvizity/"]
    },
    {
        "domain": "tgresurs.ru",
        "inn": "7839339421",
        "email": "manager@tgresurs.ru",
        "inn_url": "https://tgresurs.ru/requisiti/",
        "source_urls": ["https://tgresurs.ru/", "https://tgresurs.ru/kontakty.html", "https://tgresurs.ru/requisiti/"]
    },
    {
        "domain": "bgazobeton.ru",
        "inn": "7801319040",
        "email": None,
        "inn_url": "https://bgazobeton.ru/upload/requizit.pdf",
        "source_urls": ["https://bgazobeton.ru/", "https://bgazobeton.ru/upload/requizit.pdf"]
    },
]

for s in successes:
    if s["inn"]:
        result = engine.learn_from_manual_inn(
            domain=s["domain"],
            inn=s["inn"],
            source_url=s["inn_url"],
            learning_session_id=session_id
        )
        items = result.get("learned_items", [])
        print("INN learned for %s: %d items" % (s["domain"], len(items)))

    if s["email"]:
        email_learning = engine._learn_email_pattern(s["domain"], s["email"], s["source_urls"])
        if email_learning:
            engine.patterns["statistics"]["total_learned"] += 1
            engine._save_patterns()
            print("Email learned for %s: %s" % (s["domain"], email_learning["url_patterns"]))

# Domains that found email but not INN
email_only = [
    {"domain": "ccc1.ru", "email": "1@ccc1.ru", "urls": ["https://www.ccc1.ru/", "https://www.ccc1.ru/info/", "https://www.ccc1.ru/about-us.html"]},
    {"domain": "feroteks.ru", "email": "zakaz@feroteks.ru", "urls": ["https://feroteks.ru/", "https://feroteks.ru/info/", "https://feroteks.ru/about/", "https://feroteks.ru/contacts/"]},
    {"domain": "gazobetonvspb.ru", "email": "info@gazobetonvspb.ru", "urls": ["https://gazobetonvspb.ru/", "https://gazobetonvspb.ru/contacts", "https://gazobetonvspb.ru/about"]},
    {"domain": "gazosilikatstroy.ru", "email": "stroym@gazosilikatstroy.ru", "urls": ["https://gazosilikatstroy.ru/", "https://gazosilikatstroy.ru/contacts/", "https://gazosilikatstroy.ru/o-kompanii/"]},
    {"domain": "gbi78.ru", "email": "monolit@gbi78.ru", "urls": ["https://gbi78.ru/", "https://gbi78.ru/partners.html", "https://gbi78.ru/ur-licam.html", "https://gbi78.ru/contacts.html"]},
    {"domain": "konkrit.ru", "email": "konkrit-ooo@mail.ru", "urls": ["https://konkrit.ru/", "https://konkrit.ru/contact/", "https://konkrit.ru/about/"]},
    {"domain": "pbkbeton.ru", "email": "sbut@pbkbeton.ru", "urls": ["https://pbkbeton.ru/", "https://pbkbeton.ru/partnery", "https://pbkbeton.ru/optovikam", "https://pbkbeton.ru/kontakty"]},
    {"domain": "snabblock.ru", "email": "info@snabblock.ru", "urls": ["https://snabblock.ru/", "https://snabblock.ru/company/", "https://snabblock.ru/contacts/"]},
    {"domain": "stdostavka.ru", "email": "stdostavka@yandex.ru", "urls": ["https://stdostavka.ru/", "https://stdostavka.ru/contacts/", "https://stdostavka.ru/company/", "https://stdostavka.ru/info/"]},
    {"domain": "vladblok.ru", "email": "info@vladblok.ru", "urls": ["https://vladblok.ru/", "https://vladblok.ru/kontaktyi"]},
    {"domain": "velesark.ru", "email": "pk@velesark.ru", "urls": ["https://velesark.ru/", "https://velesark.ru/contact", "https://velesark.ru/o-kompanii/", "https://velesark.ru/ur-lica"]},
    {"domain": "sibyt.ru", "email": "umts@ao-gns.ru", "urls": ["https://sibyt.ru/", "https://sibyt.ru/o-kompanii/"]},
    {"domain": "sls.by", "email": "sale@sls.by", "urls": ["https://sls.by/", "https://sls.by/o-kompanii", "https://sls.by/contacts", "https://sls.by/gazobetonnye-bloki-optom"]},
    {"domain": "tiberg.ru", "email": "tiberg@dizos.ru", "urls": ["https://tiberg.ru/", "https://tiberg.ru/contact-us/", "https://tiberg.ru/about_us"]},
    {"domain": "tophouse.ru", "email": "info@tophouse.ru", "urls": ["https://www.tophouse.ru/", "https://www.tophouse.ru/company/"]},
    {"domain": "kirpich-gazobeton.ru", "email": "zed@kirpich-gazobeton.ru", "urls": ["https://kirpich-gazobeton.ru/", "https://kirpich-gazobeton.ru/contacts/", "https://kirpich-gazobeton.ru/company/", "https://kirpich-gazobeton.ru/info/"]},
    {"domain": "poritep.ru", "email": "sales@poritep.ru", "urls": ["https://poritep.ru/", "https://poritep.ru/contacts/", "https://poritep.ru/company/"]},
]

for e in email_only:
    email_learning = engine._learn_email_pattern(e["domain"], e["email"], e["urls"])
    if email_learning:
        engine.patterns["statistics"]["total_learned"] += 1
        engine._save_patterns()

print()
print("=== TRAINING COMPLETE ===")
summary = engine.get_learned_summary()
print("Total patterns: %d" % summary["total_patterns"])
print("INN URL patterns: %s" % summary["inn_url_patterns"])
print("Email URL patterns: %s" % summary["email_url_patterns"])
print("Domains learned: %d" % summary["domains_learned"])
print("Statistics: %s" % summary["statistics"])
