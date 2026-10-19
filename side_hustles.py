# side_hustles.py
"""
Knowledge base: UK side hustles that need NO specific training or
qualification and only LOW resources (start-up cost up to about £250).

Single source of truth for
  - the AI assistants (both AI conditions get the same catalogue),
  - the Gorilla system prompts (export_gorilla_prompt_section),
  - the HTML advisor page (build_advisor.py -> side_hustle_advisor.html).

Structure (in the spirit of a data-grounded generator):
  SOURCES        every rule and statistic points to a source key here
  HUSTLES        the catalogue; each entry has cost, mode, customer groups,
                 area fit and the legal/practical rules that apply
  DRIVERS        customer groups that create demand
  REGION_DRIVERS how strongly each customer group features in each of the
                 12 UK regions (qualitative 1-3, evidence status per region)
  AREA_DRIVERS   adjustments for city / town / rural

Evidence status
  - Rules (registration, licences, tax) are taken from the official pages in
    SOURCES, checked on 16 October 2026 and independently re-checked against
    the same pages. Several rules apply to England only (stated in the rule);
    Wales, Scotland and Northern Ireland can differ.
  - Regional weights are QUALITATIVE judgements. Each REGION_DRIVERS entry
    names the dataset to check them against before the pilot (status
    "to verify"). Do not report them as measured values.
"""

CHECKED_ON = "16 October 2026"

SOURCES = {
    "food_registration": {
        "title": "Starting a food business (GOV.UK / Food Standards Agency)",
        "url": "https://www.gov.uk/guidance/starting-a-food-business",
        "finding": "Applies to England, Wales and Northern Ireland. If you provide food on a regular and organised "
                   "basis you are a food business and must register with the local authority at least 28 days "
                   "before trading. Registration is free and can't be refused. A food hygiene certificate is not "
                   "compulsory, but you must be able to show you've been adequately trained in food hygiene. Home "
                   "businesses can expect a hygiene inspection and may need permission from their mortgage lender "
                   "or landlord.",
    },
    "childcare_exemptions": {
        "title": "Childcare registration exemptions (GOV.UK / Ofsted)",
        "url": "https://www.gov.uk/guidance/registration-exemptions",
        "finding": "Applies to England. Babysitters looking after children at home between 6pm and 2am, nannies "
                   "for up to 2 families in one child's home, and people only looking after children over 8 in "
                   "someone's home don't have to register with Ofsted. Only one exemption can be used and it must "
                   "cover all the care you give. Care of under 2 hours a day per child can't be registered, "
                   "unless it is before- or after-school care.",
    },
    "dbs_self_employed": {
        "title": "DBS checks for self-employed people and personal employees (GOV.UK)",
        "url": "https://www.gov.uk/guidance/dbs-checks-for-self-employed-people-and-personal-employees",
        "finding": "Self-employed people apply for their own check through a DBS Umbrella Body, if their role is "
                   "eligible; for example, a self-employed tutor working with children can apply for an Enhanced "
                   "with Barred List check. Clients can ask to see the certificate.",
    },
    "dog_walking_licence": {
        "title": "Dog walking businesses (Barnsley Council, example of council guidance in England)",
        "url": "https://www.barnsley.gov.uk/services/animal-welfare-and-licences/dog-walking-businesses",
        "finding": "One council's guidance: you don't need a licence to walk dogs or visit them in the owner's "
                   "home. Defra is reviewing possible licensing or registration for professional dog walkers.",
    },
    "home_boarding_licence": {
        "title": "Home boarding for dogs: licensing statutory guidance (GOV.UK / Defra)",
        "url": "https://www.gov.uk/government/publications/animal-activities-licensing-guidance-for-local-authorities/"
               "home-boarding-for-dogs-licensing-statutory-guidance-for-local-authorities",
        "finding": "Applies to England. Boarding dogs in your own home needs a council licence if it is carried "
                   "out as a commercial business; the guidance's business test refers to trading income above the "
                   "£1,000 trading allowance. Boarding cats is licensed separately.",
    },
    "market_stall_licence": {
        "title": "Market stall licence (GOV.UK)",
        "url": "https://www.gov.uk/market-stall-licence",
        "finding": "To run a market stall as a trader you need a temporary ('casual') or permanent licence "
                   "from the local council. The page does not cover car-boot sales.",
    },
    "trading_allowance": {
        "title": "Tax help for side hustles (HMRC campaign, GOV.UK)",
        "url": "https://taxhelpforhustles.campaign.gov.uk/i-work-for-myself",
        "finding": "You have a single £1,000 tax-free trading allowance per tax year across all side hustles. "
                   "Above that you must tell HMRC. Occasionally selling unwanted personal items is unlikely to be "
                   "taxable; you only need to tell HMRC if a single item or collection sells for over £6,000.",
    },
    "register_sa": {
        "title": "Register for Self Assessment (GOV.UK)",
        "url": "https://www.gov.uk/register-for-self-assessment",
        "finding": "If you need to send a tax return and haven't before, register by 5 October after the end of "
                   "the tax year in which you had the income.",
    },
    "online_sellers": {
        "title": "Information for online sellers (GOV.UK news, 4 December 2024)",
        "url": "https://www.gov.uk/government/news/information-for-online-sellers",
        "finding": "Platforms such as eBay and Vinted report sellers who sold at least 30 items or earned "
                   "roughly £1,700 in a year. Being reported doesn't automatically mean tax is due, and selling "
                   "unwanted belongings hasn't changed. Tax may be due if you buy to resell, make goods to sell or "
                   "offer services online and that income is over £1,000 before expenses in a tax year.",
    },
    "side_hustle_survey": {
        "title": "Side hustle statistics UK (Finder, survey by Censuswide, 3-6 January 2026, n=2,000 GB adults)",
        "url": "https://www.finder.com/uk/side-hustle-statistics",
        "finding": "46% of GB adults report having a side hustle (Censuswide for Finder). Finder separately cites "
                   "unnamed external research ranking selling old clothes on Vinted or similar as the most "
                   "popular type. Commercial survey: use as context, not as an official figure.",
    },
    "private_hire": {
        "title": "Taxi and private hire driver licence (GOV.UK)",
        "url": "https://www.gov.uk/taxi-driver-licence",
        "finding": "Driving people for payment needs a private hire licence from the council (TfL in London), "
                   "which can involve medical, enhanced DBS and knowledge checks.",
    },
    "sia_licence": {
        "title": "Find out if you need an SIA licence (GOV.UK)",
        "url": "https://www.gov.uk/guidance/find-out-if-you-need-an-sia-licence",
        "finding": "Key holding for a fee under a contract is an activity that can need a Security Industry "
                   "Authority licence.",
    },
    "waste_carrier": {
        "title": "Register as a waste carrier, broker or dealer (GOV.UK, England)",
        "url": "https://www.gov.uk/waste-carrier-or-broker-registration",
        "finding": "Transporting waste as part of a business, including garden waste or packaging you take away "
                   "from customers, needs waste carrier registration in England; Wales, Scotland and Northern "
                   "Ireland have their own schemes.",
    },
}

# Customer groups whose needs create demand for side hustles
DRIVERS = {
    "time_poor": "Busy workers and commuters short on time",
    "families": "Families with children",
    "older": "Older people and retirees",
    "pet_owners": "Pet owners",
    "students": "Students and young adults",
    "tourists": "Visitors and holiday lets",
    "small_biz": "Small local businesses",
    "renters": "Renters and people moving home",
    "rural": "Rural residents far from services",
    "online": "Online buyers anywhere in the UK",
}

# cost: rough start-up cost in GBP (low, high); mode: in_person / online / both
HUSTLES = [
    # ---- Care and home services
    {"id": "babysitting", "name": "Evening babysitting", "category": "Care and home services",
     "what": "Looking after children in their own home so parents can go out.",
     "cost": (0, 0), "mode": "in_person", "customers": ["families"], "areas": ["city", "town", "rural"],
     "rules": [("In England, babysitting in the child's home only between 6pm and 2am doesn't need Ofsted "
                "registration; daytime or after-school care needs a different exemption.", "childcare_exemptions"),
               ("If your role is eligible, you can apply for your own DBS check through an Umbrella Body, and "
                "parents can ask to see it.", "dbs_self_employed")]},
    {"id": "dog_walking", "name": "Dog walking", "category": "Care and home services",
     "what": "Walking dogs for owners who are at work or less mobile.",
     "cost": (0, 50), "mode": "in_person", "customers": ["pet_owners", "time_poor", "older"],
     "areas": ["city", "town", "rural"],
     "rules": [("No licence needed to walk dogs or visit them in the owner's home (Defra is reviewing this).",
                "dog_walking_licence"),
               ("In England, boarding dogs in your own home as a business needs a council licence.",
                "home_boarding_licence")]},
    {"id": "pet_sitting", "name": "Pet sitting in the owner's home", "category": "Care and home services",
     "what": "Feeding and checking on cats, rabbits or dogs while owners are away.",
     "cost": (0, 0), "mode": "in_person", "customers": ["pet_owners", "tourists", "time_poor"],
     "areas": ["city", "town", "rural"],
     "rules": [("Visiting pets in the owner's home needs no licence.", "dog_walking_licence"),
               ("In England, boarding dogs or cats at your home as a business needs a council licence.",
                "home_boarding_licence")]},
    {"id": "house_sitting", "name": "House sitting and plant watering",
     "category": "Care and home services",
     "what": "Checking homes, feeding pets and watering plants while people are away.",
     "cost": (0, 0), "mode": "in_person", "customers": ["time_poor", "older", "tourists"],
     "areas": ["city", "town", "rural"],
     "rules": [("Offering paid key holding under a contract can need an SIA licence.", "sia_licence")]},
    {"id": "cleaning", "name": "Home cleaning", "category": "Care and home services",
     "what": "Regular or one-off cleaning, including end-of-tenancy cleans.",
     "cost": (20, 100), "mode": "in_person", "customers": ["time_poor", "older", "renters"],
     "areas": ["city", "town"], "rules": []},
    {"id": "changeovers", "name": "Holiday-let changeover cleaning", "category": "Care and home services",
     "what": "Cleaning and resetting holiday cottages and short lets between guests.",
     "cost": (20, 100), "mode": "in_person", "customers": ["tourists"], "areas": ["rural", "town", "city"],
     "rules": []},
    {"id": "ironing", "name": "Ironing and laundry service", "category": "Care and home services",
     "what": "Collecting, ironing and returning clothes.",
     "cost": (0, 50), "mode": "in_person", "customers": ["time_poor", "older"], "areas": ["city", "town"],
     "rules": []},
    {"id": "gardening", "name": "Garden tidying and lawn mowing", "category": "Care and home services",
     "what": "Mowing, weeding, hedge trimming and leaf clearing.",
     "cost": (0, 250), "mode": "in_person", "customers": ["older", "families", "time_poor", "rural"],
     "areas": ["town", "rural"],
     "rules": [("Taking garden waste away for customers needs waste carrier registration (England).",
                "waste_carrier")]},
    {"id": "odd_jobs", "name": "Odd jobs and flat-pack assembly", "category": "Care and home services",
     "what": "Assembling furniture, putting up shelves and small repairs.",
     "cost": (50, 150), "mode": "in_person", "customers": ["renters", "time_poor", "older"],
     "areas": ["city", "town"],
     "rules": [("Stick to simple jobs; leave gas and electrical installation to registered trades.", None),
               ("Taking old packaging or waste away needs waste carrier registration (England).", "waste_carrier")]},
    {"id": "errands", "name": "Errands and shopping for older people", "category": "Care and home services",
     "what": "Shopping, prescription collection, walking to appointments and company.",
     "cost": (0, 0), "mode": "in_person", "customers": ["older", "rural"], "areas": ["town", "rural"],
     "rules": [("Driving people for payment needs a private hire licence, so offer errands, not paid lifts.",
                "private_hire")]},
    {"id": "car_wash", "name": "Car washing at people's homes", "category": "Care and home services",
     "what": "Washing and cleaning cars on driveways or at workplaces.",
     "cost": (30, 100), "mode": "in_person", "customers": ["time_poor", "families"], "areas": ["town"],
     "rules": []},
    # ---- Selling products
    {"id": "resell_own", "name": "Selling your own unwanted clothes and items online",
     "category": "Selling products",
     "what": "Clearing out wardrobes and homes on Vinted, eBay or Depop.",
     "cost": (0, 0), "mode": "online", "customers": ["online"], "areas": ["city", "town", "rural"],
     "rules": [("Selling your own unwanted things is usually tax-free; platforms report sellers with 30+ "
                "sales or about £1,700 a year, which doesn't by itself mean tax is due.", "online_sellers")]},
    {"id": "resell_secondhand", "name": "Buying and reselling second-hand and vintage finds",
     "category": "Selling products",
     "what": "Sourcing clothes, books or homeware from charity shops and car boots and reselling online.",
     "cost": (50, 200), "mode": "online", "customers": ["online", "students"], "areas": ["city", "town", "rural"],
     "rules": [("Buying to resell counts as trading: total trading income over £1,000 a year (before expenses) "
                "must be reported to HMRC.", "online_sellers")]},
    {"id": "baking", "name": "Home baking to order", "category": "Selling products",
     "what": "Birthday cakes, cupcakes or bread for families and local events.",
     "cost": (30, 100), "mode": "in_person", "customers": ["families", "small_biz"], "areas": ["city", "town", "rural"],
     "rules": [("Register as a food business with your council (free) at least 28 days before you start "
                "(England, Wales, NI).", "food_registration"),
               ("A hygiene certificate isn't compulsory, but you must be able to show you've been adequately "
                "trained in food hygiene; expect a home inspection.", "food_registration")]},
    {"id": "upcycling", "name": "Upcycling and reselling furniture", "category": "Selling products",
     "what": "Painting and refreshing second-hand furniture and selling it locally or online.",
     "cost": (50, 200), "mode": "both", "customers": ["renters", "online", "students"], "areas": ["town", "rural"],
     "rules": [("Total trading income over £1,000 a year (before expenses, across all side hustles) must be "
                "reported to HMRC.", "online_sellers")]},
    {"id": "crafts", "name": "Handmade crafts and cards", "category": "Selling products",
     "what": "Selling knitted, sewn or hand-drawn items online, at fairs or to visitors.",
     "cost": (30, 100), "mode": "both", "customers": ["online", "tourists"], "areas": ["city", "town", "rural"],
     "rules": [("Toys for children must meet toy safety rules; check before selling soft toys.", None),
               ("Total trading income over £1,000 a year (before expenses, across all side hustles) must be "
                "reported to HMRC.", "online_sellers")]},
    {"id": "market_stall", "name": "Market or car-boot stall", "category": "Selling products",
     "what": "Selling second-hand goods, crafts or plants at a local market or car-boot sale.",
     "cost": (10, 50), "mode": "in_person", "customers": ["families", "tourists", "older"],
     "areas": ["town", "rural"],
     "rules": [("Selling at a council market needs a casual or permanent licence from the council.",
                "market_stall_licence")]},
    {"id": "plants", "name": "Growing and selling plants and seedlings", "category": "Selling products",
     "what": "Selling cuttings, seedlings or herbs from home or at markets.",
     "cost": (20, 50), "mode": "in_person", "customers": ["families", "older"], "areas": ["town", "rural"],
     "rules": []},
    {"id": "printables", "name": "Digital printables and templates", "category": "Selling products",
     "what": "Selling planners, checklists or party templates as downloads.",
     "cost": (0, 0), "mode": "online", "customers": ["online"], "areas": ["city", "town", "rural"],
     "rules": [("Total trading income over £1,000 a year (before expenses, across all side hustles) must be "
                "reported to HMRC.", "online_sellers")]},
    # ---- Teaching and helping
    {"id": "tutoring", "name": "Tutoring a school subject you're good at", "category": "Teaching and helping",
     "what": "Homework help or exam revision, in person or online.",
     "cost": (0, 0), "mode": "both", "customers": ["families", "students"], "areas": ["city", "town", "rural"],
     "rules": [("Self-employed tutors working with children can apply for their own Enhanced DBS check, and "
                "parents can ask to see it.", "dbs_self_employed")]},
    {"id": "hobby_teaching", "name": "Teaching a hobby or language conversation",
     "category": "Teaching and helping",
     "what": "Small classes or one-to-one sessions in something you enjoy, such as knitting or cooking.",
     "cost": (0, 50), "mode": "both", "customers": ["older", "families", "students"], "areas": ["city", "town", "rural"],
     "rules": []},
    {"id": "tech_help", "name": "Tech help for older people", "category": "Teaching and helping",
     "what": "Setting up phones, video calls and online banking, and showing how to use them.",
     "cost": (0, 0), "mode": "in_person", "customers": ["older", "rural"], "areas": ["town", "rural", "city"],
     "rules": []},
    {"id": "smallbiz_help", "name": "Social media and admin help for local businesses",
     "category": "Teaching and helping",
     "what": "Posting updates, answering messages or simple admin for cafés, shops and tradespeople.",
     "cost": (0, 0), "mode": "online", "customers": ["small_biz"], "areas": ["city", "town"], "rules": []},
    {"id": "proofreading", "name": "Proofreading and CV help", "category": "Teaching and helping",
     "what": "Checking CVs, cover letters and assignments for spelling and clarity.",
     "cost": (0, 0), "mode": "online", "customers": ["students", "time_poor"], "areas": ["city", "town", "rural"],
     "rules": []},
    # ---- Local and events
    {"id": "event_help", "name": "Party and event helper", "category": "Local and events",
     "what": "Setting up, serving and tidying at children's parties and family events.",
     "cost": (0, 0), "mode": "in_person", "customers": ["families", "small_biz"], "areas": ["city", "town", "rural"],
     "rules": []},
    {"id": "face_painting", "name": "Face painting at parties and fairs", "category": "Local and events",
     "what": "Simple face painting at birthday parties, school fairs and festivals.",
     "cost": (50, 100), "mode": "in_person", "customers": ["families"], "areas": ["town", "rural", "city"],
     "rules": []},
    {"id": "walking_tours", "name": "Local walking tours", "category": "Local and events",
     "what": "Showing visitors around your town, its history or its food spots.",
     "cost": (0, 0), "mode": "in_person", "customers": ["tourists"], "areas": ["city", "town"], "rules": []},
]

GENERAL_RULES = [
    ("The first £1,000 of trading income per tax year, across all side hustles and before expenses, is "
     "tax-free (trading allowance).", "trading_allowance"),
    ("Above that, register for Self Assessment by 5 October after the end of that tax year.", "register_sa"),
    ("Check your employment contract for rules about second jobs or competing work.", None),
]

# 1 = present, 2 = notable, 3 = strong. Qualitative; verify against the named datasets.
REGION_DRIVERS = {
    "London": {"time_poor": 3, "renters": 3, "tourists": 3, "small_biz": 3, "students": 2, "families": 2,
               "pet_owners": 1, "older": 1, "rural": 0},
    "South East": {"families": 3, "time_poor": 3, "older": 2, "pet_owners": 2, "tourists": 2, "rural": 2,
                   "students": 1, "small_biz": 2, "renters": 1},
    "South West": {"tourists": 3, "older": 3, "rural": 3, "pet_owners": 2, "families": 2, "students": 1,
                   "small_biz": 1, "time_poor": 1, "renters": 1},
    "East of England": {"time_poor": 3, "rural": 3, "families": 2, "older": 2, "tourists": 2, "students": 1,
                        "pet_owners": 2, "small_biz": 1, "renters": 1},
    "East Midlands": {"families": 2, "students": 2, "time_poor": 2, "tourists": 2, "rural": 2, "older": 2,
                      "pet_owners": 2, "small_biz": 1, "renters": 1},
    "West Midlands": {"students": 2, "small_biz": 2, "families": 2, "time_poor": 2, "rural": 2, "older": 2,
                      "renters": 2, "tourists": 1, "pet_owners": 1},
    "North West": {"students": 3, "time_poor": 2, "tourists": 2, "families": 2, "renters": 2, "older": 2,
                   "small_biz": 2, "rural": 1, "pet_owners": 1},
    "North East": {"older": 2, "students": 2, "tourists": 2, "rural": 2, "families": 2, "small_biz": 1,
                   "time_poor": 1, "renters": 1, "pet_owners": 1},
    "Yorkshire and the Humber": {"tourists": 3, "students": 2, "rural": 2, "families": 2, "older": 2,
                                 "time_poor": 2, "small_biz": 1, "renters": 1, "pet_owners": 1},
    "Wales": {"tourists": 3, "rural": 3, "older": 2, "students": 2, "families": 2, "pet_owners": 2,
              "small_biz": 1, "time_poor": 1, "renters": 1},
    "Scotland": {"tourists": 3, "rural": 3, "students": 2, "time_poor": 2, "older": 2, "families": 2,
                 "small_biz": 1, "renters": 1, "pet_owners": 1},
    "Northern Ireland": {"rural": 3, "families": 3, "tourists": 2, "older": 2, "small_biz": 1, "students": 1,
                         "time_poor": 1, "renters": 1, "pet_owners": 2},
}
for _w in REGION_DRIVERS.values():
    _w["online"] = 2  # online demand is UK-wide
    _w["pet_owners"] = max(_w.get("pet_owners", 0), 2)  # pet ownership is widespread across the UK

# Datasets to verify the regional weights against (England and Wales: Census 2021; Scotland: Census 2022;
# Northern Ireland: Census 2021 by NISRA)
VERIFY_WITH = {
    "older": "Census age structure (ONS TS007a; NRS Scotland; NISRA)",
    "students": "Census schoolchildren and full-time students (ONS TS068)",
    "families": "Census household composition (ONS TS003)",
    "rural": "Rural-urban classification (Defra, Population statistics for rural England; Scottish/Welsh/NI equivalents)",
    "tourists": "VisitBritain GB Tourism Survey, regional data",
    "time_poor": "Census travel to work and hours worked (ONS TS058, TS059)",
    "renters": "Census tenure (ONS TS054)",
    "small_biz": "UK Business Counts (ONS IDBR via Nomis)",
    "pet_owners": "PDSA Animal Wellbeing (PAW) Report, regional figures",
}

AREA_DRIVERS = {
    "city": {"time_poor": 2, "renters": 2, "students": 2, "small_biz": 1, "tourists": 1},
    "town": {"families": 2, "older": 1, "pet_owners": 1, "time_poor": 1},
    "rural": {"rural": 2, "older": 1, "tourists": 1, "pet_owners": 1},
}


def cost_label(h):
    lo, hi = h["cost"]
    if hi == 0:
        return "£0"
    return f"£{lo}-{hi}" if lo else f"up to £{hi}"


def score(h, region=None, area_type=None):
    """Fit of a hustle for an area: sum of demand weights of its customer groups, plus area fit."""
    weights = dict(REGION_DRIVERS.get(region, {k: 1 for k in DRIVERS}))
    for k, v in AREA_DRIVERS.get(area_type, {}).items():
        weights[k] = weights.get(k, 0) + v
    vals = sorted((weights.get(c, 0) for c in h["customers"]), reverse=True)
    # Strongest customer group counts fully; extra groups add a little, so long tag lists don't dominate.
    s = vals[0] + 0.1 * sum(vals[1:]) if vals else 0
    if area_type and area_type not in h["areas"]:
        s -= 3
    return round(s, 2)


def best_for(region=None, area_type=None, n=8, per_category=2):
    """Top hustles for an area, with at most `per_category` from each category for variety."""
    ranked = sorted(HUSTLES, key=lambda h: (-score(h, region, area_type), h["name"]))
    picked, counts = [], {}
    for h in ranked:
        if counts.get(h["category"], 0) < per_category:
            picked.append(h)
            counts[h["category"]] = counts.get(h["category"], 0) + 1
        if len(picked) == n:
            break
    return picked


def _rule_text(rule):
    text, src = rule
    return text


def catalogue_text():
    """Compact catalogue for AI prompts (same for both AI conditions)."""
    lines = []
    category = None
    for h in HUSTLES:
        if h["category"] != category:
            category = h["category"]
            lines.append(f"{category}:")
        who = ", ".join(DRIVERS[c].lower() for c in h["customers"])
        rules = "; ".join(_rule_text(r) for r in h["rules"])
        lines.append(f"- {h['name']} (start-up {cost_label(h)}; customers: {who})" + (f". Rule: {rules}" if rules else ""))
    lines.append("General: " + " ".join(_rule_text(r) for r in GENERAL_RULES))
    return "\n".join(lines)


def best_fits_text(region, area_type):
    """For the backend prompt: the best-fitting hustles for one participant's area."""
    return ", ".join(h["name"].lower() for h in best_for(region, area_type))


def gorilla_region_table():
    """For static Gorilla prompts: best-fitting hustles per region (any area type) and per area type."""
    lines = [f"- {r}: " + ", ".join(h["name"].lower() for h in best_for(r, None, 8)) for r in REGION_DRIVERS]
    lines.append("Adjust for type of area:")
    for a, label in (("city", "City"), ("town", "Town or suburb"), ("rural", "Village or rural area")):
        lines.append(f"- {label}: favour " + ", ".join(h["name"].lower() for h in best_for(None, a, 6)))
    return "\n".join(lines)


def export_json():
    return {
        "checked_on": CHECKED_ON,
        "sources": SOURCES,
        "drivers": DRIVERS,
        "hustles": [dict(h, cost=list(h["cost"]), cost_label=cost_label(h),
                         rules=[{"text": t, "source": s} for t, s in h["rules"]]) for h in HUSTLES],
        "general_rules": [{"text": t, "source": s} for t, s in GENERAL_RULES],
        "region_drivers": REGION_DRIVERS,
        "area_drivers": AREA_DRIVERS,
        "verify_with": VERIFY_WITH,
    }
