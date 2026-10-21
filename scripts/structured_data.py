"""Build Schema.org data from the same service cards visitors can read."""

import re

from html_document import parse_html


def career_services(document, page_url: str, person_id: str) -> list:
    services = []
    for card in document.find_all("article", "offer"):
        card_id = card.attributes.get("id")
        if not card_id:
            raise ValueError("A career service card is missing its id attribute.")
        service_url = page_url + "#" + card_id
        service = {
            "@type": "Service",
            "@id": service_url,
            "name": card.require("h3").text,
            "url": service_url,
            "provider": {"@id": person_id},
            "areaServed": {"@type": "Place", "name": "Online"},
            "availableChannel": {
                "@type": "ServiceChannel",
                "serviceUrl": page_url + "#contact",
            },
        }
        price_text = card.require(class_name="offer-cost").require("strong").text
        price_match = re.fullmatch(r"([\d\s]+) ₸", price_text)
        if price_match:
            service["offers"] = {
                "@type": "Offer",
                "price": re.sub(r"\s", "", price_match[1]),
                "priceCurrency": "KZT",
                "url": service_url,
            }
        services.append(service)
    return services


def business_services(document, page_url: str, person_id: str) -> list:
    services = []
    service_list = document.require("ul", "business-list")
    for index, card in enumerate(service_list.find_all("li", recursive=False), start=1):
        service = {
            "@type": "Service",
            "@id": f"{page_url}#business-service-{index}",
            "name": card.require("h3").text,
            "provider": {"@id": person_id},
            "url": page_url + "#business",
        }
        description = next(card.find_all("p"), None)
        if description:
            service["description"] = description.text
        services.append(service)
    return services


def build_structured_data(config: dict, language: str, markup: str) -> dict:
    metadata = config["locales"][language]
    site_url = config["site_url"]
    page_url = site_url + metadata["path"]
    person_id = site_url + "#person"
    document = parse_html(markup)
    services = career_services(document, page_url, person_id)
    services.extend(business_services(document, page_url, person_id))
    service_section = document.require("section", element_id="services")

    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Person",
                "@id": person_id,
                "name": metadata["person_name"],
                "url": site_url,
                "jobTitle": metadata["job_title"],
                "email": config["email"],
                "sameAs": [
                    url for url in (config["telegram_url"], config.get("linkedin_url")) if url
                ],
                "workLocation": {"@type": "Place", "name": "Almaty, Kazakhstan"},
                "knowsLanguage": list(config["locales"]),
            },
            {
                "@type": "WebSite",
                "@id": site_url + "#website",
                "url": site_url,
                "name": config["site_name"],
                "inLanguage": list(config["locales"]),
                "publisher": {"@id": person_id},
            },
            {
                "@type": "WebPage",
                "@id": page_url + "#webpage",
                "url": page_url,
                "name": metadata["title"],
                "description": metadata["description"],
                "inLanguage": language,
                "isPartOf": {"@id": site_url + "#website"},
                "about": {"@id": person_id},
                "mainEntity": {"@id": page_url + "#services-catalog"},
            },
            {
                "@type": "OfferCatalog",
                "@id": page_url + "#services-catalog",
                "name": service_section.require("h2").text,
                "itemListElement": [
                    {"@type": "Offer", "itemOffered": {"@id": service["@id"]}}
                    for service in services
                ],
            },
            *services,
        ],
    }
