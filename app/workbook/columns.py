"""The columns of tab 3 (Hazard list). The reader finds them by header name, so order does not matter."""

NUMBER_FIELDS = ["killed", "injured", "affected", "displaced", "houses"]

# (header, field). The area column header comes from the country set-up (for example "Oblasts").
COLUMNS = [
    ("Year", "year"),
    ("Start month", "start"),
    ("End month", "end"),
    ("Hazard type", "type"),
    ("Hazard sub-type", "sub"),
    (None, "areas"),
    ("Description of hazard/shock", "desc"),
    ("Impact (notes)", "impact"),
    ("Killed", "killed"),
    ("Injured", "injured"),
    ("Affected", "affected"),
    ("Displaced", "displaced"),
    ("Houses damaged", "houses"),
    ("Sectors affected", "sectors"),
    ("Underlying factors (tags)", "factors"),
    ("Underlying factors (notes)", "factorNotes"),
    ("Mitigating factors", "mitigating"),
    ("Sources", "sources"),
    ("Verified", "verified"),
]

REQUIRED = {"year", "start", "end", "type", "sub", "areas", "desc", "sources", "verified"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]

HAZARD_SHEET_HINT = "hazard list"   # tab name must contain this text

# Headers in tab Lists. The reader finds each list by header, so the order of columns does not matter.
LIST_HEADERS = {
    "types": "Hazard types",
    "subs": "Hazard sub-types",
    "sub_type": "Sub-type belongs to",
    "sectors": "Sectors",
    "factors": "Underlying factors",
    "factor_context": "Factor goes under",
    "contexts": "Context headings",
}
# The Context boxes of the tree. Fixed, because each is a box in the layout.
CONTEXTS = ("Political", "Economic", "Socio-cultural", "Security", "Environmental and physical")


def columns_for(area_column):
    return [(h if h else area_column, k) for h, k in COLUMNS]


def split_list(value):
    """Cells with several values are separated by semicolons."""
    return [x.strip() for x in str(value or "").split(";") if x.strip()]
