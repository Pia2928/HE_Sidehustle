import re
# regions.py
"""
Local-area knowledge for the AI assistant: what kinds of low-cost side
businesses tend to be in demand in each UK region and type of area.

Used in BOTH AI conditions (the area is held constant across generic and
personalised), so personalisation differs only in the personal profile.

IMPORTANT: this is a qualitative draft written from general knowledge, with no
figures. Before the pilot, check and refine each entry against current sources,
e.g. ONS regional profiles and labour-market statistics (Nomis), local
authority economic strategies and VisitBritain tourism data, and record the
final version with the preregistration.

Regions are the 12 UK ITL1 regions (England's 9 regions + Wales, Scotland,
Northern Ireland). Use exactly these names as the answer options in the
survey; matching is tolerant of case and common variants.
"""

# The catalogue of side hustles lives in side_hustles.py.

REGIONS = {
    "London": [
        "very high living costs and many time-poor commuters and professionals: demand for convenience "
        "services such as meal prep, errands, pet care, cleaning and laundry",
        "large private rental market and small homes: furniture assembly, decluttering, storage and "
        "small-space solutions",
        "huge visitor numbers and very diverse food and culture scene: walking tours, food stalls, "
        "pop-ups and cultural experiences",
        "many small businesses and freelancers: admin and social media help",
        "strong demand for tutoring and language conversation practice",
    ],
    "South East": [
        "affluent commuter towns with many dual-earner families: tutoring, after-school activities, "
        "home and garden maintenance, pet care",
        "coastal and countryside tourism: holiday-let cleaning and changeovers, local tours, "
        "outdoor activities",
        "older populations in many coastal towns: home help, gardening, digital help for older people",
        "rural and equestrian areas: pet and animal care, rural home services",
    ],
    "South West": [
        "strong, seasonal tourism along the coast and in national parks: holiday-let changeovers, "
        "local food and crafts, walking tours",
        "a large retired population: gardening, home help, companionship, tech support",
        "remote rural areas with fewer local services: errands, deliveries, house and pet sitting, "
        "and online selling",
        "a large young population in Bristol: event help, reselling, tutoring",
    ],
    "East of England": [
        "commuter belt around London: convenience, childcare-related and home services",
        "large agricultural and rural areas: farm-shop and local produce, rural services",
        "university city of Cambridge: tutoring, proofreading, student services",
        "coastal resorts in Norfolk, Suffolk and Essex: tourism and holiday-let services",
        "fast-growing new-build towns: handyman work, gardening and landscaping",
    ],
    "East Midlands": [
        "manufacturing and logistics hubs with shift workers: dog walking, cleaning, ironing at flexible times",
        "large student populations in Nottingham, Leicester and Loughborough: tutoring, student services, "
        "food and events",
        "relatively affordable housing and growing families: home improvement, children's activities",
        "Peak District tourism: holiday-let changeovers, local walking tours",
        "very diverse communities, especially in Leicester: cultural food, events and celebrations",
    ],
    "West Midlands": [
        "Birmingham's large, young and diverse population: home baking, event help, reselling",
        "strong maker tradition: upcycling and handmade goods",
        "many small businesses: social media and admin help",
        "rural Shropshire, Herefordshire and Worcestershire: plants and produce, holiday-let changeovers",
    ],
    "North West": [
        "large student and young-professional populations in Manchester and Liverpool: tutoring, "
        "proofreading, reselling, event help",
        "Lake District tourism: holiday-let changeovers, local crafts",
        "strong sport and music culture: event help, selling second-hand gear",
        "former mill towns with lower living costs: affordable home improvement and personal services",
    ],
    "North East": [
        "lower living costs and strong community identity: local, community-based services",
        "universities in Newcastle, Durham and Sunderland: student services and tutoring",
        "coastal and Northumberland tourism: holiday-let and outdoor services",
        "ageing population in some areas: home help, companionship, tech support",
        "fewer high-street services in some towns: mobile and online services",
    ],
    "Yorkshire and the Humber": [
        "cities with students and young professionals (Leeds, Sheffield, York): tutoring, food, events",
        "tourism in York, the Dales, the Moors and the coast: tours, holiday-let services",
        "strong outdoor culture: walking tours, selling second-hand outdoor gear",
        "agricultural areas: local produce, farm diversification, rural services",
        "lower living costs than the South: affordable personal and home services",
    ],
    "Wales": [
        "strong tourism in Eryri (Snowdonia), Pembrokeshire and the coast: holiday-let changeovers, "
        "local crafts, walking tours",
        "rural communities with long distances to services: mobile services, delivery, online selling",
        "Welsh-language communities: Welsh conversation practice and tutoring",
        "cities with students in Cardiff and Swansea: tutoring, student services, events",
    ],
    "Scotland": [
        "major tourism and festivals in Edinburgh: walking tours, short-let changeovers, event help",
        "Glasgow's large city population: home baking, event help, cleaning, reselling",
        "remote Highlands and islands: online selling, holiday-let changeovers, errands",
        "strong outdoor culture: selling second-hand outdoor gear, walking tours",
    ],
    "Northern Ireland": [
        "Belfast's growing tourism: walking tours, event help, short-let changeovers",
        "strong community life and local events: catering, event services, community activities",
        "rural and agricultural areas: local produce, rural services, mobile services",
        "Causeway Coast and other tourism areas: holiday-let changeovers, local crafts",
    ],
}

AREA_TYPES = {
    "city": "lives in a city: dense population, many renters and time-poor people, strong demand for "
            "convenience, delivery, events and student services",
    "town": "lives in a town or suburb: many families and commuters, demand for home, garden, "
            "children's and local community services",
    "rural": "lives in a village or rural area: few local services and long distances, so mobile services, "
             "online selling, tourism and community services work well",
}

_REGION_ALIASES = {
    "greater london": "London",
    "south east england": "South East", "south-east": "South East", "southeast": "South East",
    "south west england": "South West", "south-west": "South West", "southwest": "South West",
    "east of england": "East of England", "east anglia": "East of England", "east": "East of England",
    "east midlands": "East Midlands", "west midlands": "West Midlands",
    "north west england": "North West", "north-west": "North West", "northwest": "North West",
    "north east england": "North East", "north-east": "North East", "northeast": "North East",
    "yorkshire": "Yorkshire and the Humber", "yorkshire and humber": "Yorkshire and the Humber",
    "yorkshire & the humber": "Yorkshire and the Humber", "yorkshire and the humber": "Yorkshire and the Humber",
    "wales": "Wales", "cymru": "Wales", "scotland": "Scotland",
    "northern ireland": "Northern Ireland", "ni": "Northern Ireland",
}


# Larger UK cities and towns -> region, so a free-text answer like "Leeds" or
# "Brighton, Sussex" still finds the right region.
_PLACES = {
    "London": ["london", "croydon", "bromley", "ealing", "harrow", "romford", "wembley", "hackney", "camden"],
    "South East": ["brighton", "southampton", "portsmouth", "reading", "oxford", "milton keynes", "slough",
                   "guildford", "canterbury", "maidstone", "crawley", "basingstoke", "winchester", "hastings",
                   "eastbourne", "high wycombe", "kent", "surrey", "sussex", "hampshire", "berkshire",
                   "buckinghamshire", "oxfordshire", "isle of wight"],
    "South West": ["bristol", "plymouth", "exeter", "bath", "bournemouth", "poole", "swindon", "gloucester",
                   "cheltenham", "truro", "torquay", "taunton", "salisbury", "cornwall", "devon", "dorset",
                   "somerset", "wiltshire", "gloucestershire"],
    "East of England": ["cambridge", "norwich", "ipswich", "peterborough", "luton", "colchester", "chelmsford",
                        "southend", "watford", "st albans", "bedford", "norfolk", "suffolk", "essex",
                        "hertfordshire", "cambridgeshire", "bedfordshire"],
    "East Midlands": ["nottingham", "leicester", "derby", "lincoln", "northampton", "loughborough", "chesterfield",
                      "mansfield", "nottinghamshire", "leicestershire", "derbyshire", "lincolnshire",
                      "northamptonshire", "rutland"],
    "West Midlands": ["birmingham", "coventry", "wolverhampton", "stoke", "worcester", "hereford", "shrewsbury",
                      "telford", "walsall", "dudley", "solihull", "west bromwich", "warwick", "stafford",
                      "shropshire", "staffordshire", "warwickshire", "worcestershire", "herefordshire"],
    "North West": ["manchester", "liverpool", "preston", "blackpool", "bolton", "stockport", "wigan", "warrington",
                   "chester", "lancaster", "carlisle", "salford", "oldham", "rochdale", "burnley", "blackburn",
                   "kendal", "lancashire", "cheshire", "cumbria", "merseyside"],
    "North East": ["newcastle", "sunderland", "durham", "middlesbrough", "gateshead", "darlington", "hartlepool",
                   "stockton", "northumberland", "tyne"],
    "Yorkshire and the Humber": ["leeds", "sheffield", "bradford", "york", "hull", "huddersfield", "wakefield",
                                 "doncaster", "barnsley", "rotherham", "harrogate", "scarborough", "halifax",
                                 "grimsby", "whitby"],
    "Wales": ["cardiff", "swansea", "newport", "wrexham", "bangor", "aberystwyth", "llandudno", "carmarthen",
              "pembrokeshire", "gwynedd", "anglesey", "powys", "snowdonia", "eryri"],
    "Scotland": ["edinburgh", "glasgow", "aberdeen", "dundee", "inverness", "stirling", "perth", "paisley",
                 "fife", "highlands", "ayr", "dumfries"],
    "Northern Ireland": ["belfast", "derry", "londonderry", "lisburn", "newry", "armagh", "bangor county down",
                         "coleraine", "enniskillen", "omagh", "antrim", "county down", "tyrone", "fermanagh"],
}


def _contains_word(text, phrase):
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


def match_region(value):
    """Map a survey answer (region name, or city/town/county in free text) to one of the 12 regions, or None."""
    text = (value or "").strip().lower()
    if not text:
        return None
    for name in REGIONS:
        if text == name.lower():
            return name
    if text in _REGION_ALIASES:
        return _REGION_ALIASES[text]
    # Region names written inside a longer answer, e.g. "Manchester, North West"
    for name in sorted(REGIONS, key=len, reverse=True):
        if _contains_word(text, name.lower()):
            return name
    for alias, name in sorted(_REGION_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if len(alias) > 3 and _contains_word(text, alias):
            return name
    # Otherwise a known city, town or county
    for name, places in _PLACES.items():
        if any(_contains_word(text, p) for p in sorted(places, key=len, reverse=True)):
            return name
    return None


def match_area_type(value):
    text = (value or "").strip().lower()
    if not text:
        return None
    # Check suburb and rural first: "Suburb or edge of a city (suburban)" also contains "city".
    if any(w in text for w in ("suburb", "town", "edge of")):
        return "town"
    if any(w in text for w in ("village", "rural", "country")):
        return "rural"
    if any(w in text for w in ("city", "urban")):
        return "city"
    return None


def area_context(region_value, area_type_value=None, town=None):
    """Plain-text description of the participant's local area for the system prompt."""
    region = match_region(region_value)
    area_type = match_area_type(area_type_value)
    lines = []
    if region:
        where = f"the {region} region of the UK" if region not in ("Wales", "Scotland", "Northern Ireland", "London") \
            else region
        lines.append(f"The participant lives in {where}" + (f" (near {town.strip()})" if town and town.strip() else "") + ".")
        lines.append("Typical local demand for low-cost side businesses there:")
        lines.extend(f"- {item}" for item in REGIONS[region])
    else:
        lines.append("The participant lives in the UK (region unknown). Use demand that is common across the UK.")
    if area_type:
        lines.append(f"Type of area: the participant {AREA_TYPES[area_type]}.")
    return "\n".join(lines)
